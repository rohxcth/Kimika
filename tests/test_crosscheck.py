"""Tests for app/crosscheck.py — synthetic data only, no network.

Covers every case in the spec:
  - Agreement within tolerance → ✅ Verified
  - Conflict resolved by third source (majority) → ✅ Resolved
  - Conflict resolved by authority (no majority) → ✅ Resolved
  - Single source → ❓ Single source
  - Recomputed helper → 🔁 Recomputed
  - Text (non-numeric) figures
  - Tolerance boundaries for price, yield, FX
"""

import pytest

from app.crosscheck import (
    SourceReading,
    VerificationResult,
    VerificationStatus,
    check_numeric,
    check_text,
    recomputed,
    _within_fx_tolerance,
    _within_price_tolerance,
    _within_yield_tolerance,
)


# ---------------------------------------------------------------------------
# Single source
# ---------------------------------------------------------------------------

def test_single_source_returns_single_source_status():
    readings = [SourceReading("FMP", 4.10)]
    result = check_numeric("offer price", readings)
    assert result.status == VerificationStatus.SINGLE_SOURCE
    assert result.chosen_value == 4.10
    assert result.sources_used == ["FMP"]


def test_single_source_note_present():
    readings = [SourceReading("RBA", 4.42)]
    result = check_numeric("AU 10y yield", readings, figure_type="yield")
    assert "one source" in result.note.lower()


def test_no_readings_raises():
    with pytest.raises(ValueError):
        check_numeric("price", [])


# ---------------------------------------------------------------------------
# ✅ Verified: all sources agree
# ---------------------------------------------------------------------------

def test_two_sources_agree_verified():
    # FMP 4.10, yfinance 4.10 — exact match
    readings = [SourceReading("FMP", 4.10), SourceReading("yfinance", 4.10)]
    result = check_numeric("offer price", readings)
    assert result.status == VerificationStatus.VERIFIED
    assert result.chosen_value == 4.10


def test_three_sources_agree_verified():
    readings = [
        SourceReading("FMP", 100.0),
        SourceReading("yfinance", 100.5),   # within 1% of 100
        SourceReading("ASX", 100.2),
    ]
    result = check_numeric("share price", readings)
    assert result.status == VerificationStatus.VERIFIED


def test_verified_picks_highest_authority():
    # Both within tolerance; ASX announcement (authority=10) should win
    readings = [
        SourceReading("FMP", 3.12, authority=1),
        SourceReading("ASX announcement", 3.12, authority=10),
    ]
    result = check_numeric("undisturbed close", readings)
    assert result.status == VerificationStatus.VERIFIED
    assert result.sources_used == ["FMP", "ASX announcement"]


# ---------------------------------------------------------------------------
# Tolerance boundaries: price (1%)
# ---------------------------------------------------------------------------

def test_price_within_tolerance():
    # 100 vs 100.99 → diff = 0.0099 < 0.01 → agree
    assert _within_price_tolerance(100.0, 100.99) is True


def test_price_at_tolerance_boundary():
    # 100 vs 101 → diff = 0.01 = 0.01 → agree (≤)
    assert _within_price_tolerance(100.0, 101.0) is True


def test_price_outside_tolerance():
    # 100 vs 101.5 → diff = 0.015 > 0.01 → disagree
    assert _within_price_tolerance(100.0, 101.5) is False


def test_price_tolerance_conflict_detected():
    readings = [
        SourceReading("FMP", 100.0),
        SourceReading("yfinance", 102.0),  # 2% apart → conflict
    ]
    result = check_numeric("price", readings)
    assert result.status != VerificationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Tolerance boundaries: yield (5 bps)
# ---------------------------------------------------------------------------

def test_yield_within_tolerance():
    # 4.42% vs 4.46% → 4 bps → agree
    assert _within_yield_tolerance(4.42, 4.46) is True


def test_yield_at_boundary():
    # 4.42% vs 4.47% → 5 bps → agree (≤)
    assert _within_yield_tolerance(4.42, 4.47) is True


def test_yield_outside_tolerance():
    # 4.42% vs 4.49% → 7 bps → disagree
    assert _within_yield_tolerance(4.42, 4.49) is False


def test_yield_conflict_resolved():
    # RBA and yfinance agree (4 bps); FMP differs by 7 bps from RBA
    # RBA has highest authority → should be chosen
    readings = [
        SourceReading("FMP", 4.49, authority=1),
        SourceReading("RBA", 4.42, authority=10),
        SourceReading("yfinance", 4.44, authority=1),
    ]
    result = check_numeric("AU 10y yield", readings, figure_type="yield")
    # RBA and yfinance agree (2 bps); FMP disagrees with RBA (7 bps)
    assert result.status == VerificationStatus.RESOLVED
    # Majority cluster is RBA+yfinance; highest authority in that cluster is RBA
    assert result.chosen_value == 4.42
    assert "RBA" in result.note


# ---------------------------------------------------------------------------
# Tolerance boundaries: FX (0.5%)
# ---------------------------------------------------------------------------

def test_fx_within_tolerance():
    # 0.650 vs 0.653 → 0.46% → agree
    assert _within_fx_tolerance(0.650, 0.653) is True


def test_fx_outside_tolerance():
    # 0.650 vs 0.657 → 1.08% → disagree
    assert _within_fx_tolerance(0.650, 0.657) is False


# ---------------------------------------------------------------------------
# ✅ Resolved: conflict with third-source majority
# ---------------------------------------------------------------------------

def test_conflict_resolved_by_majority():
    # Two sources say 4.10; one says 3.90 (>1% away) → majority wins
    readings = [
        SourceReading("FMP", 4.10, authority=1),
        SourceReading("yfinance", 4.10, authority=1),
        SourceReading("outlier_feed", 3.90, authority=1),
    ]
    result = check_numeric("target price", readings)
    assert result.status == VerificationStatus.RESOLVED
    assert result.chosen_value == 4.10
    assert "majority" in result.note.lower()


def test_conflict_resolved_note_lists_all_values():
    readings = [
        SourceReading("FMP", 4.10, authority=1),
        SourceReading("yfinance", 4.10, authority=1),
        SourceReading("outlier", 3.90, authority=1),
    ]
    result = check_numeric("price", readings)
    # Note must mention every source's value so the record is auditable
    assert "FMP" in result.note
    assert "yfinance" in result.note
    assert "outlier" in result.note


# ---------------------------------------------------------------------------
# ✅ Resolved: conflict resolved by authority (no majority)
# ---------------------------------------------------------------------------

def test_conflict_resolved_by_authority_no_majority():
    # Two sources conflict; authority breaks the tie
    readings = [
        SourceReading("news_wire", 3.90, authority=1),
        SourceReading("ASX announcement", 4.10, authority=10),
    ]
    result = check_numeric("deal price", readings)
    assert result.status == VerificationStatus.RESOLVED
    assert result.chosen_value == 4.10
    assert "authority" in result.note.lower()


def test_conflict_resolved_sources_recorded():
    readings = [
        SourceReading("news_wire", 3.90, authority=1),
        SourceReading("ASX announcement", 4.10, authority=10),
    ]
    result = check_numeric("deal price", readings)
    assert set(result.sources_used) == {"news_wire", "ASX announcement"}


# ---------------------------------------------------------------------------
# Text (non-numeric) figures
# ---------------------------------------------------------------------------

def test_text_two_agree():
    readings = [
        SourceReading("ASX announcement", "Scheme of arrangement"),
        SourceReading("news wire", "scheme of arrangement"),  # case-insensitive
    ]
    result = check_text("deal structure", readings)
    assert result.status == VerificationStatus.VERIFIED


def test_text_single_source():
    readings = [SourceReading("SID", "cash consideration")]
    result = check_text("consideration type", readings)
    assert result.status == VerificationStatus.SINGLE_SOURCE


def test_text_conflict_resolved_by_authority():
    readings = [
        SourceReading("news_summary", "takeover bid", authority=1),
        SourceReading("ASX_announcement", "scheme of arrangement", authority=10),
    ]
    result = check_text("deal structure", readings)
    assert result.status == VerificationStatus.RESOLVED
    assert result.chosen_value == "scheme of arrangement"


def test_text_no_readings_raises():
    with pytest.raises(ValueError):
        check_text("figure", [])


# ---------------------------------------------------------------------------
# 🔁 Recomputed
# ---------------------------------------------------------------------------

def test_recomputed_status():
    result = recomputed(
        "implied equity value",
        value=2_050_000_000,
        sources_used=["finance.py"],
        note="offer_price × shares_on_issue",
    )
    assert result.status == VerificationStatus.RECOMPUTED
    assert result.chosen_value == 2_050_000_000


def test_recomputed_to_dict():
    result = recomputed("EV/EBITDA", 10.0, ["finance.py"])
    d = result.to_dict()
    assert d["status"] == "🔁 Recomputed"
    assert d["value"] == 10.0


# ---------------------------------------------------------------------------
# to_dict serialisation
# ---------------------------------------------------------------------------

def test_to_dict_verified():
    readings = [SourceReading("FMP", 4.10), SourceReading("yfinance", 4.10)]
    result = check_numeric("price", readings)
    d = result.to_dict()
    assert d["status"] == "✅ Verified"
    assert d["figure"] == "price"
    assert d["value"] == 4.10
    assert isinstance(d["sources"], list)


def test_to_dict_single_source():
    result = check_numeric("price", [SourceReading("FMP", 4.10)])
    d = result.to_dict()
    assert d["status"] == "❓ Single source"
