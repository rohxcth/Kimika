"""Kimika LLM interface — Google Gemini (free tier).

Step 7 fills in the real Gemini calls. For now every function returns a
realistic stub so the pipeline, save, and test paths work end-to-end.

Public interface (called by pipeline.py):
  classify_deals(raw_deals)   → list of classification dicts
  write_ma_report(deal, doc, sources, date_str) → ReportData
  write_deal_wrap(deals, date_str) → list of deal-wrap entry dicts

Quota tracking is a no-op stub until Step 7.
"""

from __future__ import annotations

import json
import logging
from datetime import date as _date

from app.report import ReportData, make_slug

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quota tracker stub (Step 7 implements real tracking)
# ---------------------------------------------------------------------------

_request_counts: dict[str, int] = {"flash": 0, "flash_lite": 0}


def quota_log() -> dict[str, int]:
    """Return request counts per model for this run."""
    return dict(_request_counts)


# ---------------------------------------------------------------------------
# Classify deals (Flash-Lite)
# ---------------------------------------------------------------------------

def classify_deals(raw_deals: list[dict]) -> list[dict]:
    """Classify a batch of RawDeals into M&A / ECM / DCM / Other / not_a_deal.

    Stub: marks everything as M&A with medium confidence.
    Step 7 replaces this with a batched Flash-Lite call.
    """
    _request_counts["flash_lite"] += 1  # one batched call for all deals
    results = []
    for i, deal in enumerate(raw_deals):
        filing_type = deal.get("filing_type", "")
        # Simple heuristic for stub: use filing type keywords
        if any(kw in filing_type for kw in ("8-K", "DEFM14A", "SC TO-T", "ASX_announcement", "RNS_Rule")):
            deal_type = "M&A"
            confidence = "medium"
        else:
            deal_type = "Other"
            confidence = "low"
        results.append({
            "index": i,
            "deal_type": deal_type,
            "region": deal.get("region", "Unknown"),
            "confidence": confidence,
            "reason": "Stub classification — Step 7 replaces with Gemini Flash-Lite.",
        })
    return results


# ---------------------------------------------------------------------------
# Write M&A full report (Flash)
# ---------------------------------------------------------------------------

def write_ma_report(
    deal: dict,
    primary_doc: str,
    secondary_sources: str,
    date_str: str,
) -> ReportData:
    """Write a full M&A report from the primary document and secondary sources.

    Stub: returns a pre-filled ReportData so the save path can be tested.
    Step 7 replaces this with a real Flash call using app/prompts/ma_report.py.
    """
    _request_counts["flash"] += 1
    company = deal.get("company", "Unknown")
    region = deal.get("region", "US")
    title = f"{company} — M&A transaction"

    slug = make_slug(title, region, "ma_full", date_str)

    return ReportData(
        slug=slug,
        date=date_str,
        report_type="ma_full",
        region=region,
        title=title,
        key_takeaways=[
            "Stub report — Step 7 will populate with Gemini output.",
            "Primary document fetched and trimmed successfully.",
            "Verification log attached below.",
        ],
        sections={
            "1_deal_snapshot": "Not yet populated — LLM stub.",
            "2_strategic_rationale": "Not yet populated — LLM stub.",
            "3_process_and_negotiations": "Not publicly disclosed.",
            "4_valuation": "Not yet populated — LLM stub.",
            "5_structure_terms_financing": "Not yet populated — LLM stub.",
            "6_advisers": "Not publicly disclosed.",
            "7_market_view": "Not yet populated — LLM stub.",
            "8_outlook_and_scenarios": "Not yet populated — LLM stub.",
        },
        bibliography=[],
        metadata={
            "acquirer": "Unknown",
            "target": company,
            "deal_value_usd": None,
            "structure": "Unknown",
            "region": region,
            "status": "announced",
            "primary_doc_chars": len(primary_doc),
        },
        verification_log=[],
    )


# ---------------------------------------------------------------------------
# Write deal wrap entries (Flash-Lite)
# ---------------------------------------------------------------------------

def write_deal_wrap(deals: list[dict], date_str: str) -> list[dict]:
    """Write compact deal-wrap entries for deals without full reports.

    Stub: returns minimal entries.
    Step 7 replaces this with a batched Flash-Lite call.
    """
    _request_counts["flash_lite"] += 1
    entries = []
    for deal in deals:
        entries.append({
            "region": deal.get("region", "?"),
            "deal_type": "M&A",
            "parties": deal.get("company", "Unknown"),
            "size": "Not publicly disclosed",
            "key_term": "Not publicly disclosed",
            "status": "Announced",
            "context_line": f"Source: {deal.get('source', '?')}",
        })
    return entries
