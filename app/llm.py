"""Kimika LLM interface — Google Gemini (free tier).

Model routing:
  Flash-Lite  →  classify_deals   (volume; batched)
  Flash       →  write_ma_report  (quality; one per report)

Model names and daily caps come from config.yaml — never hard-coded here.

Quota guard: before each call, check remaining quota for the model. If the
cap is reached, log a warning and return the stub result so the run publishes
what it has rather than crashing.

429 back-off: on a ClientError with code=429, wait backoff_base_seconds (from
config.yaml), double it each retry, up to max_retries. After max retries, fall
back to the stub result and log an error.

Response caching: Gemini responses are cached by SHA-256 of the prompt string
in cache/llm/. Same TTL as the fetch cache. Avoids re-processing unchanged
documents across runs.

JSON parsing: Gemini sometimes wraps JSON in ```json ... ``` fences — we strip
them. If the JSON is still invalid, log and return the stub.

Public interface (called by pipeline.py):
  classify_deals(raw_deals)                        → list[dict]
  write_ma_report(deal, doc, sources, date_str)    → ReportData
  quota_log()                                      → dict[str, int]
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path

from app.config import cfg
from app.prompts.ma_report import CLASSIFY_BATCH, MA_FULL_REPORT, SYSTEM
from app.prompts.ecm_dcm_report import ECM_FULL_REPORT, DCM_FULL_REPORT
from app.prompts.economy_report import (
    ECONOMY_SECTION, EQUITIES_SECTION, COMMODITIES_SECTION,
    BONDS_SECTION, CURRENCIES_SECTION,
)
from app.report import ReportData, make_slug

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_FLASH = cfg["gemini"]["flash_model"]
_FLASH_LITE = cfg["gemini"]["flash_lite_model"]
_FLASH_CAP = cfg["gemini"]["flash_daily_cap"]
_FLASH_LITE_CAP = cfg["gemini"]["flash_lite_daily_cap"]
_BACKOFF_BASE = cfg["gemini"]["backoff_base_seconds"]
_MAX_RETRIES = cfg["gemini"]["backoff_max_retries"]
_CACHE_TTL = cfg["pipeline"]["cache_ttl_hours"] * 3600

_LLM_CACHE_DIR = Path(cfg["reports"]["output_dir"]).parent / "cache" / "llm"

# ---------------------------------------------------------------------------
# Request counters (reset on each process start; one run = one process)
# ---------------------------------------------------------------------------

_request_counts: dict[str, int] = {"flash": 0, "flash_lite": 0}


def quota_log() -> dict[str, int]:
    """Return request counts per model for this run."""
    return dict(_request_counts)


def reset_quota_log() -> None:
    """Reset counters (used in tests)."""
    _request_counts["flash"] = 0
    _request_counts["flash_lite"] = 0


# ---------------------------------------------------------------------------
# Gemini client (lazy init so tests don't need GEMINI_API_KEY at import time)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from app.config import require_env
        api_key = require_env("GEMINI_API_KEY")
        _client = genai.Client(api_key=api_key)
    return _client


def _set_client(client) -> None:
    """Override the client (used in tests to inject a mock)."""
    global _client
    _client = client


# ---------------------------------------------------------------------------
# Core: call Gemini with quota guard, 429 back-off, and caching
# ---------------------------------------------------------------------------

def _call(model: str, model_key: str, prompt: str) -> str | None:
    """Call Gemini and return the response text, or None on failure.

    None means the caller should fall back to the stub result.
    The prompt is the complete text sent to the model (system + user).
    """
    cap = _FLASH_CAP if model_key == "flash" else _FLASH_LITE_CAP

    # Quota check before the call
    if _request_counts[model_key] >= cap:
        logger.warning(
            "Quota reached for %s (%d/%d requests used). Falling back to stub.",
            model_key, _request_counts[model_key], cap,
        )
        return None

    # Cache check — skip real call if we already have a response for this prompt
    cached = _cache_get(prompt)
    if cached is not None:
        logger.debug("LLM cache hit for model=%s", model_key)
        return cached

    client = _get_client()
    wait = _BACKOFF_BASE

    for attempt in range(_MAX_RETRIES + 1):
        try:
            from google import genai
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM,
                ),
            )
            _request_counts[model_key] += 1
            text = response.text
            _cache_set(prompt, text)
            logger.info("Gemini %s call #%d succeeded", model_key, _request_counts[model_key])
            return text

        except Exception as exc:
            # Detect 429 by checking the error code if available
            is_429 = (
                getattr(exc, "code", None) == 429
                or "429" in str(exc)
                or "quota" in str(exc).lower()
                or "resource_exhausted" in str(exc).lower()
            )
            if is_429 and attempt < _MAX_RETRIES:
                logger.warning(
                    "429 from Gemini %s — waiting %ds (attempt %d/%d)",
                    model_key, wait, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(wait)
                wait *= 2
                continue

            logger.error("Gemini %s call failed (attempt %d): %s", model_key, attempt + 1, exc)
            return None  # fall back to stub

    return None


# ---------------------------------------------------------------------------
# JSON extraction from Gemini response
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict | list | None:
    """Extract and parse JSON from a Gemini response.

    Handles:
    - Clean JSON
    - JSON wrapped in ```json ... ``` fences
    - JSON wrapped in ``` ... ``` fences
    """
    if text is None:
        return None

    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object/array anywhere in the text
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    logger.warning("Could not parse JSON from Gemini response (length=%d)", len(text))
    return None


# ---------------------------------------------------------------------------
# LLM response cache (keyed by SHA-256 of prompt)
# ---------------------------------------------------------------------------

def _cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def _cache_path(prompt: str) -> Path:
    key = _cache_key(prompt)
    return _LLM_CACHE_DIR / key[:2] / (key + ".json")


def _cache_get(prompt: str) -> str | None:
    path = _cache_path(prompt)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - data["cached_at"]
        if age > _CACHE_TTL:
            return None
        return data["text"]
    except Exception as exc:
        logger.debug("LLM cache read error: %s", exc)
        return None


def _cache_set(prompt: str, text: str) -> None:
    path = _cache_path(prompt)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"cached_at": time.time(), "text": text}),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("LLM cache write error: %s", exc)


# ---------------------------------------------------------------------------
# Stub results (returned when quota is exceeded or call fails)
# ---------------------------------------------------------------------------

def _stub_classification(index: int, deal: dict) -> dict:
    filing_type = deal.get("filing_type", "")
    deal_type = "M&A" if any(
        kw in filing_type for kw in ("8-K", "DEFM14A", "SC TO-T", "ASX_announcement", "RNS_Rule")
    ) else "Other"
    return {
        "index": index,
        "deal_type": deal_type,
        "region": deal.get("region", "Unknown"),
        "confidence": "low",
        "reason": "Stub classification (Gemini unavailable).",
    }


def _stub_ma_report(deal: dict, date_str: str) -> ReportData:
    company = deal.get("company", "Unknown")
    region = deal.get("region", "US")
    title = f"{company} — M&A transaction"
    return ReportData(
        slug=make_slug(title, region, "ma_full", date_str),
        date=date_str,
        report_type="ma_full",
        region=region,
        title=title,
        key_takeaways=["Stub report — Gemini unavailable or quota exceeded."],
        sections={
            "1_deal_snapshot": "Not yet populated.",
            "2_strategic_rationale": "Not yet populated.",
            "3_process_and_negotiations": "Not publicly disclosed.",
            "4_valuation": "Not yet populated.",
            "5_structure_terms_financing": "Not yet populated.",
            "6_advisers": "Not publicly disclosed.",
            "7_market_view": "Not yet populated.",
            "8_outlook_and_scenarios": "Not yet populated.",
        },
        bibliography=[],
        metadata={
            "acquirer": "Unknown", "target": company,
            "deal_value_usd": None, "structure": "Unknown",
            "region": region, "status": "announced",
        },
        verification_log=[],
    )


def _stub_ecm_report(deal: dict, date_str: str) -> ReportData:
    company = deal.get("company", "Unknown")
    region = deal.get("region", "US")
    title = f"{company} — ECM transaction"
    return ReportData(
        slug=make_slug(title, region, "ecm", date_str),
        date=date_str,
        report_type="ecm",
        region=region,
        title=title,
        key_takeaways=["Stub report — Gemini unavailable or quota exceeded."],
        sections={
            "1_snapshot": "Not yet populated.",
            "2_why_now": "Not yet populated.",
            "3_process": "Not publicly disclosed.",
            "4_pricing": "Not yet populated.",
            "5_underwriting_and_fees": "Not publicly disclosed.",
            "6_market_view": "Not yet populated.",
            "7_outlook": "Not yet populated.",
        },
        bibliography=[],
        metadata={
            "issuer": company, "raise_type": "Unknown",
            "deal_value_usd": None, "region": region, "status": "announced",
        },
        verification_log=[],
    )


def _stub_dcm_report(deal: dict, date_str: str) -> ReportData:
    company = deal.get("company", "Unknown")
    region = deal.get("region", "US")
    title = f"{company} — DCM transaction"
    return ReportData(
        slug=make_slug(title, region, "dcm", date_str),
        date=date_str,
        report_type="dcm",
        region=region,
        title=title,
        key_takeaways=["Stub report — Gemini unavailable or quota exceeded."],
        sections={
            "1_snapshot": "Not yet populated.",
            "2_credit_story": "Not yet populated.",
            "3_process": "Not publicly disclosed.",
            "4_pricing": "Not yet populated.",
            "5_use_of_proceeds": "Not yet populated.",
            "6_market_view": "Not yet populated.",
            "7_outlook": "Not yet populated.",
        },
        bibliography=[],
        metadata={
            "issuer": company, "instrument": "Unknown",
            "deal_value_usd": None, "region": region, "status": "announced",
        },
        verification_log=[],
    )



# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def classify_deals(raw_deals: list[dict]) -> list[dict]:
    """Classify a batch of RawDeals. Uses Flash-Lite (one batched request).

    Returns a list of classification dicts, one per input deal (same order).
    Falls back to keyword-based stub if Gemini is unavailable.
    """
    if not raw_deals:
        return []

    filings_json = json.dumps(
        [{"index": i, "title": d.get("title", ""), "filing_type": d.get("filing_type", ""),
          "source": d.get("source", ""), "region": d.get("region", "")}
         for i, d in enumerate(raw_deals)],
        indent=2,
    )
    prompt = CLASSIFY_BATCH.format(filings_json=filings_json)
    text = _call(_FLASH_LITE, "flash_lite", prompt)

    if text:
        parsed = _extract_json(text)
        if isinstance(parsed, list) and len(parsed) == len(raw_deals):
            return parsed

    logger.warning("Classification fell back to stub for %d deals", len(raw_deals))
    return [_stub_classification(i, d) for i, d in enumerate(raw_deals)]


def write_ma_report(
    deal: dict,
    primary_doc: str,
    secondary_sources: str,
    date_str: str,
    verified_facts: str = "",
) -> ReportData:
    """Write a full M&A report. Uses Flash (one request per report).

    Returns a ReportData. Falls back to stub if Gemini is unavailable.
    """
    prompt = MA_FULL_REPORT.format(
        primary_doc=primary_doc or "Primary document not available.",
        secondary_sources=secondary_sources or "No secondary sources available.",
        date=date_str,
        verified_facts=verified_facts,
    )
    text = _call(_FLASH, "flash", prompt)

    if text:
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            return _build_report_from_json(parsed, deal, date_str)

    logger.warning("write_ma_report fell back to stub for: %s", deal.get("title"))
    return _stub_ma_report(deal, date_str)


def write_ecm_report(
    deal: dict,
    primary_doc: str,
    secondary_sources: str,
    date_str: str,
    verified_facts: str = "",
) -> ReportData:
    """Write a full ECM report. Uses Flash (one request per report).

    Returns a ReportData. Falls back to stub if Gemini is unavailable.
    """
    prompt = ECM_FULL_REPORT.format(
        primary_doc=primary_doc or "Primary document not available.",
        secondary_sources=secondary_sources or "No secondary sources available.",
        date=date_str,
        verified_facts=verified_facts,
    )
    text = _call(_FLASH, "flash", prompt)

    if text:
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            return _build_report_from_json(parsed, deal, date_str, report_type="ecm",
                                           bib_key="8_bibliography")

    logger.warning("write_ecm_report fell back to stub for: %s", deal.get("title"))
    return _stub_ecm_report(deal, date_str)


def write_dcm_report(
    deal: dict,
    primary_doc: str,
    secondary_sources: str,
    date_str: str,
    verified_facts: str = "",
) -> ReportData:
    """Write a full DCM report. Uses Flash (one request per report).

    Returns a ReportData. Falls back to stub if Gemini is unavailable.
    """
    prompt = DCM_FULL_REPORT.format(
        primary_doc=primary_doc or "Primary document not available.",
        secondary_sources=secondary_sources or "No secondary sources available.",
        date=date_str,
        verified_facts=verified_facts,
    )
    text = _call(_FLASH, "flash", prompt)

    if text:
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            return _build_report_from_json(parsed, deal, date_str, report_type="dcm",
                                           bib_key="8_bibliography")

    logger.warning("write_dcm_report fell back to stub for: %s", deal.get("title"))
    return _stub_dcm_report(deal, date_str)


def _write_market_report(
    prompt_template: str,
    context: str,
    date_str: str,
    report_type: str,
    section_key: str,
    title_prefix: str,
    secondary_sources: str = "",
    verified_facts: str = "",
) -> ReportData:
    """Shared writer for all 5 daily market column reports. Uses Flash."""
    prompt = prompt_template.format(
        primary_doc=context or "Market data not available.",
        secondary_sources=secondary_sources,
        date=date_str,
        verified_facts=verified_facts,
    )
    text = _call(_FLASH, "flash", prompt)

    if text:
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            synthetic = {"region": "global", "company": title_prefix, "title": f"{title_prefix}: {date_str}"}
            return _build_report_from_json(parsed, synthetic, date_str,
                                           report_type=report_type, bib_key="2_bibliography")

    logger.warning("%s report fell back to stub for date: %s", report_type, date_str)
    return _stub_market_report(date_str, report_type, section_key, title_prefix)


def _stub_market_report(date_str: str, report_type: str, section_key: str, title_prefix: str) -> ReportData:
    title = f"{title_prefix}: {date_str}"
    return ReportData(
        slug=make_slug(title, "global", report_type, date_str),
        date=date_str,
        report_type=report_type,
        region="global",
        title=title,
        key_takeaways=["Stub report - Gemini unavailable or quota exceeded."],
        sections={section_key: "Not yet populated."},
        bibliography=[],
        metadata={"region": "global", "report_date": date_str},
        verification_log=[],
    )


def write_economy_report(
    context: str, secondary_sources: str, date_str: str, verified_facts: str = "",
) -> ReportData:
    """Write the daily Economy column report (macro + policy). Uses Flash."""
    return _write_market_report(
        ECONOMY_SECTION, context, date_str,
        report_type="economy", section_key="1_economy", title_prefix="Economy",
        secondary_sources=secondary_sources, verified_facts=verified_facts,
    )


def write_equities_report(
    context: str, date_str: str, verified_facts: str = "", secondary_sources: str = "",
) -> ReportData:
    """Write the daily Equities column report. Uses Flash."""
    return _write_market_report(
        EQUITIES_SECTION, context, date_str,
        report_type="equities", section_key="1_equities", title_prefix="Equities",
        secondary_sources=secondary_sources, verified_facts=verified_facts,
    )


def write_commodities_report(
    context: str, date_str: str, verified_facts: str = "", secondary_sources: str = "",
) -> ReportData:
    """Write the daily Commodities column report. Uses Flash."""
    return _write_market_report(
        COMMODITIES_SECTION, context, date_str,
        report_type="commodities", section_key="1_commodities", title_prefix="Commodities",
        secondary_sources=secondary_sources, verified_facts=verified_facts,
    )


def write_bonds_report(
    context: str, date_str: str, verified_facts: str = "", secondary_sources: str = "",
) -> ReportData:
    """Write the daily Bonds column report. Uses Flash."""
    return _write_market_report(
        BONDS_SECTION, context, date_str,
        report_type="bonds", section_key="1_bonds", title_prefix="Bonds",
        secondary_sources=secondary_sources, verified_facts=verified_facts,
    )


def write_currencies_report(
    context: str, date_str: str, verified_facts: str = "", secondary_sources: str = "",
) -> ReportData:
    """Write the daily Currencies column report. Uses Flash."""
    return _write_market_report(
        CURRENCIES_SECTION, context, date_str,
        report_type="currencies", section_key="1_currencies", title_prefix="Currencies",
        secondary_sources=secondary_sources, verified_facts=verified_facts,
    )


# ---------------------------------------------------------------------------
# Build ReportData from Gemini JSON response
# ---------------------------------------------------------------------------

def _build_report_from_json(
    data: dict,
    deal: dict,
    date_str: str,
    report_type: str = "ma_full",
    bib_key: str = "9_bibliography",
) -> ReportData:
    """Construct a ReportData from the JSON dict Gemini returns.

    report_type: "ma_full" | "ecm" | "dcm"
    bib_key: key under sections where bibliography was placed by the prompt
    """
    region = deal.get("region", data.get("metadata", {}).get("region", "US"))
    title = data.get("title", deal.get("title", f"{report_type.upper()} report"))
    sections = data.get("sections", {})

    # Bibliography lives inside sections in the prompt schema — pull it out
    bibliography = sections.pop(bib_key, []) or data.get("bibliography", [])
    if not isinstance(bibliography, list):
        bibliography = []

    metadata = data.get("metadata", {})
    metadata.setdefault("region", region)

    return ReportData(
        slug=make_slug(title, region, report_type, date_str),
        date=date_str,
        report_type=report_type,
        region=region,
        title=title,
        key_takeaways=data.get("key_takeaways", [])[:3],
        sections=sections,
        bibliography=bibliography,
        metadata=metadata,
        verification_log=data.get("verification_log", []),
    )
