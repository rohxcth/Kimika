"""Tests for app/fetch.py — synthetic data only, no real network calls.

All HTTP is mocked with unittest.mock. The blocklist is read from config.yaml
so these tests also prove the config drives behaviour.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.fetch import (
    BlockedDomainError,
    _cache_get,
    _cache_path,
    _cache_set,
    _check_blocklist,
    clear_cache,
    fetch,
    fetch_json,
    is_blocked,
)


# ---------------------------------------------------------------------------
# Blocklist: every domain in config.yaml must be refused
# ---------------------------------------------------------------------------

MUST_BE_BLOCKED = [
    "https://www.afr.com/markets/deal",
    "https://afr.com/politics",
    "https://www.bloomberg.com/news/articles/123",
    "https://bloomberg.com/",
    "https://www.wsj.com/articles/something",
    "https://www.ft.com/content/abc",
    "https://ft.com/",
    "https://www.theaustralian.com.au/business",
    "https://www.mergermarket.com/deals",
    "https://www.pitchbook.com/",
    "https://www.capitaliq.com/",
    "https://www.refinitiv.com/",
    "https://markets.ft.com/data",          # subdomain of ft.com
    "https://sub.afr.com/something",        # subdomain of afr.com
]

MUST_BE_ALLOWED = [
    "https://www.asx.com.au/asx/1/announcement",
    "https://efts.sec.gov/LATEST/search-index",
    "https://data.sec.gov/submissions/CIK0001234567.json",
    "https://financialmodelingprep.com/api/v3/quote/AAPL",
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS",
    "https://www.rba.gov.au/statistics/tables/",
    "https://globenewswire.com/news-release/2026/10/26/1234",
    "https://www.businesswire.com/news/home/20261026005000",
]


@pytest.mark.parametrize("url", MUST_BE_BLOCKED)
def test_blocked_domains_raise(url):
    """Every paywalled domain must raise BlockedDomainError."""
    with pytest.raises(BlockedDomainError):
        _check_blocklist(url)


@pytest.mark.parametrize("url", MUST_BE_BLOCKED)
def test_is_blocked_true(url):
    assert is_blocked(url) is True


@pytest.mark.parametrize("url", MUST_BE_ALLOWED)
def test_allowed_domains_do_not_raise(url):
    _check_blocklist(url)   # must not raise


@pytest.mark.parametrize("url", MUST_BE_ALLOWED)
def test_is_blocked_false(url):
    assert is_blocked(url) is False


def test_afr_blocked_via_fetch():
    """The main fetch() entry point must also refuse AFR URLs."""
    with pytest.raises(BlockedDomainError):
        fetch("https://www.afr.com/markets/equities/bhp-deal-20261026")


def test_bloomberg_blocked_via_fetch():
    with pytest.raises(BlockedDomainError):
        fetch("https://bloomberg.com/news/articles/test")


# ---------------------------------------------------------------------------
# Successful fetch (mocked HTTP)
# ---------------------------------------------------------------------------

def _mock_response(text: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        import requests as _req
        resp.raise_for_status.side_effect = _req.HTTPError(response=resp)
    return resp


@patch("app.fetch.requests.get")
def test_fetch_returns_body(mock_get, tmp_path, monkeypatch):
    """fetch() returns the response body text."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    mock_get.return_value = _mock_response("<html>hello</html>")
    result = fetch("https://www.asx.com.au/test", use_cache=False)
    assert result == "<html>hello</html>"
    mock_get.assert_called_once()


@patch("app.fetch.requests.get")
def test_fetch_sets_user_agent(mock_get, tmp_path, monkeypatch):
    """fetch() always sends a User-Agent header."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    mock_get.return_value = _mock_response("ok")
    fetch("https://data.sec.gov/submissions/CIK0001234567.json", use_cache=False)
    _, kwargs = mock_get.call_args
    headers = kwargs.get("headers", {})
    assert "User-Agent" in headers
    assert headers["User-Agent"]  # non-empty


@patch("app.fetch.requests.get")
def test_fetch_raises_on_http_error(mock_get, tmp_path, monkeypatch):
    """fetch() propagates HTTPError on non-2xx responses."""
    import requests as _req
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    mock_get.return_value = _mock_response("not found", status=404)
    with pytest.raises(_req.HTTPError):
        fetch("https://www.asx.com.au/missing", use_cache=False)


@patch("app.fetch.requests.get")
def test_fetch_json_parses_response(mock_get, tmp_path, monkeypatch):
    """fetch_json() returns a parsed dict/list."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    mock_get.return_value = _mock_response('{"price": 4.10}')
    result = fetch_json("https://financialmodelingprep.com/api/v3/quote/BHP", use_cache=False)
    assert result == {"price": 4.10}


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------

def test_cache_set_and_get(tmp_path, monkeypatch):
    """_cache_set writes a file; _cache_get reads it back within TTL."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr("app.fetch._CACHE_TTL_SECONDS", 3600)
    url = "https://data.sec.gov/submissions/CIK0001234567.json"
    _cache_set(url, "body text")
    assert _cache_get(url) == "body text"


def test_cache_expired_returns_none(tmp_path, monkeypatch):
    """_cache_get returns None when the cached entry is older than the TTL."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr("app.fetch._CACHE_TTL_SECONDS", 1)
    url = "https://data.sec.gov/submissions/CIK0000000001.json"
    _cache_set(url, "stale body")

    # Backdate the cached file's fetched_at to 2 seconds ago
    path = _cache_path(url)
    data = json.loads(path.read_text())
    data["fetched_at"] = time.time() - 2
    path.write_text(json.dumps(data))

    assert _cache_get(url) is None


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    assert _cache_get("https://example.com/not-cached") is None


@patch("app.fetch.requests.get")
def test_fetch_uses_cache_on_second_call(mock_get, tmp_path, monkeypatch):
    """Second fetch() of the same URL uses the cache; no second HTTP call."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr("app.fetch._CACHE_TTL_SECONDS", 3600)
    mock_get.return_value = _mock_response("cached body")
    url = "https://www.asx.com.au/asx/1/announcement"

    first = fetch(url, use_cache=True)
    second = fetch(url, use_cache=True)

    assert first == second == "cached body"
    assert mock_get.call_count == 1   # only one real HTTP call


@patch("app.fetch.requests.get")
def test_fetch_bypasses_cache_when_disabled(mock_get, tmp_path, monkeypatch):
    """use_cache=False always hits the network."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    mock_get.return_value = _mock_response("fresh")
    url = "https://www.asx.com.au/asx/1/announcement"

    fetch(url, use_cache=False)
    fetch(url, use_cache=False)

    assert mock_get.call_count == 2


def test_clear_cache(tmp_path, monkeypatch):
    """clear_cache() removes all cached files and returns the count."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "cache")
    for i in range(3):
        _cache_set(f"https://example.com/{i}", f"body {i}")
    removed = clear_cache()
    assert removed == 3
    assert _cache_get("https://example.com/0") is None


def test_clear_cache_empty_dir(tmp_path, monkeypatch):
    """clear_cache() on an empty/nonexistent cache dir returns 0."""
    monkeypatch.setattr("app.fetch._CACHE_DIR", tmp_path / "no-cache")
    assert clear_cache() == 0
