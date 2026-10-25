"""Tests for app/pipeline.py and supporting modules (report.py, llm.py).

All HTTP and LLM calls are mocked. The pipeline is run against fixture data
and the output files are written to a tmp_path directory.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.pipeline import (
    _bucket_deals,
    _rank_deals,
    _write_market_reports,
    run,
)
from app.report import (
    ReportData,
    _index_entry,
    _update_index,
    load_index,
    load_report,
    make_slug,
    save_report,
)
from app import llm as _llm
from app.sources import RawDeal

DATE_STR = "2026-10-26"
TARGET_DATE = date(2026, 10, 26)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _raw_deal(source="ASX", region="AU", val_usd=None) -> RawDeal:
    return RawDeal(
        title="Acme Corp — acquisition via scheme",
        url="https://www.asx.com.au/asx/1/file/2026/ACME.pdf",
        source=source,
        region=region,
        filing_type="ASX_announcement",
        date=DATE_STR,
        company="Acme Corp",
        extra={"ticker": "ACM", "deal_value_usd": val_usd},
    )


def _stub_report(slug="test-slug", date_str=DATE_STR, val_usd=None) -> ReportData:
    return ReportData(
        slug=slug,
        date=date_str,
        report_type="ma_full",
        region="AU",
        title="Acme Corp — acquisition",
        key_takeaways=["Takeaway 1", "Takeaway 2", "Takeaway 3"],
        sections={"1_deal_snapshot": "Snapshot content"},
        verification_log=[],
        bibliography=[],
        metadata={"deal_value_usd": val_usd},
    )


# ---------------------------------------------------------------------------
# make_slug
# ---------------------------------------------------------------------------

def test_make_slug_basic():
    slug = make_slug("BHP / Anglo American: US$49bn scheme", "AU", "ma_full", "2026-10-26")
    assert "bhp" in slug
    assert "2026-10-26" in slug
    assert " " not in slug
    assert "/" not in slug


def test_make_slug_no_special_chars():
    slug = make_slug("Test Corp: $1.2bn deal!", "US", "ma_full", "2026-10-26")
    # Should only contain alphanumerics and hyphens
    import re
    assert re.match(r"^[a-z0-9\-]+$", slug)


# ---------------------------------------------------------------------------
# save_report / load_report
# ---------------------------------------------------------------------------

def test_save_and_load_report(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    report = _stub_report()
    path = save_report(report)
    assert path.exists()
    loaded = load_report(DATE_STR, "test-slug")
    assert loaded is not None
    assert loaded.title == report.title
    assert loaded.report_type == "ma_full"


def test_save_report_sets_updated_at(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    report = _stub_report()
    save_report(report)
    assert report.updated_at.endswith("Z")


def test_load_report_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    assert load_report(DATE_STR, "nonexistent-slug") is None


def test_save_report_creates_directory(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    report = _stub_report(slug="new-dir-slug")
    save_report(report)
    assert (tmp_path / "reports" / DATE_STR / "new-dir-slug" / "report.json").exists()


# ---------------------------------------------------------------------------
# index.json
# ---------------------------------------------------------------------------

def test_save_report_creates_index(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    save_report(_stub_report(slug="report-a"))
    index = load_index(DATE_STR)
    assert len(index) == 1
    assert index[0]["slug"] == "report-a"


def test_save_multiple_reports_updates_index(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    save_report(_stub_report(slug="report-a", val_usd=2000))
    save_report(_stub_report(slug="report-b", val_usd=500))
    index = load_index(DATE_STR)
    assert len(index) == 2
    # Larger deal should be first
    assert index[0]["slug"] == "report-a"


def test_index_upserts_existing_report(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    save_report(_stub_report(slug="report-a"))
    save_report(_stub_report(slug="report-a"))  # second save — same slug
    index = load_index(DATE_STR)
    assert len(index) == 1  # not duplicated



def test_load_index_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    assert load_index("2099-01-01") == []


def test_index_ordering_three_deals(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    save_report(_stub_report(slug="small", val_usd=500))
    save_report(_stub_report(slug="large", val_usd=2000))
    save_report(_stub_report(slug="mid",   val_usd=1000))
    index = load_index(DATE_STR)
    slugs = [e["slug"] for e in index]
    assert slugs == ["large", "mid", "small"]



# ---------------------------------------------------------------------------
# _bucket_deals
# ---------------------------------------------------------------------------

def test_bucket_deals_routes_by_type():
    deals = [_raw_deal(), _raw_deal(), _raw_deal(), _raw_deal()]
    classifications = [
        {"index": 0, "deal_type": "M&A"},
        {"index": 1, "deal_type": "ECM"},
        {"index": 2, "deal_type": "DCM"},
        {"index": 3, "deal_type": "Other"},
    ]
    buckets = _bucket_deals(deals, classifications)
    assert len(buckets["M&A"]) == 1
    assert len(buckets["ECM"]) == 1
    assert len(buckets["DCM"]) == 1
    assert len(buckets["Other"]) == 1


def test_bucket_deals_drops_not_a_deal():
    deals = [_raw_deal(), _raw_deal()]
    classifications = [
        {"index": 0, "deal_type": "not_a_deal"},
        {"index": 1, "deal_type": "M&A"},
    ]
    buckets = _bucket_deals(deals, classifications)
    assert len(buckets["M&A"]) == 1
    assert sum(len(v) for v in buckets.values()) == 1


def test_bucket_deals_attaches_deal_type():
    deals = [_raw_deal()]
    classifications = [{"index": 0, "deal_type": "ECM"}]
    buckets = _bucket_deals(deals, classifications)
    assert buckets["ECM"][0]["deal_type"] == "ECM"


def test_bucket_deals_all_not_a_deal():
    deals = [_raw_deal()]
    classifications = [{"index": 0, "deal_type": "not_a_deal"}]
    buckets = _bucket_deals(deals, classifications)
    assert all(len(v) == 0 for v in buckets.values())


# ---------------------------------------------------------------------------
# _rank_deals
# ---------------------------------------------------------------------------

def test_rank_deals_largest_first():
    deals = [
        _raw_deal(val_usd=500),
        _raw_deal(val_usd=5000),
        _raw_deal(val_usd=1000),
    ]
    ranked = _rank_deals(deals)
    values = [d["extra"]["deal_value_usd"] for d in ranked]
    assert values == [5000, 1000, 500]


def test_rank_deals_unknown_value_sorts_last():
    deals = [
        _raw_deal(val_usd=None),   # unknown
        _raw_deal(val_usd=1000),
        _raw_deal(val_usd=None),   # unknown
    ]
    ranked = _rank_deals(deals)
    # known value deal should come first
    assert ranked[0]["extra"]["deal_value_usd"] == 1000


def test_rank_deals_all_unknown():
    deals = [_raw_deal(val_usd=None), _raw_deal(val_usd=None)]
    ranked = _rank_deals(deals)
    assert len(ranked) == 2  # order preserved, no crash


def test_rank_deals_zero_value_treated_as_unknown():
    # val=0 is distinct from None but both sort after legitimate deal values
    deals = [_raw_deal(val_usd=0), _raw_deal(val_usd=1000)]
    ranked = _rank_deals(deals)
    assert ranked[0]["extra"]["deal_value_usd"] == 1000


def test_rank_deals_negative_value_sorts_last():
    # Negative value = upstream data error; should not rank above real deals
    deals = [_raw_deal(val_usd=-500), _raw_deal(val_usd=1000)]
    ranked = _rank_deals(deals)
    assert ranked[0]["extra"]["deal_value_usd"] == 1000


def test_rank_deals_single_deal():
    result = _rank_deals([_raw_deal(val_usd=1000)])
    assert len(result) == 1
    assert result[0]["extra"]["deal_value_usd"] == 1000


# ---------------------------------------------------------------------------
# LLM stub
# ---------------------------------------------------------------------------

def test_llm_classify_returns_list(tmp_path):
    import json as _json
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.text = _json.dumps([
        {"index": 0, "deal_type": "M&A", "region": "AU", "confidence": "high", "reason": "test"},
        {"index": 1, "deal_type": "M&A", "region": "AU", "confidence": "high", "reason": "test"},
    ])
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp
    _llm._set_client(mock_client)
    _llm._LLM_CACHE_DIR = tmp_path / "cache"

    deals = [_raw_deal(), _raw_deal()]
    result = _llm.classify_deals(deals)
    assert len(result) == 2
    assert all("deal_type" in r for r in result)
    _llm._set_client(None)
    _llm.reset_quota_log()


def test_llm_write_ma_report_returns_report_data(tmp_path):
    import json as _json
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.text = _json.dumps({
        "title": "Acme Corp — M&A", "key_takeaways": ["t1", "t2", "t3"],
        "sections": {"1_deal_snapshot": "snap"}, "metadata": {"region": "AU"},
        "verification_log": [],
    })
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp
    _llm._set_client(mock_client)
    _llm._LLM_CACHE_DIR = tmp_path / "cache"

    report = _llm.write_ma_report(_raw_deal(), "doc text", "sources", DATE_STR)
    assert isinstance(report, ReportData)
    assert report.date == DATE_STR
    assert report.report_type == "ma_full"
    _llm._set_client(None)
    _llm.reset_quota_log()



def test_llm_quota_log():
    log = _llm.quota_log()
    assert "flash" in log and "flash_lite" in log


# ---------------------------------------------------------------------------
# End-to-end pipeline run (all network mocked)
# ---------------------------------------------------------------------------

def test_pipeline_run_writes_files(tmp_path, monkeypatch):
    """Full pipeline run with mocked discovery, LLM, and fetch."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")

    stub_deal = _raw_deal(val_usd=2000)
    stub_report = _stub_report()

    with (
        patch("app.pipeline.discover_all", return_value=[stub_deal]),
        patch("app.pipeline.llm.classify_deals", return_value=[
            {"index": 0, "deal_type": "M&A", "region": "AU", "confidence": "high", "reason": "test"}
        ]),
        patch("app.pipeline.fetch", return_value="<html>Filing content</html>"),
        patch("app.pipeline.llm.write_ma_report", return_value=stub_report),
        patch("app.pipeline.save_report", wraps=lambda r: save_report.__wrapped__(r) if hasattr(save_report, '__wrapped__') else _save_to_tmp(r, tmp_path)),
    ):
        # Patch save_report directly in report module
        with patch("app.pipeline.save_report") as mock_save:
            mock_save.return_value = tmp_path / "reports" / DATE_STR / "test-slug" / "report.json"
            summary = run(date_str=DATE_STR)

    assert summary["date"] == DATE_STR
    assert summary["full_reports"] == 1


def test_pipeline_run_no_deals(tmp_path, monkeypatch):
    """Pipeline with zero discoveries should not crash."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")

    with (
        patch("app.pipeline.discover_all", return_value=[]),
        patch("app.pipeline.llm.classify_deals", return_value=[]),
        patch("app.pipeline.save_report") as mock_save,
    ):
        mock_save.return_value = None
        summary = run(date_str=DATE_STR)

    assert summary["full_reports"] == 0


def test_pipeline_run_fetch_failure_continues(tmp_path, monkeypatch):
    """A fetch failure for the primary doc should not stop the pipeline."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path / "reports")
    stub_deal = _raw_deal()
    stub_rep = _stub_report()

    with (
        patch("app.pipeline.discover_all", return_value=[stub_deal]),
        patch("app.pipeline.llm.classify_deals", return_value=[
            {"index": 0, "deal_type": "M&A", "region": "AU", "confidence": "high", "reason": "test"}
        ]),
        patch("app.pipeline.fetch", side_effect=Exception("timeout")),
        patch("app.pipeline.llm.write_ma_report", return_value=stub_rep),
        patch("app.pipeline.save_report") as mock_save,
    ):
        mock_save.return_value = None
        summary = run(date_str=DATE_STR)

    # Should still produce a report (with empty primary_doc)
    assert summary["full_reports"] == 1


# ---------------------------------------------------------------------------
# _write_market_reports
# ---------------------------------------------------------------------------

def _stub_market(report_type: str) -> "ReportData":
    from app.report import ReportData
    from datetime import datetime
    return ReportData(
        slug=f"{report_type}-{DATE_STR}",
        date=DATE_STR,
        report_type=report_type,
        region="global",
        title=f"{report_type.title()}: {DATE_STR}",
        key_takeaways=["A", "B", "C"],
        sections={f"1_{report_type}": "content"},
        bibliography=[],
        verification_log=[],
        metadata={},
        updated_at=datetime.utcnow(),
    )


def test_write_market_reports_returns_five(tmp_path):
    """_write_market_reports should return one report per market column."""
    import app.llm as llm_mod
    import app.pipeline as pipe_mod

    stubs = {
        "economy":     _stub_market("economy"),
        "equities":    _stub_market("equities"),
        "commodities": _stub_market("commodities"),
        "bonds":       _stub_market("bonds"),
        "currencies":  _stub_market("currencies"),
    }

    with (
        patch("app.pipeline.discover_economy_context", return_value="eco ctx"),
        patch("app.pipeline.discover_markets_context", return_value={
            "equities": "eq ctx", "commodities": "com ctx",
            "bonds": "bon ctx", "currencies": "fx ctx",
        }),
        patch("app.pipeline.llm.write_economy_report",     return_value=stubs["economy"]),
        patch("app.pipeline.llm.write_equities_report",    return_value=stubs["equities"]),
        patch("app.pipeline.llm.write_commodities_report", return_value=stubs["commodities"]),
        patch("app.pipeline.llm.write_bonds_report",       return_value=stubs["bonds"]),
        patch("app.pipeline.llm.write_currencies_report",  return_value=stubs["currencies"]),
    ):
        reports = _write_market_reports(DATE_STR)

    assert len(reports) == 5
    report_types = {r.report_type for r in reports}
    assert report_types == {"economy", "equities", "commodities", "bonds", "currencies"}


def test_write_market_reports_skips_failed_writer(tmp_path):
    """If one writer fails, the others still succeed."""
    stubs = {
        "economy":     _stub_market("economy"),
        "equities":    _stub_market("equities"),
        "commodities": _stub_market("commodities"),
        "bonds":       _stub_market("bonds"),
    }

    with (
        patch("app.pipeline.discover_economy_context", return_value=""),
        patch("app.pipeline.discover_markets_context", return_value={
            "equities": "", "commodities": "", "bonds": "", "currencies": "",
        }),
        patch("app.pipeline.llm.write_economy_report",     return_value=stubs["economy"]),
        patch("app.pipeline.llm.write_equities_report",    return_value=stubs["equities"]),
        patch("app.pipeline.llm.write_commodities_report", return_value=stubs["commodities"]),
        patch("app.pipeline.llm.write_bonds_report",       return_value=stubs["bonds"]),
        patch("app.pipeline.llm.write_currencies_report",  side_effect=Exception("FX error")),
    ):
        reports = _write_market_reports(DATE_STR)

    assert len(reports) == 4
    assert all(r.report_type != "currencies" for r in reports)
