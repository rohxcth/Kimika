"""Kimika finance calculations.

All numbers used in reports are computed here, never by the LLM.
Each function documents its formula and the glossary term it implements.

Currency is always explicit in callers (A$, US$, £). These functions
work on plain floats; the caller is responsible for keeping currencies
consistent before passing values in.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# M&A: premium / discount
# ---------------------------------------------------------------------------

def premium_pct(offer: float, reference: float) -> float:
    """Premium of an offer over a reference price, in percent.

    Formula: (offer − reference) / reference × 100
    Glossary: "Premium" (M&A section)

    Example: offer A$4.10, reference (undisturbed close) A$3.12
             → (4.10 − 3.12) / 3.12 × 100 = 31.4%
    """
    if reference <= 0:
        raise ValueError(f"reference price must be > 0, got {reference}")
    return (offer - reference) / reference * 100


def discount_pct(reference: float, offer: float) -> float:
    """Discount of an offer below a reference price, in percent.

    Formula: (reference − offer) / reference × 100
    Glossary: "Discount" (ECM section)

    Example: last close A$1.00, placement price A$0.90
             → (1.00 − 0.90) / 1.00 × 100 = 10.0%
    """
    if reference <= 0:
        raise ValueError(f"reference price must be > 0, got {reference}")
    return (reference - offer) / reference * 100


# ---------------------------------------------------------------------------
# M&A: implied values
# ---------------------------------------------------------------------------

def implied_equity_value(offer_price: float, shares_on_issue: float) -> float:
    """Implied equity value of a deal.

    Formula: offer price × shares on issue (fully diluted if stated)
    Glossary: "Implied equity value" (M&A section)

    Example: offer A$4.10 × 500m shares = A$2,050m (A$2.05bn)
    """
    if offer_price <= 0:
        raise ValueError(f"offer_price must be > 0, got {offer_price}")
    if shares_on_issue <= 0:
        raise ValueError(f"shares_on_issue must be > 0, got {shares_on_issue}")
    return offer_price * shares_on_issue


def enterprise_value(equity_value: float, net_debt: float) -> float:
    """Enterprise value from equity value and net debt.

    Formula: EV = equity value + net debt
    Net debt = total debt − cash. Positive net debt means the company
    owes more than it holds in cash; negative means net cash.
    Glossary: "Enterprise value (EV)" (M&A section)

    Note: the glossary defines EV as equity value + net debt + minorities
    + preferred − associates where relevant. This function takes those
    adjustments as pre-computed additions to net_debt. The caller must
    handle minorities, preferred and associate adjustments before passing
    in net_debt; otherwise EV will be understated for companies with
    listed subsidiaries.

    Example: equity value A$2,050m + net debt A$450m = EV A$2,500m
    """
    return equity_value + net_debt


def ev_to_ebitda(ev: float, ebitda: float) -> float:
    """EV / EBITDA multiple.

    A common valuation multiple for M&A. Higher = more expensive relative
    to earnings power. Computed from verified inputs; never sent to the LLM.

    Raises ValueError for negative EV (e.g. extreme net-cash company): a
    negative multiple is meaningless and must not be published in a report.

    Example: EV A$2,500m / EBITDA A$250m = 10.0×
    """
    if ebitda <= 0:
        raise ValueError(f"ebitda must be > 0, got {ebitda}")
    if ev < 0:
        raise ValueError(f"ev is negative ({ev}); EV/EBITDA multiple is not meaningful")
    return ev / ebitda


def price_to_earnings(price: float, eps: float) -> float:
    """Price / earnings (P/E) multiple.

    Example: offer price A$4.10 / EPS A$0.28 = 14.6×
    """
    if eps <= 0:
        raise ValueError(f"eps must be > 0, got {eps}")
    return price / eps


def ev_to_revenue(ev: float, revenue: float) -> float:
    """EV / Revenue multiple.

    Example: EV US$500m / Revenue US$200m = 2.5×
    """
    if revenue <= 0:
        raise ValueError(f"revenue must be > 0, got {revenue}")
    return ev / revenue


# ---------------------------------------------------------------------------
# M&A: break fee
# ---------------------------------------------------------------------------

def break_fee_pct(break_fee: float, equity_value: float) -> float:
    """Break fee as a percentage of implied equity value.

    Takeovers Panel guidance treats ~1% as a general benchmark.
    Kimika reports the % only; it never judges whether it is appropriate.
    Glossary: "Break fee" (M&A section)

    Example: break fee A$20.5m / equity value A$2,050m = 1.0%
    """
    if equity_value <= 0:
        raise ValueError(f"equity_value must be > 0, got {equity_value}")
    return break_fee / equity_value * 100


# ---------------------------------------------------------------------------
# M&A: merger arbitrage spread
# ---------------------------------------------------------------------------

def arb_spread_pct(current_price: float, offer_value: float) -> float:
    """Merger arbitrage spread: gap between current target price and offer value.

    A wider spread signals the market sees more risk to deal completion.
    Glossary: "Merger arbitrage spread"

    Example: target trading at A$4.02, cash offer A$4.10
             → (4.10 − 4.02) / 4.10 × 100 = 1.95%
    A negative result means the target is trading above the offer (e.g.
    counter-bid speculation); this is valid and should not be guarded.
    """
    if offer_value <= 0:
        raise ValueError(f"offer_value must be > 0, got {offer_value}")
    return (offer_value - current_price) / offer_value * 100


# ---------------------------------------------------------------------------
# ECM: VWAP and dilution
# ---------------------------------------------------------------------------

def vwap(closes: list[float], volumes: list[float]) -> float:
    """Volume-weighted average price over N trading days.

    Formula: Σ(close × volume) / Σ(volume)
    Glossary: "VWAP" (ECM section) — Kimika approximates with daily closes,
    which is not exact (intraday prices differ from the close).

    Example: closes [1.00, 1.02, 0.99], volumes [1_000_000, 800_000, 1_200_000]
             → (1,000,000 + 816,000 + 1,188,000) / 3,000,000 = 1.0013
    """
    if len(closes) != len(volumes):
        raise ValueError("closes and volumes must be the same length")
    if not closes:
        raise ValueError("closes list must not be empty")
    total_volume = sum(volumes)
    if total_volume <= 0:
        raise ValueError("total volume must be > 0")
    return sum(c * v for c, v in zip(closes, volumes)) / total_volume


def dilution_pct(new_shares: float, existing_shares: float) -> float:
    """Dilution from a share issuance, as a percentage of pre-raise shares.

    Formula: new shares / existing shares × 100
    Glossary: "Dilution" (ECM section)

    Example: 50m new shares / 500m existing shares = 10.0% dilution
    """
    if existing_shares <= 0:
        raise ValueError(f"existing_shares must be > 0, got {existing_shares}")
    return new_shares / existing_shares * 100


# ---------------------------------------------------------------------------
# Scrip consideration
# ---------------------------------------------------------------------------

def scrip_value(ratio: float, acquirer_price: float) -> float:
    """Value of scrip consideration per target share.

    Formula: scrip ratio × acquirer's current share price
    Glossary: "Scrip ratio" (M&A section)

    Example: ratio 0.5 × acquirer at A$10.00 = A$5.00 per target share
    """
    if ratio <= 0:
        raise ValueError(f"ratio must be > 0, got {ratio}")
    if acquirer_price <= 0:
        raise ValueError(f"acquirer_price must be > 0, got {acquirer_price}")
    return ratio * acquirer_price


# ---------------------------------------------------------------------------
# Mixed consideration (cash + scrip)
# ---------------------------------------------------------------------------

def mixed_consideration(
    cash_per_share: float,
    scrip_ratio: float,
    acquirer_price: float,
) -> float:
    """Total offer value per target share for a cash-and-scrip deal.

    Formula: cash + (scrip_ratio × acquirer_price)
    Glossary: "Consideration" and "Scrip ratio" (M&A section)

    Example: A$1.50 cash + 0.25 acquirer shares at A$10.00
             → A$1.50 + 0.25 × A$10.00 = A$4.00 per target share

    Pass cash_per_share=0 for pure scrip; scrip_ratio=0 for pure cash.
    """
    if cash_per_share < 0:
        raise ValueError(f"cash_per_share must be ≥ 0, got {cash_per_share}")
    if scrip_ratio < 0:
        raise ValueError(f"scrip_ratio must be ≥ 0, got {scrip_ratio}")
    if acquirer_price < 0:
        raise ValueError(f"acquirer_price must be ≥ 0, got {acquirer_price}")
    return cash_per_share + scrip_ratio * acquirer_price


# ---------------------------------------------------------------------------
# Currency conversion (for ranking deals by US$ equivalent)
# ---------------------------------------------------------------------------

def to_usd(amount: float, fx_rate: float) -> float:
    """Convert an amount in local currency to US dollars.

    fx_rate is USD per 1 unit of local currency (i.e. the standard direct
    quote: AUD/USD = 0.65 means A$1 = US$0.65).
        to_usd(amount_aud, 0.65)  →  amount_aud × 0.65

    Raises ValueError for non-positive fx_rate or negative amount (a
    negative deal value indicates a data error upstream).

    Example: A$2,050m at AUD/USD 0.65 → US$1,332.5m
    """
    if fx_rate <= 0:
        raise ValueError(f"fx_rate must be > 0, got {fx_rate}")
    if amount < 0:
        raise ValueError(f"amount must be ≥ 0, got {amount}")
    return amount * fx_rate


# ---------------------------------------------------------------------------
# Football field helper
# ---------------------------------------------------------------------------

def football_field_row(
    method: str,
    low: float,
    high: float,
    offer: float,
) -> dict:
    """Build one row of a football-field valuation table.

    Returns a dict with the method name, the low/high range, the offer price,
    and where the offer sits relative to the range:
      - 'below'  → offer < low  (offer is below the assessed range)
      - 'within' → low ≤ offer ≤ high
      - 'above'  → offer > high (offer is above the assessed range)

    Example: DCF low A$3.50 / high A$4.20, offer A$4.10 → 'within'
    """
    if low > high:
        raise ValueError(f"low ({low}) must be ≤ high ({high})")
    if offer < low:
        position = "below"
    elif offer > high:
        position = "above"
    else:
        position = "within"
    return {
        "method": method,
        "low": low,
        "high": high,
        "offer": offer,
        "offer_position": position,
    }


# ---------------------------------------------------------------------------
# Rounding helpers (report formatting)
# ---------------------------------------------------------------------------

def round_pct(value: float, dp: int = 1) -> float:
    """Round a percentage to dp decimal places (default 1, per CLAUDE.md)."""
    return round(value, dp)


def round_bps(value_pct: float) -> int:
    """Convert a percentage move to basis points and round to nearest integer.

    1% = 100 bps. Used for rate and spread moves.
    Example: 0.25% → 25 bps
    """
    return round(value_pct * 100)
