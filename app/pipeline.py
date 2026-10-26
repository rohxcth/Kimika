"""Kimika pipeline: Pool → Collate → Verify → Style → Synthesise → Save.

Run manually:  python -m app.pipeline --now
Run for a date: python -m app.pipeline --date 2026-10-26

Stages (per report)
-------------------
1. Pool      — discover candidates (EDGAR, ASX, RNS) + fetch primary doc + news
2. Collate   — build a labelled Dossier from all fetched sources (app/dossier.py)
3. Verify    — cross-reference structured figures; resolve conflicts (app/verify.py)
4. Style     — format dossier into (primary_doc, secondary_sources) strings (app/prompts)
5. Synthesise — call LLM with verified facts and formatted sources (app/llm.py)
6. Save      — write report.json + update index.json (app/report.py)
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime

from app.config import cfg
from app.dossier import build_deal_dossier, build_market_dossier
from app.fetch import extract_text, fetch
from app.finance import to_usd
from app import llm
from app.prompts import format_dossier_for_prompt
from app.report import ReportData, save_report
from app.sources import (
    RawDeal,
    discover_all,
    discover_deal_market_data,
    discover_economy_context,
    discover_market_figures,
    discover_markets_context,
    discover_news,
)
from app.verify import verify_claim_groups

logger = logging.getLogger(__name__)

_MAX_FULL = cfg["pipeline"]["max_full_reports_per_run"]
_TRIM_CHARS = cfg["pipeline"]["doc_trim_chars"]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(date_str: str | None = None) -> dict:
    """Run the full pipeline for the given date (YYYY-MM-DD), or today if None.

    Returns a summary dict: {"date", "full_reports", "wrap_entries", "quota"}.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    target_date = date.fromisoformat(date_str)
    logger.info("Pipeline run started for %s", date_str)

    # 1. Discover
    raw_deals = discover_all(target_date)
    logger.info("Discovered %d raw candidates", len(raw_deals))

    # 2. Classify (batch LLM call) → bucket by deal type
    classifications = llm.classify_deals(raw_deals)
    buckets = _bucket_deals(raw_deals, classifications)
    logger.info(
        "Classified: M&A=%d ECM=%d DCM=%d Other=%d",
        len(buckets["M&A"]), len(buckets["ECM"]),
        len(buckets["DCM"]), len(buckets["Other"]),
    )

    # 3. Pick: rank each bucket by deal value; combined top N get full reports
    all_deals = (
        _rank_deals(buckets["M&A"])
        + _rank_deals(buckets["ECM"])
        + _rank_deals(buckets["DCM"])
        + _rank_deals(buckets["Other"])
    )
    full_deals = all_deals[:_MAX_FULL]

    # 4 + 5 + 6. Research → Write → Verify for each deal
    saved_reports: list[ReportData] = []
    for deal in full_deals:
        report = _research_write_verify(deal, date_str)
        if report is not None:
            save_report(report)
            saved_reports.append(report)

    # 7. Five daily market column reports (Economy, Equities, Commodities, Bonds, Currencies)
    for market_report in _write_market_reports(date_str):
        save_report(market_report)
        saved_reports.append(market_report)

    quota = llm.quota_log()
    logger.info(
        "Pipeline done: %d total reports (incl. economy), quota=%s",
        len(saved_reports), quota,
    )
    return {
        "date": date_str,
        "full_reports": len(saved_reports),
        "quota": quota,
    }


# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------

def _bucket_deals(
    raw_deals: list[RawDeal],
    classifications: list[dict],
) -> dict[str, list[RawDeal]]:
    """Group deals by type: M&A, ECM, DCM, Other. Drops not_a_deal."""
    buckets: dict[str, list[RawDeal]] = {"M&A": [], "ECM": [], "DCM": [], "Other": []}
    cls_by_index = {c["index"]: c for c in classifications}
    for i, deal in enumerate(raw_deals):
        deal_type = cls_by_index.get(i, {}).get("deal_type", "not_a_deal")
        if deal_type in buckets:
            # Attach classified deal_type so the writer can route correctly
            deal = dict(deal)
            deal["deal_type"] = deal_type
            buckets[deal_type].append(deal)
    return buckets


def _rank_deals(deals: list[RawDeal]) -> list[RawDeal]:
    """Rank M&A deals by deal value (US$ equivalent), largest first.

    Deals with unknown value are placed after known-value deals, preserving
    their original relative order (source order = discovery priority).

    Finance note: deal value in US$ = local value × FX rate (USD per local unit).
    E.g. A$2,050m at AUD/USD 0.65 → US$1,332.5m. Unknown values sort last.
    """
    def sort_key(deal: RawDeal):
        val = deal.get("extra", {}).get("deal_value_usd")
        # Use `is not None` to distinguish None (unknown) from 0 (explicitly zero).
        # Negative values are data errors; both 0 and negatives sort after real values.
        if val is not None and val > 0:
            return -val   # negative so larger values sort first
        return 0          # unknown/zero/negative → sort after known values (0 ≥ -any_positive)

    return sorted(deals, key=sort_key)


def _research_write_verify(deal: RawDeal, date_str: str) -> ReportData | None:
    """Pool → Collate → Verify → Style → Synthesise for a single deal.

    Returns None if the LLM call fails (logged; never crashes the pipeline).
    """
    # Stage 1: Pool — fetch primary document and clean HTML boilerplate
    url = deal.get("url", "")
    primary_doc_text = ""
    source_label = deal.get("source") or "primary filing"
    if url:
        try:
            raw = fetch(url)
            # Strip nav/script/footer boilerplate so the LLM sees filing content only
            primary_doc_text = extract_text(raw)[:_TRIM_CHARS]
        except Exception as exc:
            logger.warning("Could not fetch primary doc for %s (%s): %s",
                           deal.get("title"), url, exc)

    # Stage 1 (cont.): Pool — discover news from multiple angles for richer context.
    # Query 1: deal title + company (catches deal-specific coverage).
    # Query 2: company name alone (catches background on the parties, prior bids,
    #           financial profile, analyst views not tied to this specific announcement).
    news_items: list = []
    seen_news_urls: set[str] = set()
    base_queries = []
    deal_query = f"{deal.get('company', '')} {deal.get('title', '')}".strip()[:120]
    if deal_query:
        base_queries.append(deal_query)
    company_query = (deal.get("company") or "").strip()[:80]
    if company_query and company_query not in base_queries:
        base_queries.append(company_query)
    for q in base_queries:
        try:
            for item in discover_news(q, max_results_per_source=8):
                if item["url"] not in seen_news_urls:
                    seen_news_urls.add(item["url"])
                    news_items.append(item)
        except Exception as exc:
            logger.warning("News discovery failed for %r: %s", q, exc)

    # Stage 1 (cont.): Pool — target/acquirer share price history for premium analysis
    raw_texts = [(source_label, primary_doc_text)] if primary_doc_text else []
    market_data_text = ""
    try:
        market_data_text = discover_deal_market_data(deal)
    except Exception as exc:
        logger.warning("Deal market data failed for %s: %s", deal.get("title"), exc)
    if market_data_text:
        raw_texts.append(("Market price data", market_data_text))

    # Stage 2: Collate — assemble dossier with labelled source chunks
    deal_type_label = deal.get("deal_type", "M&A")
    report_type = {"M&A": "ma_full", "ECM": "ecm", "DCM": "dcm"}.get(deal_type_label, "ma_full")
    topic = deal.get("title") or "Unknown deal"
    dossier = build_deal_dossier(topic, report_type, date_str, raw_texts, news_items=news_items)

    # Stage 3: Verify — cross-reference structured figures from deal metadata.
    # Numeric fields from deal["extra"] (e.g. deal_value_usd) become claim groups
    # with one source each, producing Single-source status — accurate for a filing
    # seen for the first time. As more sources land, status upgrades to Verified.
    claim_groups = _deal_claim_groups(deal)
    verify_result = verify_claim_groups(claim_groups)

    # Stage 4: Style — format dossier into prompt-ready strings
    primary_doc, secondary_sources = format_dossier_for_prompt(dossier)

    # Stage 5: Synthesise
    verified_facts_str = (
        json.dumps(verify_result["verified_facts"], indent=2)
        if verify_result["verified_facts"] else ""
    )

    writer = {
        "M&A":   llm.write_ma_report,
        "ECM":   llm.write_ecm_report,
        "DCM":   llm.write_dcm_report,
        "Other": llm.write_ma_report,
    }.get(deal_type_label, llm.write_ma_report)

    try:
        report = writer(deal, primary_doc, secondary_sources, date_str,
                        verified_facts=verified_facts_str)
    except Exception as exc:
        logger.error("LLM write failed for %s: %s", deal.get("title"), exc)
        return None

    report.verification_log = verify_result["verification_log"]
    return report


def _deal_claim_groups(deal: RawDeal) -> dict:
    """Extract claim groups from a deal's extra metadata for cross-verification.

    Numeric fields in deal["extra"] (e.g. deal_value_usd, offer_price) become
    single-source claim groups. Text fields are excluded. Status will be
    Single source until a second independent source confirms the same value.

    Finance note: only positive numeric values are included; 0 and negative
    values indicate unknown or data errors and are excluded.
    """
    groups: dict = {}
    extra = deal.get("extra") or {}
    source = deal.get("source") or "primary filing"
    for key, val in extra.items():
        if isinstance(val, (int, float)) and val > 0:
            groups[key] = {source: val}
    return groups


def _write_market_reports(date_str: str) -> list[ReportData]:
    """Pool → Collate → Verify → Style → Synthesise for all 5 market columns.

    Economy, Equities, Commodities, Bonds, Currencies — one report per column.
    A failure in any single column is logged and skipped; the others still run.
    """
    target_date = date.fromisoformat(date_str)
    reports: list[ReportData] = []

    # Stage 1: Pool — fetch primary data contexts
    try:
        economy_ctx = discover_economy_context(target_date)
    except Exception as exc:
        logger.warning("Economy context fetch failed: %s", exc)
        economy_ctx = ""

    try:
        markets_ctx = discover_markets_context(target_date)
    except Exception as exc:
        logger.warning("Markets context fetch failed: %s", exc)
        markets_ctx = {}

    # Stage 1 (cont.): fetch structured market figures for cross-verification
    try:
        market_figures = discover_market_figures()
    except Exception as exc:
        logger.warning("Market figures fetch failed: %s", exc)
        market_figures = {}

    # Per-column configuration: (report_type, writer_fn, label, primary_ctx, news_query)
    columns = [
        ("economy",     llm.write_economy_report,     "Economy",
         economy_ctx,                          "Federal Reserve FOMC RBA monetary policy interest rates"),
        ("equities",    llm.write_equities_report,    "Equities",
         markets_ctx.get("equities", ""),      "stock market S&P 500 ASX 200 equities index"),
        ("commodities", llm.write_commodities_report, "Commodities",
         markets_ctx.get("commodities", ""),   "oil gold copper iron ore commodities"),
        ("bonds",       llm.write_bonds_report,       "Bonds",
         markets_ctx.get("bonds", ""),         "US Treasury yield bonds interest rates"),
        ("currencies",  llm.write_currencies_report,  "Currencies",
         markets_ctx.get("currencies", ""),    "USD AUD EUR FX exchange rate currency"),
    ]

    for report_type, writer_fn, label, ctx, news_query in columns:
        try:
            # Stage 1 (cont.): Pool news for secondary commentary
            news_items = []
            try:
                news_items = discover_news(news_query, max_results_per_source=5)
            except Exception as exc:
                logger.debug("News discovery for %s failed: %s", label, exc)

            # Stage 2: Collate
            raw_texts = [(f"{label} context", ctx)] if ctx else []
            dossier = build_market_dossier(report_type, date_str, raw_texts, {}, news_items=news_items)

            # Stage 3: Verify — use structured figures for this column where available;
            # economy has no numeric claim groups (prose only)
            claim_groups = market_figures.get(report_type, {})
            verify_result = verify_claim_groups(claim_groups)

            # Stage 4: Style
            primary_doc, secondary_sources = format_dossier_for_prompt(dossier)

            # Stage 5: Synthesise
            verified_facts_str = (
                json.dumps(verify_result["verified_facts"], indent=2)
                if verify_result["verified_facts"] else ""
            )
            if label == "Economy":
                report = writer_fn(primary_doc, secondary_sources, date_str,
                                   verified_facts=verified_facts_str)
            else:
                report = writer_fn(primary_doc, date_str, verified_facts=verified_facts_str)

            report.verification_log = verify_result["verification_log"]
            reports.append(report)
            logger.info("Market report written: %s", label)
        except Exception as exc:
            logger.error("%s report write failed: %s", label, exc)

    return reports


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the Kimika pipeline")
    parser.add_argument("--now", action="store_true", help="Run for today")
    parser.add_argument("--date", help="Run for YYYY-MM-DD")
    args = parser.parse_args()
    summary = run(date_str=args.date)
    print(summary)


if __name__ == "__main__":
    main()
