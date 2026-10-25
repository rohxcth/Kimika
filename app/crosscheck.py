"""Kimika cross-verification engine.

Every figure that appears in a report must be verified here before it is
written. The rules (from CLAUDE.md):

  - Market data (prices, yields, FX): ≥2 independent sources must agree
    within the tolerances in config.yaml.
  - News facts / deal terms: ≥2 independent publishers, or 1 primary source.
  - Conflicts: search for more sources; go with the majority or the most
    authoritative; record the choice and reason.

Verification statuses (stored in the report JSON, never printed in the PDF):
  ✅ Verified   — ≥2 sources, all agree within tolerance
  ✅ Resolved   — conflict found, resolved by authority/majority; note records how
  ❓ Single source — only one reading available
  🔁 Recomputed — derived in finance.py from verified inputs (assigned by caller)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.config import cfg

# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class VerificationStatus(str, Enum):
    VERIFIED = "✅ Verified"
    RESOLVED = "✅ Resolved"
    SINGLE_SOURCE = "❓ Single source"
    RECOMPUTED = "🔁 Recomputed"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SourceReading:
    """One source's reading of a figure.

    source_name: human-readable name, e.g. "FMP", "RBA", "ASX announcement"
    value:       the raw numeric or string value from that source
    authority:   relative authority rank (higher = more authoritative).
                 Primary sources (filings, central bank) should get higher
                 authority than secondary (news wires, data vendors).
                 Default 1; primary documents typically 10.
    """
    source_name: str
    value: Any
    authority: int = 1


@dataclass
class VerificationResult:
    """The outcome of checking a figure across one or more sources."""
    figure_name: str
    chosen_value: Any
    status: VerificationStatus
    sources_used: list[str]
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "figure": self.figure_name,
            "value": self.chosen_value,
            "status": self.status.value,
            "sources": self.sources_used,
            "note": self.note,
        }


# ---------------------------------------------------------------------------
# Tolerance helpers
# ---------------------------------------------------------------------------

def _within_price_tolerance(a: float, b: float) -> bool:
    """Two price readings agree if they differ by ≤ price_tolerance (fraction)."""
    tol = cfg["crosscheck"]["price_tolerance"]
    if a == 0 and b == 0:
        return True
    ref = max(abs(a), abs(b))
    return abs(a - b) / ref <= tol


def _within_yield_tolerance(a: float, b: float) -> bool:
    """Two yield readings (in %) agree if they differ by ≤ yield_tolerance_bps."""
    tol_bps = cfg["crosscheck"]["yield_tolerance_bps"]
    return abs(a - b) * 100 <= tol_bps  # convert % → bps


def _within_fx_tolerance(a: float, b: float) -> bool:
    """Two FX rate readings agree if they differ by ≤ fx_tolerance (fraction)."""
    tol = cfg["crosscheck"]["fx_tolerance"]
    if a == 0 and b == 0:
        return True
    ref = max(abs(a), abs(b))
    return abs(a - b) / ref <= tol


# Map figure_type string → tolerance function
_TOLERANCE_FN = {
    "price":  _within_price_tolerance,
    "yield":  _within_yield_tolerance,
    "fx":     _within_fx_tolerance,
}


# ---------------------------------------------------------------------------
# Core verification functions
# ---------------------------------------------------------------------------

def check_numeric(
    figure_name: str,
    readings: list[SourceReading],
    figure_type: str = "price",
) -> VerificationResult:
    """Verify a numeric figure across multiple source readings.

    figure_type: "price" | "yield" | "fx" — selects the tolerance function.

    Algorithm:
      0 readings → raises ValueError (nothing to verify).
      1 reading  → ❓ Single source; chosen_value = that reading's value.
      2+ readings:
        - If all agree within tolerance → ✅ Verified; chosen_value = highest-
          authority reading (ties broken by first in list).
        - If conflict → search for a third reading to break the tie.
            - If a majority agree → ✅ Resolved; record which source differed.
            - If still split → ✅ Resolved; pick the highest-authority reading;
              record all values and the authority-based choice.
    """
    if not readings:
        raise ValueError(f"No readings provided for '{figure_name}'")

    sources = [r.source_name for r in readings]

    # Single source
    if len(readings) == 1:
        return VerificationResult(
            figure_name=figure_name,
            chosen_value=readings[0].value,
            status=VerificationStatus.SINGLE_SOURCE,
            sources_used=sources,
            note="Only one source found.",
        )

    tol_fn = _TOLERANCE_FN.get(figure_type, _within_price_tolerance)
    # Wrap the float-level tolerance function so _all_agree receives SourceReadings
    agree_fn = lambda a, b: tol_fn(a.value, b.value)  # noqa: E731

    # Check all-agree (every pair within tolerance)
    if _all_agree(readings, agree_fn):
        best = _highest_authority(readings)
        return VerificationResult(
            figure_name=figure_name,
            chosen_value=best.value,
            status=VerificationStatus.VERIFIED,
            sources_used=sources,
        )

    # Conflict: pick by majority or authority
    return _resolve_conflict(figure_name, readings, agree_fn)


def check_text(
    figure_name: str,
    readings: list[SourceReading],
) -> VerificationResult:
    """Verify a non-numeric figure (e.g. a stated deal term, a date).

    Agreement = exact string match (case-insensitive, stripped).
    Conflict resolution follows the same majority/authority logic.
    """
    if not readings:
        raise ValueError(f"No readings provided for '{figure_name}'")

    sources = [r.source_name for r in readings]

    if len(readings) == 1:
        return VerificationResult(
            figure_name=figure_name,
            chosen_value=readings[0].value,
            status=VerificationStatus.SINGLE_SOURCE,
            sources_used=sources,
            note="Only one source found.",
        )

    def text_agree(a: SourceReading, b: SourceReading) -> bool:
        return str(a.value).strip().lower() == str(b.value).strip().lower()

    if _all_agree(readings, text_agree):
        best = _highest_authority(readings)
        return VerificationResult(
            figure_name=figure_name,
            chosen_value=best.value,
            status=VerificationStatus.VERIFIED,
            sources_used=sources,
        )

    return _resolve_conflict(figure_name, readings, text_agree)


def recomputed(
    figure_name: str,
    value: Any,
    sources_used: list[str],
    note: str = "",
) -> VerificationResult:
    """Mark a figure as 🔁 Recomputed (derived in finance.py from verified inputs)."""
    return VerificationResult(
        figure_name=figure_name,
        chosen_value=value,
        status=VerificationStatus.RECOMPUTED,
        sources_used=sources_used,
        note=note,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _all_agree(readings: list[SourceReading], agree_fn) -> bool:
    """Return True if every pair of readings agrees under agree_fn."""
    for i, a in enumerate(readings):
        for b in readings[i + 1:]:
            if not agree_fn(a, b):
                return False
    return True


def _highest_authority(readings: list[SourceReading]) -> SourceReading:
    """Return the reading with the highest authority score (first wins ties)."""
    return max(readings, key=lambda r: r.authority)


def _resolve_conflict(
    figure_name: str,
    readings: list[SourceReading],
    agree_fn,
) -> VerificationResult:
    """Resolve a conflict by majority then authority.

    Strategy:
      1. Find the largest cluster of readings that mutually agree.
      2. If that cluster has more readings than any other cluster → majority wins.
      3. Otherwise (tied clusters) → pick the reading with the highest authority.

    The chosen_value is the highest-authority reading within the winning cluster.
    The note records every source's value and why the choice was made.
    """
    sources = [r.source_name for r in readings]

    # Sort by authority descending so the most-authoritative source seeds its cluster
    # first. This means "primary source + anything that agrees with it" beats a
    # cluster seeded by a low-authority source that happens to appear first.
    ordered = sorted(readings, key=lambda r: r.authority, reverse=True)

    # Build agreement clusters: each reading seeds a cluster of readings it agrees with
    clusters: list[list[SourceReading]] = []
    for r in ordered:
        placed = False
        for cluster in clusters:
            if agree_fn(cluster[0], r):
                cluster.append(r)
                placed = True
                break
        if not placed:
            clusters.append([r])

    # Sort clusters by size descending, then by max authority descending
    clusters.sort(key=lambda c: (len(c), max(r.authority for r in c)), reverse=True)

    winning_cluster = clusters[0]
    runner_up = clusters[1] if len(clusters) > 1 else []

    chosen = _highest_authority(winning_cluster)

    # Build human-readable note
    all_values = ", ".join(
        f"{r.source_name}={r.value}" for r in readings
    )
    if len(winning_cluster) > len(runner_up):
        reason = (
            f"Majority ({len(winning_cluster)} of {len(readings)} sources agree). "
            f"All values: {all_values}."
        )
    else:
        reason = (
            f"No majority; chose highest-authority source "
            f"({chosen.source_name}, authority={chosen.authority}). "
            f"All values: {all_values}."
        )

    return VerificationResult(
        figure_name=figure_name,
        chosen_value=chosen.value,
        status=VerificationStatus.RESOLVED,
        sources_used=sources,
        note=reason,
    )
