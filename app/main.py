"""Kimika FastAPI application.

Start:        uvicorn app.main:app --reload
Run pipeline: python -m app.pipeline --now
"""
from __future__ import annotations

import json
import logging
import re as _re
from datetime import date, datetime
from pathlib import Path

import markdown as md_lib
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import cfg
from app.report import ReportData, load_index, load_report

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

app = FastAPI(title="Kimika")

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


templates.env.filters["section_title"] = _section_title
templates.env.filters["format_usd"] = _format_usd
templates.env.tests["list"] = lambda v: isinstance(v, list)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, date: str | None = None):
    date_str = date or _today()
    entries = _load_index(date_str)
    reports = {
        e["slug"]: _prepare_report(date_str, e["slug"])
        for e in entries
    }
    return templates.TemplateResponse(
        request=request,
        name="page.html",
        context={
            "page_date": date_str,
            "display_date": _format_date(date_str),
            "entries": entries,
            "reports": reports,
            "available_dates": _available_dates(),
        },
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


@app.get("/api/render/{date_str}/{slug}")
async def api_render(date_str: str, slug: str, background_tasks: BackgroundTasks):
    """Generate a PDF for a report and return it. Renders synchronously."""
    from app.pdf import render_report
    report = _load_report(date_str, slug)
    if report is None:
        raise HTTPException(404, "Report not found")
    # Determine output dir: real reports dir (not samples)
    output_dir = _REPORTS_ROOT / date_str / slug
    try:
        path = render_report(report, output_dir=output_dir)
    except Exception as exc:
        logger.error("PDF render failed for %s/%s: %s", date_str, slug, exc)
        raise HTTPException(500, f"PDF render failed: {exc}")
    return FileResponse(str(path), media_type="application/pdf",
                        filename=f"Kimika_{slug}.pdf")


@app.get("/reports/{date_str}/{slug}/report.pdf")
async def serve_pdf(date_str: str, slug: str):
    """Serve a pre-rendered PDF, or 404 if not yet generated."""
    # Check real reports first, then samples
    for base in [_REPORTS_ROOT / date_str, _REPORTS_ROOT / "samples" / date_str]:
        path = base / slug / "report.pdf"
        if path.exists():
            return FileResponse(str(path), media_type="application/pdf",
                                filename=f"Kimika_{slug}.pdf")
    raise HTTPException(404, "PDF not yet generated — use /api/render/{date}/{slug}")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()


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
