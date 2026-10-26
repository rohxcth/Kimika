"""Tests for app/dossier.py — synthetic data, no network."""

from __future__ import annotations

import pytest

from app.dossier import (
    WORD_COUNT_TARGETS,
    DocChunk,
    Dossier,
    _classify_authority,
    _classify_chunk_type,
    _normalise_date,
    _trim,
    build_deal_dossier,
    build_market_dossier,
    dossier_summary,
)
from app.sources import NewsItem

DATE = "2026-10-26"
TOPIC = "Acme Corp / Beta Ltd scheme"


# ---------------------------------------------------------------------------
# _classify_chunk_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source,expected", [
    ("ASX announcement",          "filing"),
    ("8-K filing",                "filing"),
    ("Scheme booklet",            "filing"),
    ("FRED macroeconomic data",   "data"),
    ("RBA interest rate page",    "data"),
    ("FMP quote",                 "data"),
    ("GoogleNews:Reuters",        "commentary"),
    ("NewsAPI:AP News",           "commentary"),
    ("Central bank speech",       "data"),
    ("Unknown source xyz",        "news"),
])
def test_classify_chunk_type(source, expected):
    assert _classify_chunk_type(source) == expected


# ---------------------------------------------------------------------------
# _classify_authority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source,expected", [
    ("ASX announcement",         "primary"),
    ("RBA",                      "primary"),
    ("Federal Reserve FOMC",     "primary"),
    ("Independent Expert Report","primary"),
    ("Rule 2.7 announcement",    "primary"),
    ("GoogleNews:Reuters",       "secondary"),
    ("NewsAPI:AP News",          "secondary"),
    ("Company press release",    "secondary"),
])
def test_classify_authority(source, expected):
    assert _classify_authority(source) == expected


# ---------------------------------------------------------------------------
# _normalise_date
# ---------------------------------------------------------------------------

def test_normalise_date_iso():
    assert _normalise_date("2026-10-26") == "2026-10-26"


def test_normalise_date_iso_with_time():
    assert _normalise_date("2026-10-26T07:00:00Z") == "2026-10-26"


def test_normalise_date_rfc2822():
    result = _normalise_date("Mon, 26 Oct 2026 07:00:00 GMT")
    assert result == "2026-10-26"


def test_normalise_date_empty():
    assert _normalise_date("") == ""


def test_normalise_date_garbage():
    assert _normalise_date("not a date") == ""


# ---------------------------------------------------------------------------
# _trim
# ---------------------------------------------------------------------------

def test_trim_respects_config_limit():
    long_text = "x" * 100_000
    result = _trim(long_text)
    assert len(result) <= 8000  # matches config.yaml pipeline.doc_trim_chars


def test_trim_short_text_unchanged():
    short = "Hello world"
    assert _trim(short) == short


# ---------------------------------------------------------------------------
# build_deal_dossier — structure
# ---------------------------------------------------------------------------

def test_build_deal_dossier_returns_dossier():
    raw = [("ASX announcement", "BHP proposes A$50bn acquisition of Anglo American.")]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    assert isinstance(d, dict)
    assert d["topic"] == TOPIC
    assert d["report_type"] == "ma_full"
    assert d["date"] == DATE
    assert isinstance(d["documents"], list)
    assert d["market_data"] == {}


def test_build_deal_dossier_word_count_target():
    d = build_deal_dossier(TOPIC, "ma_full", DATE, [])
    assert d["word_count_target"] == WORD_COUNT_TARGETS["ma_full"]


def test_build_deal_dossier_ecm_target():
    d = build_deal_dossier("ECM deal", "ecm", DATE, [])
    assert d["word_count_target"] == WORD_COUNT_TARGETS["ecm"]


def test_build_deal_dossier_unknown_type_uses_other():
    d = build_deal_dossier("misc", "spin_off", DATE, [])
    assert d["word_count_target"] == WORD_COUNT_TARGETS["other"]


def test_build_deal_dossier_chunk_fields():
    raw = [("ASX announcement", "Deal text here")]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    chunk = d["documents"][0]
    assert chunk["source"] == "ASX announcement"
    assert chunk["type"] == "filing"
    assert chunk["authority"] == "primary"
    assert chunk["text"] == "Deal text here"


def test_build_deal_dossier_skips_empty_text():
    raw = [("ASX announcement", ""), ("Scheme booklet", "  "), ("RNS", "Valid text")]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    assert len(d["documents"]) == 1
    assert d["documents"][0]["source"] == "RNS"


def test_build_deal_dossier_multiple_chunks():
    raw = [
        ("ASX announcement", "Primary filing text."),
        ("GoogleNews:Reuters", "Reuters coverage."),
        ("FRED data", "Interest rate: 4.35%"),
    ]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    assert len(d["documents"]) == 3
    types = {c["type"] for c in d["documents"]}
    assert "filing" in types
    assert "commentary" in types
    assert "data" in types


def test_build_deal_dossier_text_trimmed():
    long_text = "A" * 100_000
    raw = [("ASX announcement", long_text)]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    assert len(d["documents"][0]["text"]) <= 8000


# ---------------------------------------------------------------------------
# build_deal_dossier — with news items
# ---------------------------------------------------------------------------

def test_build_deal_dossier_appends_news_items():
    news = [
        NewsItem(
            title="Acme Corp deal approved",
            url="https://reuters.com/article/acme",
            source="GoogleNews:Reuters",
            published="2026-10-26T07:00:00Z",
            snippet="Federal Court approved the scheme.",
        )
    ]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, [], news_items=news)
    assert len(d["documents"]) == 1
    chunk = d["documents"][0]
    assert "Acme Corp deal approved" in chunk["text"]
    assert chunk["authority"] == "secondary"
    assert chunk["type"] == "commentary"


def test_build_deal_dossier_news_item_date_normalised():
    news = [
        NewsItem(
            title="Title", url="https://x.com", source="GoogleNews:X",
            published="Mon, 26 Oct 2026 07:00:00 GMT", snippet="",
        )
    ]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, [], news_items=news)
    assert d["documents"][0]["date"] == "2026-10-26"


def test_build_deal_dossier_news_item_empty_snippet_uses_title():
    news = [NewsItem(title="Just a headline", url="https://x.com", source="NewsAPI:X", published="", snippet="")]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, [], news_items=news)
    assert d["documents"][0]["text"] == "Just a headline"


def test_build_deal_dossier_news_item_empty_title_and_snippet_skipped():
    news = [NewsItem(title="", url="https://x.com", source="NewsAPI:X", published="", snippet="")]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, [], news_items=news)
    assert len(d["documents"]) == 0


# ---------------------------------------------------------------------------
# build_market_dossier
# ---------------------------------------------------------------------------

def test_build_market_dossier_attaches_market_data():
    mdata = {"equities": "S&P 500: 5000 (+0.5%)", "bonds": "10Y: 4.42%"}
    d = build_market_dossier("economy", DATE, [], mdata)
    assert d["market_data"] == mdata


def test_build_market_dossier_report_type_preserved():
    d = build_market_dossier("equities", DATE, [], {})
    assert d["report_type"] == "equities"


def test_build_market_dossier_word_count_target():
    d = build_market_dossier("bonds", DATE, [], {})
    assert d["word_count_target"] == WORD_COUNT_TARGETS["bonds"]


def test_build_market_dossier_includes_raw_texts():
    raw = [("RBA decision page", "The RBA held rates at 4.35%.")]
    d = build_market_dossier("economy", DATE, raw, {})
    assert len(d["documents"]) == 1
    assert "RBA" in d["documents"][0]["source"]


# ---------------------------------------------------------------------------
# dossier_summary
# ---------------------------------------------------------------------------

def test_dossier_summary_returns_string():
    raw = [
        ("ASX announcement", "Filing text"),
        ("GoogleNews:Reuters", "News text"),
    ]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    summary = dossier_summary(d)
    assert isinstance(summary, str)
    assert TOPIC in summary
    assert "ma_full" in summary
    assert DATE in summary


def test_dossier_summary_chunk_counts():
    raw = [
        ("ASX announcement", "Filing"),
        ("FRED data", "Data"),
        ("GoogleNews:Reuters", "News 1"),
        ("NewsAPI:AP", "News 2"),
    ]
    d = build_deal_dossier(TOPIC, "ma_full", DATE, raw)
    summary = dossier_summary(d)
    assert "4 chunks" in summary


# ---------------------------------------------------------------------------
# WORD_COUNT_TARGETS sanity
# ---------------------------------------------------------------------------

def test_word_count_targets_all_report_types_present():
    for rt in ("ma_full", "ecm", "dcm", "economy", "equities", "commodities", "bonds", "currencies"):
        assert rt in WORD_COUNT_TARGETS
        assert WORD_COUNT_TARGETS[rt] >= 2000
