"""Kimika scheduler — daily pipeline run at 6:30am Sydney time.

Uses APScheduler's BackgroundScheduler (thread-based, works with FastAPI's
sync startup) with a CronTrigger.

Missed-run catch-up
-------------------
On startup, check whether today's pipeline has already run (reports/YYYY-MM-DD/
index.json exists and is non-empty). If it hasn't run and local Sydney time is
past 6:30am, run immediately in a background thread so the app starts fast.

Called from app/main.py lifespan.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import cfg

logger = logging.getLogger(__name__)

_SYDNEY = ZoneInfo("Australia/Sydney")
_RUN_HOUR   = cfg["schedule"]["run_hour"]    # 6
_RUN_MINUTE = cfg["schedule"]["run_minute"]  # 30
_REPORTS_ROOT = Path(cfg["reports"]["output_dir"])

_scheduler: BackgroundScheduler | None = None


def _pipeline_job() -> None:
    """Run the pipeline for today. Errors are logged, never raised."""
    try:
        from app.pipeline import run
        summary = run()
        logger.info("Scheduled pipeline done: %s", summary)
    except Exception as exc:
        logger.error("Scheduled pipeline failed: %s", exc)


def _today_run_done(now: datetime) -> bool:
    """Return True if today's index.json already exists and has entries.

    Uses the real reports dir only (not samples), because samples are
    fixture data, not a real pipeline run.
    """
    date_str = now.strftime("%Y-%m-%d")
    index_path = _REPORTS_ROOT / date_str / "index.json"
    if not index_path.exists():
        return False
    try:
        import json
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        return len(entries) > 0
    except Exception:
        return False


def _should_catchup(now: datetime) -> bool:
    """Return True if we're past today's run time and the run hasn't happened.

    Finance analogy: like checking whether the market open print already
    occurred — if it's 9:35am and no open bar exists, replay from open.
    """
    run_time_today = now.replace(
        hour=_RUN_HOUR, minute=_RUN_MINUTE, second=0, microsecond=0
    )
    return now >= run_time_today and not _today_run_done(now)


def start_scheduler() -> None:
    """Start the APScheduler and run missed-run catch-up if needed.

    Safe to call multiple times — only one scheduler instance is created.
    """
    global _scheduler

    if _scheduler is not None:
        logger.debug("Scheduler already running.")
        return

    # Missed-run catch-up: if we're past 6:30am Sydney and haven't run today,
    # kick off the pipeline immediately in a background thread.
    now_sydney = datetime.now(_SYDNEY)
    if _should_catchup(now_sydney):
        logger.info(
            "Missed-run catch-up: it's %s in Sydney and today's pipeline hasn't run — starting now.",
            now_sydney.strftime("%H:%M"),
        )
        threading.Thread(target=_pipeline_job, daemon=True, name="kimika-catchup").start()
    else:
        logger.info(
            "No catch-up needed (Sydney time: %s, run done: %s).",
            now_sydney.strftime("%H:%M"),
            _today_run_done(now_sydney),
        )

    _scheduler = BackgroundScheduler(timezone=_SYDNEY)
    _scheduler.add_job(
        _pipeline_job,
        trigger=CronTrigger(hour=_RUN_HOUR, minute=_RUN_MINUTE, timezone=_SYDNEY),
        id="daily_pipeline",
        name="Kimika daily pipeline",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late (e.g. system woke mid-run)
    )
    _scheduler.start()

    next_run = _scheduler.get_job("daily_pipeline").next_run_time
    logger.info("Scheduler started. Next run: %s", next_run)


def stop_scheduler() -> None:
    """Shut down the scheduler cleanly (called on app shutdown)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
    _scheduler = None
