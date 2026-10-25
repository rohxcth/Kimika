"""Tests for app/scheduler.py.

No real pipeline calls, no real APScheduler ticks.
Tests cover: missed-run detection, catch-up logic, scheduler lifecycle.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

import pytest

import app.scheduler as sched_mod
from app.scheduler import _should_catchup, _today_run_done

_SYDNEY = ZoneInfo("Australia/Sydney")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sydney(hour: int, minute: int = 0) -> datetime:
    """Return a timezone-aware Sydney datetime for today at the given time."""
    return datetime.now(_SYDNEY).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


# ---------------------------------------------------------------------------
# _today_run_done
# ---------------------------------------------------------------------------

def test_run_done_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    assert _today_run_done(_sydney(7)) is False


def test_run_done_empty_index(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    date_str = datetime.now(_SYDNEY).strftime("%Y-%m-%d")
    index = tmp_path / date_str / "index.json"
    index.parent.mkdir(parents=True)
    index.write_text("[]", encoding="utf-8")
    assert _today_run_done(_sydney(7)) is False


def test_run_done_with_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    date_str = datetime.now(_SYDNEY).strftime("%Y-%m-%d")
    index = tmp_path / date_str / "index.json"
    index.parent.mkdir(parents=True)
    index.write_text(
        json.dumps([{"slug": "test", "report_type": "ma_full"}]),
        encoding="utf-8",
    )
    assert _today_run_done(_sydney(7)) is True


def test_run_done_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    date_str = datetime.now(_SYDNEY).strftime("%Y-%m-%d")
    index = tmp_path / date_str / "index.json"
    index.parent.mkdir(parents=True)
    index.write_text("not json", encoding="utf-8")
    assert _today_run_done(_sydney(7)) is False


# ---------------------------------------------------------------------------
# _should_catchup
# ---------------------------------------------------------------------------

def test_no_catchup_before_run_time(tmp_path, monkeypatch):
    """Before 6:30am, no catch-up even if no run has happened."""
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    assert _should_catchup(_sydney(5, 0)) is False


def test_no_catchup_at_exactly_run_minute_minus_one(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    assert _should_catchup(_sydney(6, 29)) is False


def test_catchup_after_run_time_no_reports(tmp_path, monkeypatch):
    """After 6:30am with no reports, catch-up is needed."""
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    assert _should_catchup(_sydney(7, 0)) is True


def test_no_catchup_after_run_time_reports_exist(tmp_path, monkeypatch):
    """After 6:30am but reports already exist, no catch-up."""
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    date_str = datetime.now(_SYDNEY).strftime("%Y-%m-%d")
    index = tmp_path / date_str / "index.json"
    index.parent.mkdir(parents=True)
    index.write_text(
        json.dumps([{"slug": "done"}]), encoding="utf-8"
    )
    assert _should_catchup(_sydney(9, 0)) is False


def test_catchup_at_exactly_run_time(tmp_path, monkeypatch):
    """At exactly 6:30am with no reports, catch-up triggers."""
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    assert _should_catchup(_sydney(6, 30)) is True


# ---------------------------------------------------------------------------
# start_scheduler / stop_scheduler
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_scheduler():
    """Ensure scheduler state is clean before and after each test."""
    sched_mod._scheduler = None
    yield
    if sched_mod._scheduler is not None:
        try:
            sched_mod._scheduler.shutdown(wait=False)
        except Exception:
            pass
    sched_mod._scheduler = None


def test_start_scheduler_creates_instance(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    with patch("app.scheduler._pipeline_job"):
        sched_mod.start_scheduler()
    assert sched_mod._scheduler is not None
    assert sched_mod._scheduler.running


def test_start_scheduler_idempotent(tmp_path, monkeypatch):
    """Calling start_scheduler twice doesn't create a second scheduler."""
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    with patch("app.scheduler._pipeline_job"):
        sched_mod.start_scheduler()
        first = sched_mod._scheduler
        sched_mod.start_scheduler()
        assert sched_mod._scheduler is first


def test_stop_scheduler(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    with patch("app.scheduler._pipeline_job"):
        sched_mod.start_scheduler()
    sched_mod.stop_scheduler()
    assert sched_mod._scheduler is None


def test_stop_scheduler_when_not_started():
    """stop_scheduler is a no-op if never started."""
    sched_mod.stop_scheduler()  # should not raise


def test_scheduler_has_daily_job(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    with patch("app.scheduler._pipeline_job"):
        sched_mod.start_scheduler()
    job = sched_mod._scheduler.get_job("daily_pipeline")
    assert job is not None
    assert job.name == "Kimika daily pipeline"


def test_catchup_spawns_thread(tmp_path, monkeypatch):
    """When catch-up is needed, a background thread is started."""
    monkeypatch.setattr(sched_mod, "_REPORTS_ROOT", tmp_path)
    with (
        patch("app.scheduler._should_catchup", return_value=True),
        patch("app.scheduler.threading.Thread") as mock_thread,
    ):
        mock_thread.return_value = MagicMock()
        sched_mod.start_scheduler()
    mock_thread.assert_called_once()
    assert mock_thread.call_args.kwargs.get("daemon") is True
