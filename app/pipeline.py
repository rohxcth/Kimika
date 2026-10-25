"""Kimika pipeline: Discover → Classify → Pick → Research → Write → Verify → Save.

Run manually:  python -m app.pipeline --now
Run for a date: python -m app.pipeline --date 2026-10-26

Stages
------
1. discover   — pull M&A candidates from EDGAR, ASX, RNS (app/sources.py)
2. classify   — batch-classify with LLM (app/llm.py), filter to M&A
3. pick       — rank by deal value (US$ equiv); take top N for full reports
4. research   — fetch and trim the primary document for each deal
5. write      — call LLM to produce structured ReportData (app/llm.py)
6. verify     — attach verification log to each report
7. save       — write report.json + update index.json (app/report.py)
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

from app.config import cfg
from app.fetch import fetch
from app.finance import to_usd
from app import llm
from app.report import ReportData, save_report
from app.sources import RawDeal, discover_all

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

    # 2. Classify (batch LLM call)
    classifications = llm.classify_deals(raw_deals)
    ma_deals = _filter_ma(raw_deals, classifications)
    logger.info("%d candidates classified as M&A", len(ma_deals))

    # 3. Pick: rank by deal value; top N get full reports
    ranked = _rank_deals(ma_deals)
    full_deals = ranked[:_MAX_FULL]

    # 4 + 5 + 6. Research → Write → Verify for each deal
    saved_reports: list[ReportData] = []
    for deal in full_deals:
        report = _research_write_verify(deal, date_str)
        if report is not None:
            save_report(report)
            saved_reports.append(report)

    quota = llm.quota_log()
    logger.info(
        "Pipeline done: %d full reports, quota=%s",
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

def _filter_ma(
    raw_deals: list[RawDeal],
    classifications: list[dict],
) -> list[RawDeal]:
    """Return only deals classified as M&A (excluding not_a_deal)."""
    cls_by_index = {c["index"]: c for c in classifications}
    result = []
    for i, deal in enumerate(raw_deals):
        cls = cls_by_index.get(i, {})
        if cls.get("deal_type") == "M&A":
            result.append(deal)
    return result


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
    """Fetch primary doc, call LLM, attach verification log.

    Returns None if the primary document cannot be fetched (logged; never crashes).
    """
    url = deal.get("url", "")
    primary_doc = ""
    if url:
        try:
            raw = fetch(url)
            primary_doc = raw[:_TRIM_CHARS]  # trim to budget
        except Exception as exc:
            logger.warning("Could not fetch primary doc for %s (%s): %s",
                           deal.get("title"), url, exc)
            # Continue with empty doc — LLM will note "Not publicly disclosed"

    secondary_sources = ""  # Step 6 stub; Step 7 adds secondary fetching

    try:
        report = llm.write_ma_report(deal, primary_doc, secondary_sources, date_str)
    except Exception as exc:
        logger.error("LLM write failed for %s: %s", deal.get("title"), exc)
        return None

    # Attach stub verification log (real crosscheck added in Step 7)
    report.verification_log = _stub_verification(report)
    return report


def _stub_verification(report: ReportData) -> list[dict]:
    """Placeholder verification log — Step 7 replaces with real crosscheck calls."""
    return [
        {
            "figure": "pipeline_stub",
            "value": "n/a",
            "status": "❓ Single source",
            "sources": ["stub"],
            "note": "Verification not yet implemented (Step 7).",
        }
    ]



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
