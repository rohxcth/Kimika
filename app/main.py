"""Kimika FastAPI application.

Start:        uvicorn app.main:app --reload
Run pipeline: python -m app.pipeline --now
"""
from __future__ import annotations

import json
import logging
import re as _re
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

import markdown as md_lib
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import cfg
from app.report import ReportData, load_index, load_report
from app.scheduler import start_scheduler, stop_scheduler

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Kimika", lifespan=lifespan)

_BASE_DIR = Path(__file__).parent
_TEMPLATES_DIR = _BASE_DIR / "templates"
_STATIC_DIR = _BASE_DIR / "static"
_REPORTS_ROOT = Path(cfg["reports"]["output_dir"])

_STATIC_DIR.mkdir(exist_ok=True)
_TEMPLATES_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Jinja2 filters
# ---------------------------------------------------------------------------

def _section_title(key: str) -> str:
    """'1_deal_snapshot' → 'Deal Snapshot'"""
    clean = _re.sub(r"^\d+_", "", key)
    return clean.replace("_", " ").title()


def _format_usd(val_m: float | None) -> str:
    """Format US$ millions: 1300 → 'US$1.3bn', 450 → 'US$450m'"""
    if val_m is None:
        return ""
    if val_m >= 1000:
        return f"US${val_m / 1000:.1f}bn"
    return f"US${val_m:.0f}m"


def _format_date_short(date_str: str) -> str:
    """'2026-10-26' → '26 Oct 2026'"""
    try:
        d = datetime.fromisoformat(date_str)
        return f"{d.day} {d.strftime('%b')} {d.year}"
    except Exception:
        return date_str


templates.env.filters["section_title"] = _section_title
templates.env.filters["format_usd"] = _format_usd
templates.env.filters["format_date_short"] = _format_date_short
templates.env.tests["list"] = lambda v: isinstance(v, list)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    entries = _load_all_entries()
    reports = {
        e["slug"]: _prepare_report(e["date"], e["slug"])
        for e in entries
    }
    today = _today()
    return templates.TemplateResponse(
        request=request,
        name="page.html",
        context={
            "display_date": _format_date(today),
            "entries": entries,
            "reports": reports,
        },
    )


@app.get("/report/{date_str}/{slug}", response_class=HTMLResponse)
async def report_page(request: Request, date_str: str, slug: str):
    report = _prepare_report(date_str, slug)
    if report is None:
        raise HTTPException(404, "Report not found")
    # Find the index entry so we have version_count / deal_value_usd
    entry = next(
        (e for e in _load_index(date_str) if e["slug"] == slug),
        {},
    )
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={"report": report, "entry": entry},
    )


@app.get("/api/index/{date_str}")
async def api_index(date_str: str):
    return JSONResponse(_load_index(date_str))


@app.get("/api/report/{date_str}/{slug}")
async def api_report(date_str: str, slug: str):
    report = _load_report(date_str, slug)
    if report is None:
        raise HTTPException(404, "Report not found")
    return JSONResponse(report.to_dict())



@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()


def _load_all_entries(max_days: int = 30) -> list[dict]:
    """Aggregate entries from all available dates, newest date first.

    Within each date, larger deals sort above smaller ones (same ordering
    as each day's index.json). Entries from real reports/ take precedence;
    samples/ fills in any date that has no real reports yet.
    """
    all_entries: list[dict] = []
    for date_str in _available_dates()[:max_days]:
        all_entries.extend(_load_index(date_str))
    return all_entries


def _load_index(date_str: str) -> list[dict]:
    """Load index.json; fall back to samples/ if the real date has no reports."""
    entries = load_index(date_str)
    if not entries:
        sample_path = _REPORTS_ROOT / "samples" / date_str / "index.json"
        if sample_path.exists():
            entries = json.loads(sample_path.read_text(encoding="utf-8"))
    return entries


def _load_report(date_str: str, slug: str) -> ReportData | None:
    """Load a report; fall back to samples/ if not found in real reports."""
    report = load_report(date_str, slug)
    if report is None:
        path = _REPORTS_ROOT / "samples" / date_str / slug / "report.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return ReportData(**data)
    return report


def _prepare_report(date_str: str, slug: str) -> dict | None:
    """Load a report and pre-render markdown sections to HTML."""
    report = _load_report(date_str, slug)
    if report is None:
        return None
    d = report.to_dict()
    rendered: dict = {}
    for key, content in d["sections"].items():
        if isinstance(content, str):
            rendered[key] = md_lib.markdown(content, extensions=["tables"])
        else:
            rendered[key] = content  # list (deal wrap entries)
    d["rendered_sections"] = rendered
    return d


def _available_dates() -> list[str]:
    """All dates with reports, most recent first (real + samples)."""
    dates: set[str] = set()
    date_pattern = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

    if _REPORTS_ROOT.exists():
        for d in _REPORTS_ROOT.iterdir():
            if d.is_dir() and date_pattern.match(d.name):
                dates.add(d.name)
        samples_dir = _REPORTS_ROOT / "samples"
        if samples_dir.exists():
            for d in samples_dir.iterdir():
                if d.is_dir() and date_pattern.match(d.name):
                    dates.add(d.name)

    return sorted(dates, reverse=True)[:30]


def _format_date(date_str: str) -> str:
    """'2026-10-26' → 'Monday 26 October 2026'"""
    try:
        d = datetime.fromisoformat(date_str)
        return d.strftime(f"%A {d.day} %B %Y")
    except Exception:
        return date_str
