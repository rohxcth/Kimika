"""Kimika verify — Stage 3 of the report pipeline (... → Verify → Style → Synthesise).

Takes structured claim groups (figure → {source: value} mappings prepared by the
pipeline), cross-references them using crosscheck.py, and returns:
  - verified_facts: dict mapping figure name → resolved value (passed to the LLM)
  - verification_log: list of dicts suitable for report.verification_log

The LLM never sees raw conflicts. It receives only the resolved value for each figure.

Usage in the pipeline:
    claim_groups = {
        "offer_price_aud":   {"ASX announcement": 4.20, "GoogleNews:Reuters": 4.20},
        "target_close_aud":  {"FMP": 3.12, "yfinance": 3.12},
        "premium_pct":       {"ASX announcement": 34.6},
        "acquirer":          {"ASX announcement": "Acme Corp", "Reuters": "Acme Corp"},
    }
    result = verify_claim_groups(claim_groups)
    # result["verified_facts"]   → {"offer_price_aud": 4.20, ...}
    # result["verification_log"] → [{"figure": ..., "value": ..., ...}, ...]

Figure types (controls tolerance):
    "price"  — equity/commodity price (1% tolerance)
    "yield"  — bond yield in % (5bps tolerance)
    "fx"     — foreign exchange rate (0.5% tolerance)
    "text"   — non-numeric (exact string match)
    Inferred from figure name if not provided; default "price".
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from app.crosscheck import (
    SourceReading,
    VerificationStatus,
    check_numeric,
    check_text,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

class VerifyEntry(TypedDict):
    figure:  str
    value:   str        # stringified for display in the verification toggle
    sources: list[str]
    status:  str        # the .value of VerificationStatus
    note:    str


class VerifyResult(TypedDict):
    verified_facts:    dict[str, Any]   # figure → resolved value, passed to LLM
    verification_log:  list[VerifyEntry]


# ---------------------------------------------------------------------------
# Authority inference
# ---------------------------------------------------------------------------

# Source keywords that indicate a primary document (authority = 10)
_PRIMARY_KEYWORDS = {
    "asx announcement", "8-k", "defm14a", "prem14a", "s-4", "sc to-t",
    "scheme booklet", "sid", "independent expert", "ier", "fairness opinion",
    "rule 2.7", "rule 2.4", "rns", "prospectus", "annual report",
    "rba", "federal reserve", "fomc", "abs", "bls", "bea", "fred",
    "central bank", "treasury", "imf", "oecd", "10-k",
}


def source_authority(source_name: str) -> int:
    """Return authority score for a source name (primary=10, secondary=1).

    Primary sources outrank secondary per CLAUDE.md verification rules.
    Example: "ASX announcement" → 10; "GoogleNews:Reuters" → 1.
    """
    s = source_name.lower()
    return 10 if any(kw in s for kw in _PRIMARY_KEYWORDS) else 1


# ---------------------------------------------------------------------------
# Figure type inference
# ---------------------------------------------------------------------------

# Suffixes/patterns that unambiguously identify text fields (not numeric)
_TEXT_SUFFIXES  = ("_name", "_type", "_status", "_structure", "_description",
                   "_region", "_date", "_condition")
_TEXT_CONTAINS  = {"adviser"}   # "adviser" never refers to a number

# Specific FX pair patterns — avoid single-currency suffixes like "aud", "usd"
# which also appear in AUD-denominated price fields like "offer_price_aud"
_FX_PATTERNS    = (
    "audusd", "eurusd", "gbpusd", "usdjpy", "usdcnh", "aud_usd", "eur_usd",
    "gbp_usd", "usd_jpy", "fx_rate", "exchange_rate", "dxy",
)

# Yield patterns — specific to debt instruments
_YIELD_PATTERNS = ("_yield", "yield_", "coupon_", "_bps", "spread_bps", "tenor_")


def infer_figure_type(figure_name: str) -> str:
    """Infer the verification type from a figure name.

    Returns "text" | "fx" | "yield" | "price" (default).
    Checked in that priority order so more-specific patterns win.
    Called when figure_types dict is not provided by the caller.
    """
    fn = figure_name.lower()
    # Text: unambiguous descriptive-field suffixes or known text containers
    if any(fn.endswith(s) for s in _TEXT_SUFFIXES) or any(t in fn for t in _TEXT_CONTAINS):
        return "text"
    # FX: specific currency-pair strings (not single-currency suffixes)
    if any(p in fn for p in _FX_PATTERNS):
        return "fx"
    # Yield: debt-instrument-specific patterns
    if any(p in fn for p in _YIELD_PATTERNS):
        return "yield"
    return "price"


# ---------------------------------------------------------------------------
# Core verification function
# ---------------------------------------------------------------------------

def verify_claim_groups(
    claim_groups: dict[str, dict[str, Any]],
    figure_types: dict[str, str] | None = None,
) -> VerifyResult:
    """Cross-reference structured claim groups and return resolved facts + log.

    Args:
        claim_groups:  Dict of figure_name → {source_name: value}.
                       Values may be float (numeric) or str (text).
                       Example:
                         {"offer_price_aud": {"ASX announcement": 4.20, "FMP": 4.21}}
        figure_types:  Optional dict of figure_name → "price"|"yield"|"fx"|"text".
                       Any figure not listed is inferred from its name.

    Returns a VerifyResult with:
        verified_facts:   {figure_name: resolved_value} — safe to pass to LLM
        verification_log: list of VerifyEntry dicts for the report's toggle
    """
    verified_facts: dict[str, Any] = {}
    verification_log: list[VerifyEntry] = []
    ftypes = figure_types or {}

    for figure_name, source_values in claim_groups.items():
        if not source_values:
            logger.debug("verify: skipping empty claim group %r", figure_name)
            continue

        # Build SourceReading list
        readings = [
            SourceReading(
                source_name=src,
                value=val,
                authority=source_authority(src),
            )
            for src, val in source_values.items()
            if val is not None and val != ""
        ]
        if not readings:
            continue

        # Determine figure type
        ftype = ftypes.get(figure_name) or infer_figure_type(figure_name)

        try:
            if ftype == "text":
                result = check_text(figure_name, readings)
            else:
                # Coerce values to float for numeric checks
                numeric_readings = []
                for r in readings:
                    try:
                        numeric_readings.append(
                            SourceReading(r.source_name, float(r.value), r.authority)
                        )
                    except (ValueError, TypeError):
                        logger.debug(
                            "verify: cannot coerce %r=%r to float for %r — treating as text",
                            r.source_name, r.value, figure_name,
                        )
                if not numeric_readings:
                    result = check_text(figure_name, readings)
                else:
                    result = check_numeric(figure_name, numeric_readings, ftype)
        except Exception as exc:
            logger.warning("verify: error checking %r: %s", figure_name, exc)
            continue

        verified_facts[figure_name] = result.chosen_value
        verification_log.append(VerifyEntry(
            figure=result.figure_name,
            value=str(result.chosen_value),
            sources=result.sources_used,
            status=result.status.value,
            note=result.note,
        ))

        if result.status == VerificationStatus.RESOLVED:
            logger.info(
                "verify: RESOLVED %r → %s (%s)",
                figure_name, result.chosen_value, result.note[:80],
            )

    logger.info(
        "verify: %d figures checked — %d verified, %d resolved, %d single-source",
        len(verification_log),
        sum(1 for e in verification_log if "Verified" in e["status"] and "Resolved" not in e["status"]),
        sum(1 for e in verification_log if "Resolved" in e["status"]),
        sum(1 for e in verification_log if "Single source" in e["status"]),
    )
    return VerifyResult(
        verified_facts=verified_facts,
        verification_log=verification_log,
    )


# ---------------------------------------------------------------------------
# Convenience: empty result (for reports with no structured figures yet)
# ---------------------------------------------------------------------------

def empty_verify_result() -> VerifyResult:
    """Return an empty VerifyResult for reports that have no claim groups."""
    return VerifyResult(verified_facts={}, verification_log=[])
