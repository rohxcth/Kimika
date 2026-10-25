"""Tests for app/sources.py — synthetic data only, no real network calls.

All HTTP is mocked. Fixture JSON reflects the real shapes of EDGAR, ASX and
RNS responses so the parsing logic is exercised properly.
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.sources import (
    RawDeal,
    _is_ma_asx,
    _is_ma_rns,
    _parse_asx_date,
    _parse_rns_date,
    _rns_filing_type,
    discover_all,
    discover_asx,
    discover_edgar,
    discover_rns,
    discover_economy_context,
)

TARGET_DATE = date(2026, 10, 26)
DATE_STR = "2026-10-26"

# ---------------------------------------------------------------------------
# Fixture data — realistic shapes for each source
# ---------------------------------------------------------------------------

EDGAR_FIXTURE = {
    "hits": {
        "hits": [
            {
                "_id": "0001234567/000123456726000001",
                "_source": {
                    "entity_name": "Acme Corp",
                    "form_type": "8-K",
                    "file_num": "001-12345",
                    "period_of_report": DATE_STR,
                    "cik": "0001234567",
                },
            },
            {
                "_id": "0009876543/000987654326000001",
                "_source": {
                    "entity_name": "Target Inc",
                    "form_type": "DEFM14A",
                    "file_num": "001-98765",
                    "period_of_report": DATE_STR,
                    "cik": "0009876543",
                },
            },
            {
                # Non-M&A form type — should be filtered out
                "_id": "0001111111/000111111126000001",
                "_source": {
                    "entity_name": "Random Co",
                    "form_type": "10-Q",
                    "file_num": "001-11111",
                    "period_of_report": DATE_STR,
                    "cik": "0001111111",
                },
            },
        ]
    }
}

ASX_FIXTURE = {
    "data": [
        {
            "id": "asx-001",
            "code": "BHP",
            "issuer_full_name": "BHP Group Limited",
            "header": "BHP proposes acquisition of Anglo American via scheme of arrangement",
            "date": f"{DATE_STR}T07:30:00",
            "url": "https://www.asx.com.au/asx/1/file/2026/BHP_announcement.pdf",
        },
        {
            "id": "asx-002",
            "code": "ANZ",
            "issuer_full_name": "ANZ Banking Group",
            "header": "ANZ completes acquisition of Suncorp Bank",
            "date": f"{DATE_STR}T08:00:00",
            "url": "https://www.asx.com.au/asx/1/file/2026/ANZ_announcement.pdf",
        },
        {
            # Non-M&A announcement — should be filtered out
            "id": "asx-003",
            "code": "WBC",
            "issuer_full_name": "Westpac Banking Corporation",
            "header": "Westpac quarterly CPI update",
            "date": f"{DATE_STR}T09:00:00",
            "url": "https://www.asx.com.au/asx/1/file/2026/WBC_announcement.pdf",
        },
        {
            # Different date — should be filtered out
            "id": "asx-004",
            "code": "CBA",
            "issuer_full_name": "Commonwealth Bank",
            "header": "CBA to acquire regional bank via scheme",
            "date": "2026-10-25T08:00:00",
            "url": "https://www.asx.com.au/asx/1/file/2026/CBA_announcement.pdf",
        },
    ]
}

RNS_FIXTURE = {
    "articles": [
        {
            "id": "rns-001",
            "tidm": "VOD",
            "companyName": "Vodafone Group Plc",
            "headline": "Rule 2.7 Announcement: Firm offer for Three UK",
            "publishedDate": f"{DATE_STR}T07:00:00Z",
            "category": "REG",
            "url": "https://www.londonstockexchange.com/exchange/news/market-news/rns-001.html",
        },
        {
            "id": "rns-002",
            "tidm": "LSEG",
            "companyName": "London Stock Exchange Group",
            "headline": "Possible offer — Rule 2.4 announcement",
            "publishedDate": f"{DATE_STR}T08:00:00Z",
            "category": "REG",
            "url": "https://www.londonstockexchange.com/exchange/news/market-news/rns-002.html",
        },
        {
            # Non-M&A — should be filtered out
            "id": "rns-003",
            "tidm": "BP",
            "companyName": "BP Plc",
            "headline": "BP quarterly production update",
            "publishedDate": f"{DATE_STR}T09:00:00Z",
            "category": "REG",
            "url": "https://www.londonstockexchange.com/exchange/news/market-news/rns-003.html",
        },
        {
            # Different date — should be filtered out
            "id": "rns-004",
            "tidm": "SHEL",
            "companyName": "Shell Plc",
            "headline": "Recommended cash offer for TotalEnergies UK",
            "publishedDate": "2026-10-25T07:00:00Z",
            "category": "REG",
            "url": "https://www.londonstockexchange.com/exchange/news/market-news/rns-004.html",
        },
    ]
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_json(data: dict):
    """Patch fetch_json to return a fixed dict."""
    m = MagicMock(return_value=data)
    return patch("app.sources.fetch_json", m)


def _mock_json_error(exc: Exception):
    m = MagicMock(side_effect=exc)
    return patch("app.sources.fetch_json", m)


# ---------------------------------------------------------------------------
# SEC EDGAR
# ---------------------------------------------------------------------------

def test_edgar_returns_ma_deals():
    with _mock_json(EDGAR_FIXTURE), patch("app.sources.time.sleep"):
        deals = discover_edgar(TARGET_DATE)
    assert len(deals) == 2  # 10-Q filtered out
    form_types = {d["filing_type"] for d in deals}
    assert "8-K" in form_types
    assert "DEFM14A" in form_types


def test_edgar_deal_fields():
    with _mock_json(EDGAR_FIXTURE), patch("app.sources.time.sleep"):
        deals = discover_edgar(TARGET_DATE)
    deal = next(d for d in deals if d["filing_type"] == "8-K")
    assert deal["source"] == "EDGAR"
    assert deal["region"] == "US"
    assert deal["date"] == DATE_STR
    assert deal["company"] == "Acme Corp"
    assert deal["url"]  # non-empty


def test_edgar_filters_non_ma_forms():
    with _mock_json(EDGAR_FIXTURE), patch("app.sources.time.sleep"):
        deals = discover_edgar(TARGET_DATE)
    form_types = [d["filing_type"] for d in deals]
    assert "10-Q" not in form_types


def test_edgar_empty_hits():
    with _mock_json({"hits": {"hits": []}}), patch("app.sources.time.sleep"):
        deals = discover_edgar(TARGET_DATE)
    assert deals == []


def test_edgar_network_error_returns_empty(caplog):
    with _mock_json_error(Exception("network error")):
        deals = discover_edgar(TARGET_DATE)
    assert deals == []
    assert any("EDGAR" in r.message for r in caplog.records)


def test_edgar_rate_limit_called():
    """time.sleep should be called once per deal to respect EDGAR rate limits."""
    with _mock_json(EDGAR_FIXTURE) as _, patch("app.sources.time.sleep") as mock_sleep:
        discover_edgar(TARGET_DATE)
    assert mock_sleep.call_count == 2  # one per accepted deal


# ---------------------------------------------------------------------------
# ASX
# ---------------------------------------------------------------------------

def test_asx_returns_ma_announcements():
    with _mock_json(ASX_FIXTURE):
        deals = discover_asx(TARGET_DATE)
    assert len(deals) == 2  # non-M&A and wrong-date filtered


def test_asx_deal_fields():
    with _mock_json(ASX_FIXTURE):
        deals = discover_asx(TARGET_DATE)
    bhp = next(d for d in deals if d["extra"]["ticker"] == "BHP")
    assert bhp["source"] == "ASX"
    assert bhp["region"] == "AU"
    assert bhp["filing_type"] == "ASX_announcement"
    assert bhp["date"] == DATE_STR
    assert "BHP Group" in bhp["company"]


def test_asx_filters_non_ma():
    with _mock_json(ASX_FIXTURE):
        deals = discover_asx(TARGET_DATE)
    titles = [d["title"] for d in deals]
    assert not any("CPI" in t for t in titles)


def test_asx_filters_wrong_date():
    with _mock_json(ASX_FIXTURE):
        deals = discover_asx(TARGET_DATE)
    # CBA announcement is dated 25 Oct, not 26 Oct
    companies = [d["company"] for d in deals]
    assert "Commonwealth Bank" not in companies


def test_asx_list_response():
    """ASX sometimes returns a bare list rather than {"data": [...]}."""
    bare_list = ASX_FIXTURE["data"]
    with _mock_json(bare_list):
        deals = discover_asx(TARGET_DATE)
    assert len(deals) == 2


def test_asx_network_error_returns_empty(caplog):
    with _mock_json_error(Exception("timeout")):
        deals = discover_asx(TARGET_DATE)
    assert deals == []
    assert any("ASX" in r.message for r in caplog.records)


def test_asx_empty_returns_empty():
    with _mock_json({"data": []}):
        deals = discover_asx(TARGET_DATE)
    assert deals == []


# ---------------------------------------------------------------------------
# UK RNS
# ---------------------------------------------------------------------------

def test_rns_returns_ma_announcements():
    with _mock_json(RNS_FIXTURE):
        deals = discover_rns(TARGET_DATE)
    assert len(deals) == 2  # non-M&A and wrong-date filtered


def test_rns_deal_fields():
    with _mock_json(RNS_FIXTURE):
        deals = discover_rns(TARGET_DATE)
    vod = next(d for d in deals if d["extra"]["ticker"] == "VOD")
    assert vod["source"] == "RNS"
    assert vod["region"] == "UK"
    assert vod["filing_type"] == "RNS_Rule27"
    assert vod["date"] == DATE_STR
    assert vod["company"] == "Vodafone Group Plc"


def test_rns_rule24_filing_type():
    with _mock_json(RNS_FIXTURE):
        deals = discover_rns(TARGET_DATE)
    lseg = next(d for d in deals if d["extra"]["ticker"] == "LSEG")
    assert lseg["filing_type"] == "RNS_Rule24"


def test_rns_filters_non_ma():
    with _mock_json(RNS_FIXTURE):
        deals = discover_rns(TARGET_DATE)
    companies = [d["company"] for d in deals]
    assert "BP Plc" not in companies


def test_rns_filters_wrong_date():
    with _mock_json(RNS_FIXTURE):
        deals = discover_rns(TARGET_DATE)
    companies = [d["company"] for d in deals]
    assert "Shell Plc" not in companies


def test_rns_network_error_returns_empty(caplog):
    with _mock_json_error(ConnectionError("refused")):
        deals = discover_rns(TARGET_DATE)
    assert deals == []
    assert any("RNS" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# discover_all — combined
# ---------------------------------------------------------------------------

def test_discover_all_combines_sources():
    with (
        patch("app.sources.discover_edgar", return_value=[{"source": "EDGAR", "title": "e1"}]),
        patch("app.sources.discover_asx",   return_value=[{"source": "ASX",   "title": "a1"}, {"source": "ASX", "title": "a2"}]),
        patch("app.sources.discover_rns",   return_value=[{"source": "RNS",   "title": "r1"}]),
    ):
        results = discover_all(TARGET_DATE)
    assert len(results) == 4
    sources = [r["source"] for r in results]
    assert "EDGAR" in sources and "ASX" in sources and "RNS" in sources


def test_discover_all_continues_on_partial_failure():
    """If one source raises, the others still run."""
    def boom(_date):
        raise RuntimeError("EDGAR is down")

    with (
        patch("app.sources.discover_edgar", side_effect=boom),
        patch("app.sources.discover_asx",   return_value=[{"source": "ASX", "title": "a1"}]),
        patch("app.sources.discover_rns",   return_value=[{"source": "RNS", "title": "r1"}]),
    ):
        results = discover_all(TARGET_DATE)
    assert len(results) == 2
    sources = {r["source"] for r in results}
    assert "EDGAR" not in sources


# ---------------------------------------------------------------------------
# Keyword filters
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,expected", [
    ("BHP proposes acquisition of Anglo American", True),
    ("Company announces scheme of arrangement", True),
    ("Takeover bid for Target Corp", True),
    ("Quarterly earnings update", False),
    ("New CEO appointment", False),
    ("Market sensitive: proposed merger", True),
])
def test_is_ma_asx(title, expected):
    assert _is_ma_asx(title) == expected


@pytest.mark.parametrize("headline,category,expected", [
    ("Rule 2.7 Announcement: Firm offer", "REG", True),
    ("Possible offer — Rule 2.4", "REG", True),
    ("Recommended cash offer for XYZ", "REG", True),
    ("Quarterly production update", "REG", False),
    ("Director shareholding change", "REG", False),
])
def test_is_ma_rns(headline, category, expected):
    assert _is_ma_rns(headline, category) == expected


# ---------------------------------------------------------------------------
# Filing type classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("headline,category,expected", [
    ("Rule 2.7 Announcement: Firm offer for ABC", "REG", "RNS_Rule27"),
    ("Firm intention to make an offer", "REG", "RNS_Rule27"),
    ("Possible offer — Rule 2.4 announcement", "REG", "RNS_Rule24"),
    ("Recommended cash offer for XYZ", "REG", "RNS_announcement"),
])
def test_rns_filing_type(headline, category, expected):
    assert _rns_filing_type(headline, category) == expected


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def test_parse_asx_date_iso():
    dt = _parse_asx_date("2026-10-26T07:30:00")
    assert dt is not None
    assert dt.date() == date(2026, 10, 26)


def test_parse_asx_date_invalid_returns_none():
    assert _parse_asx_date("not-a-date") is None
    assert _parse_asx_date("") is None


def test_parse_rns_date_z_suffix():
    dt = _parse_rns_date("2026-10-26T07:00:00Z")
    assert dt is not None
    assert dt.date() == date(2026, 10, 26)


def test_parse_rns_date_invalid_returns_none():
    assert _parse_rns_date("garbage") is None


# ---------------------------------------------------------------------------
# discover_economy_context
# ---------------------------------------------------------------------------

def test_economy_context_returns_string_with_mocked_fetch():
    """discover_economy_context concatenates Fed and RBA page text."""
    with (
        patch("app.sources.fetch", return_value="<html>Central bank content</html>"),
        patch("app.sources.fetch_json", return_value={}),
        patch.dict("os.environ", {}, clear=False),
    ):
        # Remove FRED key so FRED branch is skipped
        import os
        os.environ.pop("FRED_API_KEY", None)
        result = discover_economy_context(TARGET_DATE)

    assert isinstance(result, str)
    assert "Federal Reserve" in result or "RBA" in result


def test_economy_context_includes_fred_when_key_set():
    """When FRED_API_KEY is set, FRED data is fetched and included."""
    fred_response = {
        "observations": [
            {"date": "2026-10-01", "value": "5.33"},
            {"date": "2026-09-01", "value": "5.33"},
        ]
    }
    with (
        patch("app.sources.fetch", return_value="<html>page</html>"),
        patch("app.sources.fetch_json", return_value=fred_response),
        patch.dict("os.environ", {"FRED_API_KEY": "test_key"}),
    ):
        result = discover_economy_context(TARGET_DATE)

    assert "FRED" in result
    assert "5.33" in result


def test_economy_context_fetch_failure_returns_partial():
    """A fetch failure on one source doesn't crash; other sources still included."""
    call_count = 0

    def selective_fetch(url):
        nonlocal call_count
        call_count += 1
        if "federalreserve" in url:
            raise ConnectionError("timeout")
        return "<html>RBA content</html>"

    import os
    os.environ.pop("FRED_API_KEY", None)
    with patch("app.sources.fetch", side_effect=selective_fetch):
        result = discover_economy_context(TARGET_DATE)

    # RBA should still be in result even though Fed failed
    assert isinstance(result, str)
    assert call_count >= 1


def test_economy_context_all_failures_returns_empty_string():
    """All sources failing returns an empty string, not an exception."""
    import os
    os.environ.pop("FRED_API_KEY", None)
    with patch("app.sources.fetch", side_effect=Exception("all down")):
        result = discover_economy_context(TARGET_DATE)
    assert result == ""
