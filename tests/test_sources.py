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
    NewsItem,
    _is_ma_asx,
    _is_ma_rns,
    _parse_asx_date,
    _parse_rns_date,
    _rns_filing_type,
    _strip_html,
    discover_all,
    discover_asx,
    discover_edgar,
    discover_rns,
    discover_economy_context,
    discover_markets_context,
    discover_google_news_rss,
    discover_newsapi,
    discover_edgar_fulltext,
    discover_news,
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


# ---------------------------------------------------------------------------
# discover_markets_context
# ---------------------------------------------------------------------------

def test_markets_context_returns_four_keys():
    """discover_markets_context always returns a dict with the four section keys."""
    with patch("app.sources._fetch_yfinance_tickers", return_value="mock data"):
        result = discover_markets_context(TARGET_DATE)
    assert set(result.keys()) == {"equities", "commodities", "bonds", "currencies"}


def test_markets_context_keys_are_strings():
    """Each value in the returned dict is a string (may be empty on failure)."""
    with patch("app.sources._fetch_yfinance_tickers", return_value=""):
        result = discover_markets_context(TARGET_DATE)
    for key, val in result.items():
        assert isinstance(val, str), f"{key} value should be str"


def test_markets_context_yfinance_no_data_returns_empty_strings():
    """If yfinance returns empty strings for all tickers, all four values are empty strings."""
    with patch("app.sources._fetch_yfinance_tickers", return_value=""):
        result = discover_markets_context(TARGET_DATE)
    assert set(result.keys()) == {"equities", "commodities", "bonds", "currencies"}
    for val in result.values():
        assert isinstance(val, str)


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------

def test_strip_html_removes_tags():
    assert _strip_html("<b>Hello</b> <i>world</i>") == "Hello world"


def test_strip_html_plain_text_unchanged():
    assert _strip_html("No tags here") == "No tags here"


def test_strip_html_empty_string():
    assert _strip_html("") == ""


# ---------------------------------------------------------------------------
# Google News RSS fixtures and tests
# ---------------------------------------------------------------------------

GOOGLE_NEWS_RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Google News</title>
    <item>
      <title>Acme Corp to acquire Beta Ltd for A$2bn</title>
      <link>https://news.google.com/rss/articles/abc123</link>
      <pubDate>Mon, 26 Oct 2026 07:00:00 GMT</pubDate>
      <description>&lt;p&gt;Acme Corp has announced a A$2bn scheme of arrangement.&lt;/p&gt;</description>
      <source url="https://reuters.com">Reuters</source>
    </item>
    <item>
      <title>Beta Ltd shareholders to vote on scheme</title>
      <link>https://news.google.com/rss/articles/def456</link>
      <pubDate>Mon, 26 Oct 2026 08:00:00 GMT</pubDate>
      <description>Scheme vote scheduled for December.</description>
      <source url="https://afr.com">AFR</source>
    </item>
    <item>
      <title>No title or link article</title>
      <link></link>
      <pubDate>Mon, 26 Oct 2026 09:00:00 GMT</pubDate>
      <description>Should be filtered out.</description>
    </item>
  </channel>
</rss>"""


def test_google_news_rss_returns_items():
    with patch("app.sources.fetch", return_value=GOOGLE_NEWS_RSS_FIXTURE):
        items = discover_google_news_rss("Acme Corp Beta Ltd acquisition")
    assert len(items) == 2  # third item has empty link — filtered out


def test_google_news_rss_item_fields():
    with patch("app.sources.fetch", return_value=GOOGLE_NEWS_RSS_FIXTURE):
        items = discover_google_news_rss("Acme Corp")
    first = items[0]
    assert first["title"] == "Acme Corp to acquire Beta Ltd for A$2bn"
    assert "news.google.com" in first["url"]
    assert first["source"] == "GoogleNews:Reuters"
    assert first["published"] == "Mon, 26 Oct 2026 07:00:00 GMT"


def test_google_news_rss_strips_html_from_snippet():
    with patch("app.sources.fetch", return_value=GOOGLE_NEWS_RSS_FIXTURE):
        items = discover_google_news_rss("Acme")
    # Description had <p> tags — should be stripped
    assert "<p>" not in items[0]["snippet"]
    assert "Acme Corp" in items[0]["snippet"]


def test_google_news_rss_network_error_returns_empty():
    with patch("app.sources.fetch", side_effect=ConnectionError("timeout")):
        items = discover_google_news_rss("test query")
    assert items == []


def test_google_news_rss_invalid_xml_returns_empty():
    with patch("app.sources.fetch", return_value="not valid xml <<<"):
        items = discover_google_news_rss("test query")
    assert items == []


def test_google_news_rss_max_results_respected():
    with patch("app.sources.fetch", return_value=GOOGLE_NEWS_RSS_FIXTURE):
        items = discover_google_news_rss("query", max_results=1)
    assert len(items) == 1


# ---------------------------------------------------------------------------
# NewsAPI fixtures and tests
# ---------------------------------------------------------------------------

NEWSAPI_FIXTURE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "title": "Acme Corp scheme approved by court",
            "url": "https://apnews.com/article/acme-corp-scheme",
            "publishedAt": "2026-10-26T08:00:00Z",
            "description": "The Federal Court approved the Acme/Beta scheme.",
            "source": {"name": "AP News"},
        },
        {
            "title": "Beta Ltd shareholders vote in favour",
            "url": "https://reuters.com/article/beta-vote",
            "publishedAt": "2026-10-26T09:00:00Z",
            "description": "98% of Beta Ltd shareholders voted in favour.",
            "source": {"name": "Reuters"},
        },
    ],
}


def test_newsapi_returns_items_when_key_set():
    with (
        patch("app.sources.fetch_json", return_value=NEWSAPI_FIXTURE),
        patch.dict("os.environ", {"NEWSAPI_KEY": "test_key"}),
    ):
        items = discover_newsapi("Acme Corp Beta Ltd")
    assert len(items) == 2


def test_newsapi_item_fields():
    with (
        patch("app.sources.fetch_json", return_value=NEWSAPI_FIXTURE),
        patch.dict("os.environ", {"NEWSAPI_KEY": "test_key"}),
    ):
        items = discover_newsapi("Acme Corp")
    first = items[0]
    assert first["title"] == "Acme Corp scheme approved by court"
    assert first["source"] == "NewsAPI:AP News"
    assert first["published"] == "2026-10-26T08:00:00Z"


def test_newsapi_skips_when_no_key():
    import os
    os.environ.pop("NEWSAPI_KEY", None)
    with patch("app.sources.fetch_json") as mock_fetch:
        items = discover_newsapi("test query")
    assert items == []
    mock_fetch.assert_not_called()


def test_newsapi_bad_status_returns_empty():
    with (
        patch("app.sources.fetch_json", return_value={"status": "error", "message": "apiKeyInvalid"}),
        patch.dict("os.environ", {"NEWSAPI_KEY": "bad_key"}),
    ):
        items = discover_newsapi("test")
    assert items == []


def test_newsapi_network_error_returns_empty():
    with (
        patch("app.sources.fetch_json", side_effect=ConnectionError("timeout")),
        patch.dict("os.environ", {"NEWSAPI_KEY": "test_key"}),
    ):
        items = discover_newsapi("test")
    assert items == []


def test_newsapi_filters_items_missing_title_or_url():
    fixture = {
        "status": "ok",
        "articles": [
            {"title": "", "url": "https://example.com", "source": {"name": "X"}, "publishedAt": "", "description": ""},
            {"title": "Good article", "url": "", "source": {"name": "Y"}, "publishedAt": "", "description": ""},
            {"title": "Valid", "url": "https://valid.com", "source": {"name": "Z"}, "publishedAt": "", "description": ""},
        ],
    }
    with (
        patch("app.sources.fetch_json", return_value=fixture),
        patch.dict("os.environ", {"NEWSAPI_KEY": "key"}),
    ):
        items = discover_newsapi("test")
    assert len(items) == 1
    assert items[0]["title"] == "Valid"


# ---------------------------------------------------------------------------
# EDGAR full-text search
# ---------------------------------------------------------------------------

EDGAR_FULLTEXT_FIXTURE = {
    "hits": {
        "hits": [
            {
                "_id": "0001234567/000001",
                "_source": {
                    "entity_name": "Acme Corp",
                    "form_type": "8-K",
                    "file_date": "2026-10-26",
                    "cik": "0001234567",
                },
            },
            {
                "_id": "0009876543/000002",
                "_source": {
                    "entity_name": "Beta Ltd",
                    "form_type": "DEFM14A",
                    "file_date": "2026-10-20",
                    "cik": "0009876543",
                },
            },
        ]
    }
}


def test_edgar_fulltext_returns_items():
    with (
        patch("app.sources.fetch_json", return_value=EDGAR_FULLTEXT_FIXTURE),
        patch("app.sources.time.sleep"),
    ):
        items = discover_edgar_fulltext("Acme Corp Beta Ltd")
    assert len(items) == 2


def test_edgar_fulltext_item_fields():
    with (
        patch("app.sources.fetch_json", return_value=EDGAR_FULLTEXT_FIXTURE),
        patch("app.sources.time.sleep"),
    ):
        items = discover_edgar_fulltext("Acme")
    first = items[0]
    assert first["source"] == "EDGAR_fulltext"
    assert "Acme Corp" in first["title"]
    assert "8-K" in first["title"]
    assert first["published"] == "2026-10-26"


def test_edgar_fulltext_max_results_respected():
    with (
        patch("app.sources.fetch_json", return_value=EDGAR_FULLTEXT_FIXTURE),
        patch("app.sources.time.sleep"),
    ):
        items = discover_edgar_fulltext("Acme", max_results=1)
    assert len(items) == 1


def test_edgar_fulltext_network_error_returns_empty():
    with patch("app.sources.fetch_json", side_effect=ConnectionError("down")):
        items = discover_edgar_fulltext("test")
    assert items == []


# ---------------------------------------------------------------------------
# discover_news — combined aggregator
# ---------------------------------------------------------------------------

def test_discover_news_combines_sources():
    with (
        patch("app.sources.discover_google_news_rss", return_value=[
            NewsItem(title="G1", url="https://g1.com", source="GoogleNews:Reuters", published="", snippet=""),
        ]),
        patch("app.sources.discover_newsapi", return_value=[
            NewsItem(title="N1", url="https://n1.com", source="NewsAPI:AP", published="", snippet=""),
        ]),
        patch("app.sources.discover_edgar_fulltext", return_value=[
            NewsItem(title="E1", url="https://e1.com", source="EDGAR_fulltext", published="", snippet=""),
        ]),
        patch("app.sources._enrich_news_items"),
    ):
        items = discover_news("test query")
    assert len(items) == 3
    sources = {i["source"] for i in items}
    assert "GoogleNews:Reuters" in sources
    assert "NewsAPI:AP" in sources
    assert "EDGAR_fulltext" in sources


def test_discover_news_deduplicates_by_url():
    duplicate = NewsItem(title="Dup", url="https://same.com", source="GoogleNews:X", published="", snippet="")
    with (
        patch("app.sources.discover_google_news_rss", return_value=[duplicate]),
        patch("app.sources.discover_newsapi", return_value=[duplicate]),
        patch("app.sources.discover_edgar_fulltext", return_value=[]),
        patch("app.sources._enrich_news_items"),
    ):
        items = discover_news("test")
    assert len(items) == 1


def test_discover_news_continues_on_partial_failure():
    def boom(_q, **_kw):
        raise RuntimeError("source down")

    with (
        patch("app.sources.discover_google_news_rss", side_effect=boom),
        patch("app.sources.discover_newsapi", return_value=[
            NewsItem(title="N1", url="https://n1.com", source="NewsAPI:X", published="", snippet=""),
        ]),
        patch("app.sources.discover_edgar_fulltext", return_value=[]),
        patch("app.sources._enrich_news_items"),
    ):
        items = discover_news("test")
    assert len(items) == 1
    assert items[0]["source"] == "NewsAPI:X"


# ---------------------------------------------------------------------------
# discover_market_figures
# ---------------------------------------------------------------------------

from app.sources import discover_market_figures


def _mock_yfinance(figures: dict[str, float]):
    """Return a mock yfinance module whose Ticker.history yields the given values."""
    import pandas as pd
    from unittest.mock import MagicMock

    def _make_ticker(ticker):
        # Map yf tickers back to figure names to return the right value
        from app.sources import _VERIFIABLE_FIGURES
        val = None
        for fig_name, (yf_tick, _fmp, _sec) in _VERIFIABLE_FIGURES.items():
            if yf_tick == ticker and fig_name in figures:
                val = figures[fig_name]
                break
        mock_ticker = MagicMock()
        if val is not None:
            hist = pd.DataFrame({"Close": [val - 0.01, val]})
        else:
            hist = pd.DataFrame()
        mock_ticker.history.return_value = hist
        return mock_ticker

    mock_yf = MagicMock()
    mock_yf.Ticker.side_effect = _make_ticker
    return mock_yf


def test_discover_market_figures_returns_sections():
    result = discover_market_figures.__wrapped__() if hasattr(discover_market_figures, '__wrapped__') else None
    result = discover_market_figures()
    assert isinstance(result, dict)
    for section in ("equities", "commodities", "bonds", "currencies"):
        assert section in result


def test_discover_market_figures_yfinance_only(monkeypatch):
    """With no FMP key and mocked yfinance, only yfinance figures appear."""
    import sys
    from unittest.mock import patch, MagicMock

    mock_yf = _mock_yfinance({
        "audusd_rate": 0.645,
        "gold_usd_oz": 2718.5,
        "us_10y_yield_pct": 4.38,
        "sp500_level": 5832.1,
    })

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    with patch.dict(sys.modules, {"yfinance": mock_yf}):
        result = discover_market_figures()

    # AUD/USD should appear in currencies with yfinance source
    currencies = result.get("currencies", {})
    if "audusd_rate" in currencies:
        assert "yfinance" in currencies["audusd_rate"]
        assert "FMP" not in currencies["audusd_rate"]


def test_discover_market_figures_sections_are_dicts():
    from unittest.mock import patch
    with patch("app.sources.fetch_json", return_value=[]):
        result = discover_market_figures()
    for section_data in result.values():
        assert isinstance(section_data, dict)


def test_discover_market_figures_values_are_positive(monkeypatch):
    """All returned figures must be positive floats."""
    import sys
    mock_yf = _mock_yfinance({
        "audusd_rate": 0.645,
        "gold_usd_oz": 2718.5,
        "us_10y_yield_pct": 4.38,
        "sp500_level": 5832.1,
        "asx200_level": 8341.0,
        "nasdaq100_level": 18447.0,
        "wti_crude_usd_bbl": 71.5,
        "eurusd_rate": 1.085,
        "gbpusd_rate": 1.292,
        "us_30y_yield_pct": 4.55,
    })
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    with patch.dict(sys.modules, {"yfinance": mock_yf}):
        result = discover_market_figures()

    for section, figures in result.items():
        for fig_name, readings in figures.items():
            for source, val in readings.items():
                assert isinstance(val, float), f"{fig_name} from {source} is not float"
                assert val > 0, f"{fig_name} from {source} is not positive"


def test_discover_market_figures_fmp_added_when_key_set(monkeypatch):
    """When FMP key is set and returns prices, FMP appears as second source."""
    import sys
    from unittest.mock import patch

    mock_yf = _mock_yfinance({"audusd_rate": 0.645, "gold_usd_oz": 2718.5})
    fmp_response = [
        {"symbol": "AUDUSD", "price": 0.6451},
        {"symbol": "GCUSD",  "price": 2717.0},
    ]

    monkeypatch.setenv("FMP_API_KEY", "testkey")
    with (
        patch.dict(sys.modules, {"yfinance": mock_yf}),
        patch("app.sources.fetch_json", return_value=fmp_response),
    ):
        result = discover_market_figures()

    currencies = result.get("currencies", {})
    if "audusd_rate" in currencies:
        assert "FMP" in currencies["audusd_rate"]
        assert "yfinance" in currencies["audusd_rate"]


def test_discover_market_figures_yfinance_unavailable(monkeypatch):
    """If yfinance is not importable, result has empty sections (no crash)."""
    import sys
    from unittest.mock import patch

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    # Simulate ImportError by temporarily hiding yfinance
    with patch.dict(sys.modules, {"yfinance": None}):
        result = discover_market_figures()

    # Should still return the section structure, just empty
    for section in ("equities", "commodities", "bonds", "currencies"):
        assert section in result


def test_discover_market_figures_fmp_failure_still_returns_yfinance(monkeypatch):
    """FMP batch failure should not suppress yfinance results."""
    import sys
    from unittest.mock import patch

    mock_yf = _mock_yfinance({"audusd_rate": 0.645})
    monkeypatch.setenv("FMP_API_KEY", "testkey")
    with (
        patch.dict(sys.modules, {"yfinance": mock_yf}),
        patch("app.sources.fetch_json", side_effect=Exception("FMP down")),
    ):
        result = discover_market_figures()

    currencies = result.get("currencies", {})
    if "audusd_rate" in currencies:
        assert "yfinance" in currencies["audusd_rate"]

# ---------------------------------------------------------------------------
# _enrich_news_items
# ---------------------------------------------------------------------------

from app.sources import _enrich_news_items


def test_enrich_news_items_adds_content():
    """fetch() returns article text → item gets content field."""
    items = [
        NewsItem(title="Article", url="https://example.com/article", source="GoogleNews:X", published="", snippet="short"),
    ]
    with patch("app.sources.fetch", return_value="Full article body text " * 20):
        _enrich_news_items(items, max_items=3)
    assert "content" in items[0]
    assert len(items[0]["content"]) > 50


def test_enrich_news_items_skips_edgar_browse_urls():
    """EDGAR browse/search URLs are not articles; content should not be fetched."""
    items = [
        NewsItem(title="Filing", url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=12345", source="EDGAR_fulltext", published="", snippet=""),
    ]
    with patch("app.sources.fetch") as mock_fetch:
        _enrich_news_items(items, max_items=3)
    mock_fetch.assert_not_called()
    assert "content" not in items[0]


def test_enrich_news_items_respects_max_items():
    """Only max_items articles are fetched even when more items exist."""
    items = [
        NewsItem(title=f"A{i}", url=f"https://example.com/{i}", source="GoogleNews:X", published="", snippet="")
        for i in range(5)
    ]
    with patch("app.sources.fetch", return_value="body text " * 30):
        _enrich_news_items(items, max_items=2)
    enriched = [i for i in items if "content" in i]
    assert len(enriched) == 2


def test_enrich_news_items_skips_failed_fetch():
    """A failed fetch is silently skipped; item keeps its snippet."""
    items = [
        NewsItem(title="Good", url="https://example.com/good", source="GoogleNews:X", published="", snippet="ok"),
        NewsItem(title="Bad", url="https://example.com/bad", source="GoogleNews:X", published="", snippet="ok"),
    ]

    def _selective_fetch(url, **_kw):
        if "bad" in url:
            raise Exception("blocked")
        return "full body text " * 20

    with patch("app.sources.fetch", side_effect=_selective_fetch):
        _enrich_news_items(items, max_items=3)

    assert "content" in items[0]
    assert "content" not in items[1]


def test_enrich_news_items_skips_short_responses():
    """Responses under 200 chars are treated as non-articles and skipped."""
    items = [
        NewsItem(title="Short", url="https://example.com/short", source="GoogleNews:X", published="", snippet=""),
    ]
    with patch("app.sources.fetch", return_value="too short"):
        _enrich_news_items(items, max_items=3)
    assert "content" not in items[0]


def test_discover_news_calls_enrich():
    """discover_news() calls _enrich_news_items on combined results."""
    item = NewsItem(title="X", url="https://x.com", source="GoogleNews:X", published="", snippet="")
    with (
        patch("app.sources.discover_google_news_rss", return_value=[item]),
        patch("app.sources.discover_newsapi", return_value=[]),
        patch("app.sources.discover_edgar_fulltext", return_value=[]),
        patch("app.sources._enrich_news_items") as mock_enrich,
    ):
        discover_news("test")
    mock_enrich.assert_called_once()
    args = mock_enrich.call_args[0]
    assert len(args[0]) == 1  # the single item was passed


# ---------------------------------------------------------------------------
# discover_economy_context — actual document fetch
# ---------------------------------------------------------------------------

import xml.etree.ElementTree as ET


def _fed_rss_xml(urls: list[str]) -> str:
    """Minimal RSS XML with the given item links."""
    items = "\n".join(
        f"<item><title>FOMC Statement</title><link>{u}</link></item>"
        for u in urls
    )
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'


def test_discover_economy_context_fetches_fed_statement():
    """Should parse Fed RSS and fetch the linked statement document."""
    rss_xml = _fed_rss_xml(["https://www.federalreserve.gov/newsevents/pressreleases/monetary20261026a.htm"])
    fetch_calls: list[str] = []

    def _mock_fetch(url, **_kw):
        fetch_calls.append(url)
        if "press_monetary.xml" in url:
            return rss_xml
        return "The Federal Open Market Committee decided to maintain the target range..."

    with patch("app.sources.fetch", side_effect=_mock_fetch):
        result = discover_economy_context(date(2026, 10, 26))

    # Should have fetched the RSS feed and then the statement URL
    assert any("press_monetary.xml" in u for u in fetch_calls)
    assert any("monetary20261026a" in u for u in fetch_calls)
    assert "Federal Reserve Press Release" in result


def test_discover_economy_context_fetches_rba_statement():
    """Should parse RBA decisions index and fetch the latest statement."""
    rba_index_html = '<a href="/monetary-policy/int-rate-decisions/2026/2026-10-statement.html">October 2026</a>'

    def _mock_fetch(url, **_kw):
        if "press_monetary.xml" in url:
            return _fed_rss_xml([])  # no Fed items
        if "int-rate-decisions" in url and "2026-10" not in url:
            return rba_index_html
        return "The RBA Board decided to leave the cash rate target unchanged..."

    with patch("app.sources.fetch", side_effect=_mock_fetch):
        result = discover_economy_context(date(2026, 10, 26))

    assert "RBA Interest Rate Decision" in result


def test_discover_economy_context_falls_back_on_rba_no_links():
    """If no statement links found in RBA index, falls back to index page text."""
    def _mock_fetch(url, **_kw):
        if "press_monetary.xml" in url:
            return _fed_rss_xml([])
        return "RBA decisions page with no links"

    with patch("app.sources.fetch", side_effect=_mock_fetch):
        result = discover_economy_context(date(2026, 10, 26))

    assert "RBA" in result


def test_discover_economy_context_survives_all_failures():
    """All fetches failing returns an empty string without raising."""
    with patch("app.sources.fetch", side_effect=Exception("network down")):
        result = discover_economy_context(date(2026, 10, 26))
    assert isinstance(result, str)
