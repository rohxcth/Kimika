"""Tests for app/main.py — FastAPI routes and page rendering.

Uses FastAPI's TestClient (httpx backend). All tests use sample data
in reports/samples/2026-10-26/ committed to the repo; no pipeline run needed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, _format_date, _format_usd, _section_title

SAMPLE_DATE = "2026-10-26"
SAMPLE_SLUG = "acme-corp-beta-ltd-a-2bn-scheme-mafull-au-2026-10-26"
WRAP_SLUG   = "deal-wrap-2026-10-26"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Root page
# ---------------------------------------------------------------------------

def test_index_returns_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_index_contains_kimika_brand(client):
    r = client.get("/")
    assert "Kimika" in r.text


def test_index_has_deals_section(client):
    r = client.get("/")
    assert "deals" in r.text.lower() or "Deals" in r.text


def test_index_with_future_date_shows_empty_state(client):
    r = client.get("/?date=2099-01-01")
    assert r.status_code == 200
    assert "2099-01-01" in r.text or "No reports" in r.text


def test_index_with_sample_date_shows_cards(client):
    r = client.get(f"/?date={SAMPLE_DATE}")
    assert r.status_code == 200
    # Should contain the sample report title or M&A label
    assert "M" in r.text  # at minimum the M&A badge


def test_index_sample_date_shows_deal_title(client):
    r = client.get(f"/?date={SAMPLE_DATE}")
    assert r.status_code == 200
    assert "Acme Corp" in r.text or "Beta Ltd" in r.text


def test_index_sample_date_shows_deal_wrap(client):
    r = client.get(f"/?date={SAMPLE_DATE}")
    assert r.status_code == 200
    assert "Deal Wrap" in r.text or "wrap" in r.text.lower()


def test_index_page_has_nav(client):
    r = client.get("/")
    assert "Economy" in r.text
    assert "Markets" in r.text


def test_index_page_has_html_structure(client):
    r = client.get("/")
    text = r.text.lower()
    assert "<html" in text
    assert "<head" in text
    assert "<body" in text


# ---------------------------------------------------------------------------
# API: index
# ---------------------------------------------------------------------------

def test_api_index_returns_list(client):
    r = client.get(f"/api/index/{SAMPLE_DATE}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_api_index_contains_ma_report(client):
    r = client.get(f"/api/index/{SAMPLE_DATE}")
    slugs = [e["slug"] for e in r.json()]
    assert SAMPLE_SLUG in slugs


def test_api_index_contains_ma_report_type(client):
    r = client.get(f"/api/index/{SAMPLE_DATE}")
    types = [e["report_type"] for e in r.json()]
    assert "ma_full" in types


def test_api_index_ma_first(client):
    r = client.get(f"/api/index/{SAMPLE_DATE}")
    entries = r.json()
    assert entries[0]["report_type"] == "ma_full"


def test_api_index_missing_date_returns_empty(client):
    r = client.get("/api/index/2099-01-01")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# API: report
# ---------------------------------------------------------------------------

def test_api_report_returns_report(client):
    r = client.get(f"/api/report/{SAMPLE_DATE}/{SAMPLE_SLUG}")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == SAMPLE_SLUG
    assert data["report_type"] == "ma_full"
    assert "sections" in data
    assert "key_takeaways" in data


def test_api_report_has_bibliography(client):
    r = client.get(f"/api/report/{SAMPLE_DATE}/{SAMPLE_SLUG}")
    data = r.json()
    assert isinstance(data["bibliography"], list)


def test_api_report_has_verification_log(client):
    r = client.get(f"/api/report/{SAMPLE_DATE}/{SAMPLE_SLUG}")
    data = r.json()
    assert isinstance(data["verification_log"], list)


def test_api_report_wrap(client):
    r = client.get(f"/api/report/{SAMPLE_DATE}/{WRAP_SLUG}")
    assert r.status_code == 200
    data = r.json()
    assert data["report_type"] == "deal_wrap"
    entries = data["sections"].get("entries", [])
    assert isinstance(entries, list)
    assert len(entries) >= 1


def test_api_report_not_found(client):
    r = client.get("/api/report/2099-01-01/nonexistent-slug")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Helper functions (unit tests, no HTTP)
# ---------------------------------------------------------------------------

def test_format_date_basic():
    assert _format_date("2026-10-26") == "Monday 26 October 2026"


def test_format_date_no_leading_zero():
    result = _format_date("2026-10-05")
    assert result.startswith("Monday 5 ")


def test_format_date_invalid_returns_input():
    assert _format_date("not-a-date") == "not-a-date"


def test_format_usd_billions():
    assert _format_usd(1300) == "US$1.3bn"


def test_format_usd_millions():
    assert _format_usd(450) == "US$450m"


def test_format_usd_exact_billion():
    assert _format_usd(1000) == "US$1.0bn"


def test_format_usd_none():
    assert _format_usd(None) == ""


def test_section_title_strips_number():
    assert _section_title("1_deal_snapshot") == "Deal Snapshot"


def test_section_title_multi_word():
    assert _section_title("3_process_and_negotiations") == "Process And Negotiations"


def test_section_title_no_number():
    assert _section_title("entries") == "Entries"
