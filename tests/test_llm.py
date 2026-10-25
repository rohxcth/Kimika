"""Tests for app/llm.py — no real Gemini calls, no API key needed.

All tests mock the Gemini client via app.llm._set_client(). This exercises
the quota guard, 429 back-off, response caching, JSON parsing, and fallback
logic without spending any quota.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import app.llm as llm_mod
from app.llm import (
    _build_report_from_json,
    _call,
    _cache_get,
    _cache_set,
    _extract_json,
    _stub_classification,
    _stub_ma_report,
    classify_deals,
    quota_log,
    reset_quota_log,
    write_deal_wrap,
    write_ma_report,
)
from app.report import ReportData
from app.sources import RawDeal

DATE_STR = "2026-10-26"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_deal(source="ASX", region="AU") -> dict:
    return {
        "title": "Acme Corp — scheme of arrangement",
        "url": "https://www.asx.com.au/asx/1/file/2026/ACME.pdf",
        "source": source,
        "region": region,
        "filing_type": "ASX_announcement",
        "date": DATE_STR,
        "company": "Acme Corp",
        "extra": {},
    }


def _make_mock_client(response_text: str):
    """Return a mock Gemini client whose generate_content returns response_text."""
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    """Reset quota counters and LLM client before each test."""
    reset_quota_log()
    llm_mod._set_client(None)
    # Redirect LLM cache to tmp_path so tests don't pollute real cache
    original = llm_mod._LLM_CACHE_DIR
    llm_mod._LLM_CACHE_DIR = tmp_path / "llm_cache"
    yield
    llm_mod._LLM_CACHE_DIR = original
    llm_mod._set_client(None)
    reset_quota_log()


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

def test_extract_json_clean():
    assert _extract_json('{"key": "value"}') == {"key": "value"}


def test_extract_json_fenced():
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_fenced_no_lang():
    text = '```\n{"key": "value"}\n```'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_array():
    assert _extract_json('[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]


def test_extract_json_embedded():
    text = 'Here is the result:\n{"key": "val"}\nDone.'
    result = _extract_json(text)
    assert result == {"key": "val"}


def test_extract_json_invalid_returns_none():
    assert _extract_json("this is not json") is None


def test_extract_json_none_returns_none():
    assert _extract_json(None) is None


# ---------------------------------------------------------------------------
# LLM cache
# ---------------------------------------------------------------------------

def test_cache_set_and_get(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    _cache_set("my prompt", "response text")
    assert _cache_get("my prompt") == "response text"


def test_cache_miss_returns_none(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    assert _cache_get("never cached") is None


def test_cache_expired_returns_none(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    _cache_set("prompt", "old response")
    # Backdate the cache file
    from app.llm import _cache_path
    path = _cache_path("prompt")
    data = json.loads(path.read_text())
    data["cached_at"] = time.time() - (llm_mod._CACHE_TTL + 10)
    path.write_text(json.dumps(data))
    assert _cache_get("prompt") is None


# ---------------------------------------------------------------------------
# Quota guard
# ---------------------------------------------------------------------------

def test_quota_guard_blocks_when_cap_reached(tmp_path):
    """_call returns None (not an error) when the quota cap is reached."""
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    # Exhaust the flash_lite quota
    llm_mod._request_counts["flash_lite"] = llm_mod._FLASH_LITE_CAP
    mock_client = _make_mock_client('{"result": "ok"}')
    llm_mod._set_client(mock_client)

    result = _call(llm_mod._FLASH_LITE, "flash_lite", "test prompt")
    assert result is None
    # No API call should have been made
    mock_client.models.generate_content.assert_not_called()


def test_quota_increments_on_success(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = _make_mock_client('{"ok": true}')
    llm_mod._set_client(mock_client)

    before = llm_mod._request_counts["flash_lite"]
    _call(llm_mod._FLASH_LITE, "flash_lite", "prompt A")
    assert llm_mod._request_counts["flash_lite"] == before + 1


def test_quota_log_returns_counts():
    log = quota_log()
    assert "flash" in log and "flash_lite" in log
    assert isinstance(log["flash"], int)


# ---------------------------------------------------------------------------
# 429 back-off
# ---------------------------------------------------------------------------

def test_429_retries_and_succeeds(tmp_path):
    """On a 429, _call waits and retries; succeeds on second attempt."""
    from google.genai.errors import ClientError

    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"

    # First call raises 429; second call succeeds
    mock_response = MagicMock()
    mock_response.text = '{"ok": true}'
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        ClientError(429, {"error": {"code": 429, "message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}),
        mock_response,
    ]
    llm_mod._set_client(mock_client)

    with patch("app.llm.time.sleep") as mock_sleep:
        result = _call(llm_mod._FLASH_LITE, "flash_lite", "prompt")

    assert result == '{"ok": true}'
    assert mock_sleep.call_count == 1  # slept once before retry
    assert mock_client.models.generate_content.call_count == 2


def test_429_max_retries_returns_none(tmp_path):
    """After max retries, _call returns None (never raises)."""
    from google.genai.errors import ClientError

    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    llm_mod._set_client(mock_client)

    with patch("app.llm.time.sleep"):
        result = _call(llm_mod._FLASH_LITE, "flash_lite", "prompt")

    assert result is None
    assert mock_client.models.generate_content.call_count == llm_mod._MAX_RETRIES + 1


def test_non_429_error_returns_none_immediately(tmp_path):
    """A non-429 error (e.g. 500) returns None without retrying."""
    from google.genai.errors import ServerError

    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ServerError(
        500, {"error": {"code": 500, "message": "internal", "status": "INTERNAL"}}
    )
    llm_mod._set_client(mock_client)

    with patch("app.llm.time.sleep") as mock_sleep:
        result = _call(llm_mod._FLASH_LITE, "flash_lite", "prompt")

    assert result is None
    assert mock_sleep.call_count == 0       # no retry for non-429
    assert mock_client.models.generate_content.call_count == 1


# ---------------------------------------------------------------------------
# Cache hit avoids API call
# ---------------------------------------------------------------------------

def test_cache_hit_skips_api_call(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    _cache_set("cached prompt", "cached response")

    mock_client = _make_mock_client("fresh response")
    llm_mod._set_client(mock_client)

    result = _call(llm_mod._FLASH_LITE, "flash_lite", "cached prompt")
    assert result == "cached response"
    mock_client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# classify_deals
# ---------------------------------------------------------------------------

CLASSIFY_RESPONSE = json.dumps([
    {"index": 0, "deal_type": "M&A", "region": "AU", "confidence": "high", "reason": "ASX scheme"},
    {"index": 1, "deal_type": "ECM", "region": "AU", "confidence": "high", "reason": "placement"},
])


def test_classify_deals_success(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = _make_mock_client(CLASSIFY_RESPONSE)
    llm_mod._set_client(mock_client)

    deals = [_raw_deal(), _raw_deal(source="ASX")]
    result = classify_deals(deals)
    assert len(result) == 2
    assert result[0]["deal_type"] == "M&A"
    assert result[1]["deal_type"] == "ECM"


def test_classify_deals_empty():
    result = classify_deals([])
    assert result == []


def test_classify_deals_falls_back_to_stub_on_api_failure(tmp_path):
    """If Gemini fails, classify_deals returns keyword-based stub results."""
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("network error")
    llm_mod._set_client(mock_client)

    deals = [_raw_deal()]
    result = classify_deals(deals)
    assert len(result) == 1
    assert result[0]["deal_type"] == "M&A"   # keyword stub picks up ASX_announcement


def test_classify_deals_falls_back_on_malformed_json(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = _make_mock_client("not json at all")
    llm_mod._set_client(mock_client)

    deals = [_raw_deal()]
    result = classify_deals(deals)
    assert len(result) == 1
    assert "deal_type" in result[0]


# ---------------------------------------------------------------------------
# write_ma_report
# ---------------------------------------------------------------------------

MA_RESPONSE = json.dumps({
    "title": "Acme Corp / Beta Ltd: A$2bn scheme",
    "key_takeaways": ["Deal announced", "Board recommends", "Completion expected Q1 2027"],
    "sections": {
        "1_deal_snapshot": "Snapshot table here.",
        "2_strategic_rationale": "Strategic logic here.",
        "3_process_and_negotiations": "Timeline here.",
        "4_valuation": "Valuation here.",
        "5_structure_terms_financing": "Structure here.",
        "6_advisers": "Advisers here.",
        "7_market_view": "Market view here.",
        "8_outlook_and_scenarios": "Outlook here.",
        "9_bibliography": [
            {"title": "ASX Announcement", "publisher": "ASX", "date": DATE_STR,
             "url": "https://www.asx.com.au/...", "category": "Filings & announcements"}
        ],
    },
    "metadata": {
        "acquirer": "Beta Ltd", "target": "Acme Corp",
        "deal_value_usd": 1300, "structure": "scheme",
        "region": "AU", "status": "announced",
    },
    "verification_log": [],
})


def test_write_ma_report_success(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = _make_mock_client(MA_RESPONSE)
    llm_mod._set_client(mock_client)

    deal = _raw_deal()
    report = write_ma_report(deal, "Primary doc text", "Secondary sources", DATE_STR)

    assert isinstance(report, ReportData)
    assert report.report_type == "ma_full"
    assert "Acme Corp" in report.title
    assert len(report.key_takeaways) == 3
    assert len(report.bibliography) == 1
    assert "1_deal_snapshot" in report.sections
    assert "9_bibliography" not in report.sections  # moved to bibliography field


def test_write_ma_report_increments_flash_quota(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = _make_mock_client(MA_RESPONSE)
    llm_mod._set_client(mock_client)

    before = llm_mod._request_counts["flash"]
    write_ma_report(_raw_deal(), "doc", "sources", DATE_STR)
    assert llm_mod._request_counts["flash"] == before + 1


def test_write_ma_report_falls_back_to_stub_on_failure(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("error")
    llm_mod._set_client(mock_client)

    report = write_ma_report(_raw_deal(), "doc", "sources", DATE_STR)
    assert isinstance(report, ReportData)
    assert "Stub" in report.key_takeaways[0]


# ---------------------------------------------------------------------------
# write_deal_wrap
# ---------------------------------------------------------------------------

WRAP_RESPONSE = json.dumps([
    {"region": "AU", "deal_type": "M&A", "parties": "Acme Corp",
     "size": "A$2bn", "key_term": "A$4.10 cash", "status": "Announced",
     "context_line": "Board recommends acceptance."},
])


def test_write_deal_wrap_success(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = _make_mock_client(WRAP_RESPONSE)
    llm_mod._set_client(mock_client)

    result = write_deal_wrap([_raw_deal()], DATE_STR)
    assert len(result) == 1
    assert result[0]["region"] == "AU"
    assert result[0]["size"] == "A$2bn"


def test_write_deal_wrap_empty():
    result = write_deal_wrap([], DATE_STR)
    assert result == []


def test_write_deal_wrap_falls_back_to_stub_on_failure(tmp_path):
    llm_mod._LLM_CACHE_DIR = tmp_path / "cache"
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("error")
    llm_mod._set_client(mock_client)

    result = write_deal_wrap([_raw_deal()], DATE_STR)
    assert len(result) == 1
    assert result[0]["parties"] == "Acme Corp"


# ---------------------------------------------------------------------------
# _build_report_from_json
# ---------------------------------------------------------------------------

def test_build_report_from_json():
    data = json.loads(MA_RESPONSE)
    deal = _raw_deal()
    report = _build_report_from_json(data, deal, DATE_STR)
    assert report.report_type == "ma_full"
    assert report.metadata["deal_value_usd"] == 1300
    assert "9_bibliography" not in report.sections
    assert len(report.bibliography) == 1


def test_build_report_slug_is_safe():
    data = json.loads(MA_RESPONSE)
    report = _build_report_from_json(data, _raw_deal(), DATE_STR)
    import re
    assert re.match(r"^[a-z0-9\-]+$", report.slug)
