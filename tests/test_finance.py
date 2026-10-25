"""Tests for app/finance.py — synthetic data only, no network.

Each test names the formula it covers and uses a worked example from
the glossary or CLAUDE.md so the numbers are self-documenting.
"""

import math
import pytest

from app.finance import (
    arb_spread_pct,
    break_fee_pct,
    dilution_pct,
    discount_pct,
    enterprise_value,
    ev_to_ebitda,
    ev_to_revenue,
    football_field_row,
    implied_equity_value,
    mixed_consideration,
    premium_pct,
    price_to_earnings,
    round_bps,
    round_pct,
    scrip_value,
    to_usd,
    vwap,
)


# ---------------------------------------------------------------------------
# premium_pct
# ---------------------------------------------------------------------------

def test_premium_basic():
    # offer A$4.10, undisturbed A$3.12 → (4.10−3.12)/3.12×100 = 31.41%
    result = premium_pct(4.10, 3.12)
    assert math.isclose(result, (4.10 - 3.12) / 3.12 * 100, rel_tol=1e-9)


def test_premium_zero_premium():
    # Offer equals reference → 0% premium
    assert premium_pct(5.00, 5.00) == 0.0


def test_premium_negative_offer_below_reference():
    # Offer below reference → negative premium (a discount in M&A terms)
    assert premium_pct(3.00, 4.00) < 0


def test_premium_zero_reference_raises():
    with pytest.raises(ValueError):
        premium_pct(4.10, 0)


def test_premium_negative_reference_raises():
    with pytest.raises(ValueError):
        premium_pct(4.10, -1.0)


# ---------------------------------------------------------------------------
# discount_pct
# ---------------------------------------------------------------------------

def test_discount_basic():
    # Last close A$1.00, placement A$0.90 → 10.0%
    assert math.isclose(discount_pct(1.00, 0.90), 10.0, rel_tol=1e-9)


def test_discount_zero_discount():
    assert discount_pct(1.00, 1.00) == 0.0


def test_discount_zero_reference_raises():
    with pytest.raises(ValueError):
        discount_pct(0, 0.90)


# ---------------------------------------------------------------------------
# implied_equity_value
# ---------------------------------------------------------------------------

def test_implied_equity_value_basic():
    # A$4.10 × 500m shares = A$2,050m
    assert math.isclose(implied_equity_value(4.10, 500_000_000), 2_050_000_000)


def test_implied_equity_value_zero_price_raises():
    with pytest.raises(ValueError):
        implied_equity_value(0, 500_000_000)


def test_implied_equity_value_zero_shares_raises():
    with pytest.raises(ValueError):
        implied_equity_value(4.10, 0)


# ---------------------------------------------------------------------------
# enterprise_value
# ---------------------------------------------------------------------------

def test_ev_net_debt_positive():
    # equity A$2,050m + net debt A$450m = EV A$2,500m
    assert enterprise_value(2_050, 450) == 2_500


def test_ev_net_cash():
    # Net cash (negative net debt) reduces EV below equity value
    assert enterprise_value(2_050, -200) == 1_850


# ---------------------------------------------------------------------------
# ev_to_ebitda
# ---------------------------------------------------------------------------

def test_ev_ebitda_basic():
    # EV A$2,500m / EBITDA A$250m = 10.0×
    assert math.isclose(ev_to_ebitda(2_500, 250), 10.0)


def test_ev_ebitda_zero_ebitda_raises():
    with pytest.raises(ValueError):
        ev_to_ebitda(2_500, 0)


def test_ev_ebitda_negative_ebitda_raises():
    with pytest.raises(ValueError):
        ev_to_ebitda(2_500, -50)


def test_ev_ebitda_negative_ev_raises():
    # Net-cash company where cash > equity value → negative EV → meaningless multiple
    with pytest.raises(ValueError):
        ev_to_ebitda(-100, 250)


# ---------------------------------------------------------------------------
# price_to_earnings
# ---------------------------------------------------------------------------

def test_pe_basic():
    # offer A$4.10 / EPS A$0.28 = 14.64×
    assert math.isclose(price_to_earnings(4.10, 0.28), 4.10 / 0.28, rel_tol=1e-9)


def test_pe_zero_eps_raises():
    with pytest.raises(ValueError):
        price_to_earnings(4.10, 0)


def test_pe_negative_eps_raises():
    # Loss-making company: P/E is not meaningful
    with pytest.raises(ValueError):
        price_to_earnings(4.10, -0.05)


# ---------------------------------------------------------------------------
# ev_to_revenue
# ---------------------------------------------------------------------------

def test_ev_revenue_basic():
    # EV US$500m / Revenue US$200m = 2.5×
    assert math.isclose(ev_to_revenue(500, 200), 2.5)


def test_ev_revenue_zero_raises():
    with pytest.raises(ValueError):
        ev_to_revenue(500, 0)


# ---------------------------------------------------------------------------
# break_fee_pct
# ---------------------------------------------------------------------------

def test_break_fee_pct_basic():
    # A$20.5m / A$2,050m = 1.0%
    assert math.isclose(break_fee_pct(20.5, 2_050), 1.0, rel_tol=1e-9)


def test_break_fee_pct_zero_equity_raises():
    with pytest.raises(ValueError):
        break_fee_pct(20.5, 0)


# ---------------------------------------------------------------------------
# arb_spread_pct
# ---------------------------------------------------------------------------

def test_arb_spread_basic():
    # target at A$4.02, offer A$4.10 → (4.10−4.02)/4.10×100 ≈ 1.95%
    expected = (4.10 - 4.02) / 4.10 * 100
    assert math.isclose(arb_spread_pct(4.02, 4.10), expected, rel_tol=1e-9)


def test_arb_spread_at_offer():
    # Trading exactly at offer → 0% spread
    assert arb_spread_pct(4.10, 4.10) == 0.0


def test_arb_spread_zero_offer_raises():
    with pytest.raises(ValueError):
        arb_spread_pct(4.02, 0)


def test_arb_spread_target_above_offer():
    # Target trades above offer → negative spread (counter-bid speculation)
    result = arb_spread_pct(4.20, 4.10)
    assert result < 0
    assert math.isclose(result, (4.10 - 4.20) / 4.10 * 100, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# vwap
# ---------------------------------------------------------------------------

def test_vwap_basic():
    # closes [1.00, 1.02, 0.99], volumes [1_000_000, 800_000, 1_200_000]
    closes = [1.00, 1.02, 0.99]
    volumes = [1_000_000, 800_000, 1_200_000]
    expected = (1.00 * 1_000_000 + 1.02 * 800_000 + 0.99 * 1_200_000) / 3_000_000
    assert math.isclose(vwap(closes, volumes), expected, rel_tol=1e-9)


def test_vwap_single_day():
    assert vwap([2.50], [500_000]) == 2.50


def test_vwap_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        vwap([1.00, 1.02], [1_000_000])


def test_vwap_empty_raises():
    with pytest.raises(ValueError):
        vwap([], [])


def test_vwap_zero_volume_raises():
    with pytest.raises(ValueError):
        vwap([1.00], [0])


def test_vwap_equal_volumes_is_simple_average():
    # Equal volumes → VWAP degenerates to a simple average
    closes = [1.00, 1.02, 0.99]
    expected = sum(closes) / len(closes)
    assert math.isclose(vwap(closes, [1, 1, 1]), expected, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# dilution_pct
# ---------------------------------------------------------------------------

def test_dilution_basic():
    # 50m new / 500m existing = 10.0%
    assert math.isclose(dilution_pct(50_000_000, 500_000_000), 10.0)


def test_dilution_zero_existing_raises():
    with pytest.raises(ValueError):
        dilution_pct(50_000_000, 0)


def test_dilution_zero_new_shares():
    # No new shares issued → 0% dilution
    assert dilution_pct(0, 500_000_000) == 0.0


# ---------------------------------------------------------------------------
# scrip_value
# ---------------------------------------------------------------------------

def test_scrip_value_basic():
    # ratio 0.5 × acquirer A$10.00 = A$5.00
    assert math.isclose(scrip_value(0.5, 10.00), 5.00)


def test_scrip_value_zero_ratio_raises():
    with pytest.raises(ValueError):
        scrip_value(0, 10.00)


def test_scrip_value_zero_price_raises():
    with pytest.raises(ValueError):
        scrip_value(0.5, 0)


# ---------------------------------------------------------------------------
# mixed_consideration
# ---------------------------------------------------------------------------

def test_mixed_consideration_cash_and_scrip():
    # A$1.50 cash + 0.25 × A$10.00 acquirer = A$4.00 per target share
    assert math.isclose(mixed_consideration(1.50, 0.25, 10.00), 4.00)


def test_mixed_consideration_pure_cash():
    # scrip_ratio=0 → just the cash component
    assert mixed_consideration(4.10, 0, 10.00) == 4.10


def test_mixed_consideration_pure_scrip():
    # cash=0 → just scrip value
    assert math.isclose(mixed_consideration(0, 0.5, 10.00), 5.00)


def test_mixed_consideration_negative_cash_raises():
    with pytest.raises(ValueError):
        mixed_consideration(-1.00, 0.25, 10.00)


def test_mixed_consideration_negative_ratio_raises():
    with pytest.raises(ValueError):
        mixed_consideration(1.50, -0.25, 10.00)


# ---------------------------------------------------------------------------
# to_usd (currency conversion for deal ranking)
# ---------------------------------------------------------------------------

def test_to_usd_aud():
    # A$2,050m at AUD/USD 0.65 → US$1,332.5m
    assert math.isclose(to_usd(2_050, 0.65), 1_332.5)


def test_to_usd_already_usd():
    # USD amount with fx_rate=1.0 is unchanged
    assert to_usd(500, 1.0) == 500.0


def test_to_usd_zero_fx_raises():
    with pytest.raises(ValueError):
        to_usd(2_050, 0)


def test_to_usd_negative_amount_raises():
    # Negative deal value indicates a data error upstream
    with pytest.raises(ValueError):
        to_usd(-500, 0.65)


# ---------------------------------------------------------------------------
# football_field_row
# ---------------------------------------------------------------------------

def test_football_field_within():
    row = football_field_row("DCF", 3.50, 4.20, 4.10)
    assert row["offer_position"] == "within"
    assert row["method"] == "DCF"
    assert row["low"] == 3.50
    assert row["high"] == 4.20


def test_football_field_above():
    row = football_field_row("Trading comps", 3.00, 3.80, 4.10)
    assert row["offer_position"] == "above"


def test_football_field_below():
    row = football_field_row("NAV", 4.50, 5.00, 4.10)
    assert row["offer_position"] == "below"


def test_football_field_offer_equals_low():
    row = football_field_row("LBO", 4.10, 4.50, 4.10)
    assert row["offer_position"] == "within"


def test_football_field_offer_equals_high():
    row = football_field_row("Precedents", 3.50, 4.10, 4.10)
    assert row["offer_position"] == "within"


def test_football_field_low_gt_high_raises():
    with pytest.raises(ValueError):
        football_field_row("DCF", 5.00, 3.00, 4.10)


# ---------------------------------------------------------------------------
# round_pct and round_bps
# ---------------------------------------------------------------------------

def test_round_pct_default_1dp():
    assert round_pct(31.4146) == 31.4


def test_round_pct_custom_dp():
    assert round_pct(31.4146, dp=2) == 31.41


def test_round_bps_basic():
    # 0.25% → 25 bps
    assert round_bps(0.25) == 25


def test_round_bps_rounding():
    # 0.255% → 26 bps (rounds to nearest)
    assert round_bps(0.255) == 26


def test_round_bps_negative():
    # Rate cut of 0.25% → −25 bps
    assert round_bps(-0.25) == -25
