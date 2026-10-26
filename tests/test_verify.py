"""Tests for app/verify.py — synthetic data, no network, no LLM."""

from __future__ import annotations

import pytest

from app.verify import (
    VerifyEntry,
    VerifyResult,
    empty_verify_result,
    infer_figure_type,
    source_authority,
    verify_claim_groups,
)


# ---------------------------------------------------------------------------
# source_authority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source,expected", [
    ("ASX announcement",           10),
    ("ASX Announcement",           10),   # case-insensitive
    ("8-K filing",                 10),
    ("Scheme booklet",             10),
    ("Independent Expert Report",  10),
    ("Rule 2.7 announcement",      10),
    ("RBA decision page",          10),
    ("Federal Reserve FOMC",       10),
    ("FRED data",                  10),
    ("GoogleNews:Reuters",          1),
    ("NewsAPI:AP News",             1),
    ("FMP price data",              1),
    ("yfinance",                    1),
    ("Company press release",       1),
])
def test_source_authority(source, expected):
    assert source_authority(source) == expected


# ---------------------------------------------------------------------------
# infer_figure_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("offer_price_aud",      "price"),
    ("target_close_aud",     "price"),
    ("deal_value_usd",       "price"),
    ("au_10y_yield",         "yield"),
    ("coupon_rate",          "yield"),
    ("spread_bps",           "yield"),
    ("audusd_rate",          "fx"),
    ("eur_usd",              "fx"),
    ("dxy_index",            "fx"),
    ("acquirer_name",        "text"),
    ("target_name",          "text"),
    ("deal_structure",       "text"),
    ("adviser_buy_side",     "text"),
    ("completion_date",      "text"),
])
def test_infer_figure_type(name, expected):
    assert infer_figure_type(name) == expected


# ---------------------------------------------------------------------------
# verify_claim_groups — verified (all agree)
# ---------------------------------------------------------------------------

def test_verified_two_sources_agree():
    groups = {"offer_price_aud": {"ASX announcement": 4.20, "FMP": 4.20}}
    result = verify_claim_groups(groups)
    assert result["verified_facts"]["offer_price_aud"] == 4.20
    log = result["verification_log"]
    assert len(log) == 1
    assert "Verified" in log[0]["status"]


def test_verified_chooses_primary_value():
    # FMP says 4.21, ASX says 4.20 — within tolerance → Verified, primary wins
    groups = {"offer_price_aud": {"ASX announcement": 4.20, "FMP": 4.21}}
    result = verify_claim_groups(groups)
    # ASX has authority 10, FMP has authority 1 → ASX value chosen
    assert result["verified_facts"]["offer_price_aud"] == 4.20


def test_verified_three_sources_all_agree():
    groups = {"target_close": {"ASX announcement": 3.12, "FMP": 3.12, "yfinance": 3.12}}
    result = verify_claim_groups(groups)
    assert result["verified_facts"]["target_close"] == 3.12
    assert "Verified" in result["verification_log"][0]["status"]


def test_verification_log_has_all_sources():
    groups = {"price": {"source_a": 10.0, "source_b": 10.0, "source_c": 10.0}}
    result = verify_claim_groups(groups)
    assert set(result["verification_log"][0]["sources"]) == {"source_a", "source_b", "source_c"}


# ---------------------------------------------------------------------------
# verify_claim_groups — single source
# ---------------------------------------------------------------------------

def test_single_source_returns_single_source_status():
    groups = {"premium_pct": {"ASX announcement": 34.6}}
    result = verify_claim_groups(groups)
    assert result["verified_facts"]["premium_pct"] == 34.6
    assert "Single source" in result["verification_log"][0]["status"]


# ---------------------------------------------------------------------------
# verify_claim_groups — resolved (conflict)
# ---------------------------------------------------------------------------

def test_resolved_two_sources_conflict():
    # FMP says 4.50%, RBA says 4.42% — 8bps apart, outside 5bps yield tolerance
    groups = {"au_10y_yield": {"RBA": 4.42, "FMP": 4.50}}
    result = verify_claim_groups(groups, figure_types={"au_10y_yield": "yield"})
    assert result["verified_facts"]["au_10y_yield"] is not None
    assert "Resolved" in result["verification_log"][0]["status"]
    assert result["verification_log"][0]["note"] != ""


def test_resolved_primary_wins_on_conflict():
    # Primary (ASX, authority 10) vs secondary (news, authority 1)
    groups = {"offer_price_aud": {"ASX announcement": 4.20, "GoogleNews:Reuters": 4.50}}
    result = verify_claim_groups(groups)
    # 4.20 vs 4.50 is way outside 1% price tolerance → Resolved
    # Primary (ASX) has authority 10, should win
    assert result["verified_facts"]["offer_price_aud"] == 4.20


def test_resolved_majority_wins():
    # 2 sources say 4.20, 1 says 5.00 — majority should win
    groups = {"price": {"source_a": 4.20, "source_b": 4.20, "source_c": 5.00}}
    result = verify_claim_groups(groups)
    assert result["verified_facts"]["price"] == 4.20
    assert "Resolved" in result["verification_log"][0]["status"]


# ---------------------------------------------------------------------------
# verify_claim_groups — text figures
# ---------------------------------------------------------------------------

def test_text_verified_exact_match():
    groups = {"acquirer_name": {"ASX announcement": "Acme Corp", "Reuters": "Acme Corp"}}
    result = verify_claim_groups(groups)
    assert result["verified_facts"]["acquirer_name"] == "Acme Corp"
    assert "Verified" in result["verification_log"][0]["status"]


def test_text_verified_case_insensitive():
    groups = {"deal_structure": {"ASX announcement": "Scheme of Arrangement", "FMP": "scheme of arrangement"}}
    result = verify_claim_groups(groups)
    assert "Verified" in result["verification_log"][0]["status"]


def test_text_resolved_on_conflict():
    groups = {
        "acquirer_name": {
            "ASX announcement": "Acme Corporation",
            "GoogleNews:Reuters": "ACME Corp Limited",
        }
    }
    result = verify_claim_groups(groups)
    # Conflict → Resolved; primary (ASX) wins
    assert result["verified_facts"]["acquirer_name"] == "Acme Corporation"
    assert "Resolved" in result["verification_log"][0]["status"]


# ---------------------------------------------------------------------------
# verify_claim_groups — explicit figure_types override
# ---------------------------------------------------------------------------

def test_explicit_figure_type_yield():
    # 4.42% vs 4.44% — within 5bps → Verified
    groups = {"bond_yield": {"RBA": 4.42, "yfinance": 4.44}}
    result = verify_claim_groups(groups, figure_types={"bond_yield": "yield"})
    assert "Verified" in result["verification_log"][0]["status"]


def test_explicit_figure_type_fx():
    # 0.6500 vs 0.6502 — within 0.5% FX tolerance → Verified
    groups = {"audusd": {"RBA": 0.6500, "FMP": 0.6502}}
    result = verify_claim_groups(groups, figure_types={"audusd": "fx"})
    assert "Verified" in result["verification_log"][0]["status"]


def test_explicit_figure_type_text():
    groups = {"status": {"source_a": "Announced", "source_b": "announced"}}
    result = verify_claim_groups(groups, figure_types={"status": "text"})
    assert "Verified" in result["verification_log"][0]["status"]


# ---------------------------------------------------------------------------
# verify_claim_groups — multiple figures at once
# ---------------------------------------------------------------------------

def test_multiple_figures_all_processed():
    groups = {
        "offer_price_aud": {"ASX announcement": 4.20, "FMP": 4.20},
        "premium_pct":     {"ASX announcement": 34.6},
        "acquirer_name":   {"ASX announcement": "Acme Corp", "Reuters": "Acme Corp"},
    }
    result = verify_claim_groups(groups)
    assert set(result["verified_facts"].keys()) == {
        "offer_price_aud", "premium_pct", "acquirer_name"
    }
    assert len(result["verification_log"]) == 3


def test_verification_log_value_is_string():
    """Log values are always stringified for display."""
    groups = {"price": {"source_a": 4.20}}
    result = verify_claim_groups(groups)
    assert isinstance(result["verification_log"][0]["value"], str)


# ---------------------------------------------------------------------------
# verify_claim_groups — edge cases
# ---------------------------------------------------------------------------

def test_empty_claim_groups_returns_empty():
    result = verify_claim_groups({})
    assert result["verified_facts"] == {}
    assert result["verification_log"] == []


def test_claim_group_with_no_values_skipped():
    groups = {"price": {}}
    result = verify_claim_groups(groups)
    assert result["verified_facts"] == {}


def test_none_values_skipped():
    groups = {"price": {"source_a": 4.20, "source_b": None}}
    result = verify_claim_groups(groups)
    # Only source_a contributes → single source
    assert result["verified_facts"]["price"] == 4.20
    assert "Single source" in result["verification_log"][0]["status"]


def test_non_numeric_value_in_numeric_group_falls_back_to_text():
    """If a 'price' figure has non-coercible values, falls back to text check."""
    groups = {"offer_price_aud": {"source_a": "not a number", "source_b": "not a number"}}
    result = verify_claim_groups(groups, figure_types={"offer_price_aud": "price"})
    # Should not raise; should produce a text-verified result
    assert "offer_price_aud" in result["verified_facts"]


# ---------------------------------------------------------------------------
# empty_verify_result
# ---------------------------------------------------------------------------

def test_empty_verify_result():
    result = empty_verify_result()
    assert result["verified_facts"] == {}
    assert result["verification_log"] == []


# ---------------------------------------------------------------------------
# VerifyResult type structure
# ---------------------------------------------------------------------------

def test_verify_result_has_required_keys():
    result = verify_claim_groups({"p": {"s": 1.0}})
    assert "verified_facts" in result
    assert "verification_log" in result


def test_verify_entry_has_required_keys():
    result = verify_claim_groups({"p": {"s": 1.0}})
    entry = result["verification_log"][0]
    assert "figure" in entry
    assert "value" in entry
    assert "sources" in entry
    assert "status" in entry
    assert "note" in entry
