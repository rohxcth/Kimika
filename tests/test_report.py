"""Tests for app/report.py — persistence, version history, index entry."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.report import ReportData, _archive_version, _index_entry, load_index, load_report, make_slug, save_report


DATE_STR = "2026-10-26"


def _make_report(slug: str = "test-deal-mafull-au-2026-10-26", version: int = 1) -> ReportData:
    return ReportData(
        slug=slug,
        date=DATE_STR,
        report_type="ma_full",
        region="AU",
        title=f"Test Deal v{version}",
        key_takeaways=[f"Takeaway v{version}", "B", "C"],
        sections={"1_deal": f"Content v{version}"},
        verification_log=[],
        bibliography=[],
        metadata={"deal_value_usd": 500},
        updated_at="",
    )


# ---------------------------------------------------------------------------
# make_slug
# ---------------------------------------------------------------------------

def test_make_slug_produces_safe_string():
    slug = make_slug("BHP / Anglo American: US$49bn scheme", "AU", "ma_full", DATE_STR)
    assert " " not in slug
    assert slug == slug.lower()
    assert DATE_STR in slug


def test_make_slug_max_length():
    slug = make_slug("A" * 100, "AU", "ma_full", DATE_STR)
    assert len(slug) <= 65  # 40 chars clean + suffix (~25 chars)


# ---------------------------------------------------------------------------
# save_report — first save
# ---------------------------------------------------------------------------

def test_save_report_creates_files(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)
    report = _make_report()
    path = save_report(report)

    assert path.exists()
    data = json.loads(path.read_text())
    assert data["slug"] == report.slug
    assert data["title"] == "Test Deal v1"
    assert data["updated_at"] != ""


def test_save_report_creates_index(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)
    save_report(_make_report())

    index = load_index(DATE_STR)
    assert len(index) == 1
    assert index[0]["slug"] == "test-deal-mafull-au-2026-10-26"


def test_first_save_no_versions_dir(tmp_path, monkeypatch):
    """First save should not create a versions/ directory."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)
    save_report(_make_report())

    versions_dir = tmp_path / DATE_STR / "test-deal-mafull-au-2026-10-26" / "versions"
    assert not versions_dir.exists()


# ---------------------------------------------------------------------------
# save_report — second save (version archiving)
# ---------------------------------------------------------------------------

def test_second_save_archives_old_version(tmp_path, monkeypatch):
    """Saving a report twice should archive the first version in versions/."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)

    v1 = _make_report(version=1)
    save_report(v1)

    v2 = _make_report(version=2)
    save_report(v2)

    versions_dir = tmp_path / DATE_STR / v1.slug / "versions"
    assert versions_dir.exists()
    archived = list(versions_dir.glob("*.json"))
    assert len(archived) == 1

    # Archived file should contain v1 content
    old = json.loads(archived[0].read_text())
    assert old["title"] == "Test Deal v1"


def test_second_save_current_is_latest(tmp_path, monkeypatch):
    """After two saves, report.json should contain the latest version."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)

    save_report(_make_report(version=1))
    save_report(_make_report(version=2))

    report = load_report(DATE_STR, "test-deal-mafull-au-2026-10-26")
    assert report.title == "Test Deal v2"


def test_three_saves_two_archived_versions(tmp_path, monkeypatch):
    """Three saves should produce two archived versions."""
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)

    for v in [1, 2, 3]:
        save_report(_make_report(version=v))

    versions_dir = tmp_path / DATE_STR / "test-deal-mafull-au-2026-10-26" / "versions"
    assert len(list(versions_dir.glob("*.json"))) == 2


# ---------------------------------------------------------------------------
# version_count in index entry
# ---------------------------------------------------------------------------

def test_index_entry_version_count_zero_on_first_save(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)
    save_report(_make_report())

    index = load_index(DATE_STR)
    assert index[0]["version_count"] == 0


def test_index_entry_version_count_increments(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)

    save_report(_make_report(version=1))
    save_report(_make_report(version=2))

    index = load_index(DATE_STR)
    assert index[0]["version_count"] == 1

    save_report(_make_report(version=3))
    index = load_index(DATE_STR)
    assert index[0]["version_count"] == 2


# ---------------------------------------------------------------------------
# _archive_version resilience
# ---------------------------------------------------------------------------

def test_archive_version_handles_corrupt_file(tmp_path):
    """_archive_version should not raise even if the existing file is unreadable."""
    report_path = tmp_path / "report.json"
    report_path.write_text("not valid json")
    # Should not raise
    _archive_version(report_path, tmp_path)


# ---------------------------------------------------------------------------
# load_report
# ---------------------------------------------------------------------------

def test_load_report_returns_none_for_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)
    assert load_report(DATE_STR, "nonexistent-slug") is None


def test_load_report_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr("app.report._REPORTS_ROOT", tmp_path)
    original = _make_report()
    save_report(original)

    loaded = load_report(DATE_STR, original.slug)
    assert loaded is not None
    assert loaded.slug == original.slug
    assert loaded.title == original.title
    assert loaded.metadata["deal_value_usd"] == 500
