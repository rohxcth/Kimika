"""Kimika report data structures and persistence.

ReportData holds everything about one report: title, sections, verification
log, bibliography, and metadata (deal value, companies, etc.).

save_report() writes:
  reports/YYYY-MM-DD/<slug>/report.json
  reports/YYYY-MM-DD/index.json   (list of today's reports, updated in-place)

load_report() and load_index() read them back.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.config import cfg

_REPORTS_ROOT = Path(cfg["reports"]["output_dir"])


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReportData:
    """One Kimika report — M&A full, deal wrap, or Economy & Markets.

    Fields
    ------
    slug        : URL/filesystem-safe identifier, e.g. "bhp-anglo-ma-au-2026-10-26"
    date        : ISO date the report was generated, YYYY-MM-DD
    report_type : "ma_full" | "deal_wrap" | "economy_markets"
    region      : "US" | "AU" | "UK" | "global"
    title       : human-readable report title
    key_takeaways : list of 3 short bullets shown in the PDF header
    sections    : ordered dict of section_name → markdown content string
    verification_log : list of VerificationResult.to_dict() dicts (not in PDF)
    bibliography : list of {"title", "publisher", "date", "url", "category"}
    metadata    : deal-specific extras (deal_value_usd, acquirer, target, etc.)
    updated_at  : ISO datetime of last save (set by save_report)
    """
    slug: str
    date: str
    report_type: str
    region: str
    title: str
    key_takeaways: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    verification_log: list[dict] = field(default_factory=list)
    bibliography: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def make_slug(title: str, region: str, report_type: str, date_str: str) -> str:
    """Generate a filesystem-safe slug from a report title.

    e.g. "BHP / Anglo American: US$49bn scheme", "AU", "ma_full", "2026-10-26"
      → "bhp-anglo-american-ma-au-2026-10-26"
    """
    # Strip currency symbols and punctuation; lowercase; collapse spaces to hyphens
    clean = re.sub(r"[^\w\s]", " ", title.lower())
    clean = re.sub(r"\s+", "-", clean.strip())
    # Take first 40 chars to keep paths short
    clean = clean[:40].rstrip("-")
    suffix = f"{report_type.replace('_', '')}-{region.lower()}-{date_str}"
    return f"{clean}-{suffix}"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_report(report: ReportData) -> Path:
    """Write report.json for a single report and update the day's index.json.

    If a report.json already exists at this path (i.e. the deal is being
    updated), the old version is archived to versions/<old_updated_at>.json
    before overwriting so the full history is preserved.

    Returns the path to the saved report.json.
    """
    import datetime as _dt
    report.updated_at = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")

    report_dir = _REPORTS_ROOT / report.date / report.slug
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / "report.json"

    # Archive the existing version before overwriting
    if report_path.exists():
        _archive_version(report_path, report_dir)

    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _update_index(report)
    return report_path


def _archive_version(report_path: Path, report_dir: Path) -> None:
    """Copy the current report.json into versions/ using its updated_at timestamp."""
    try:
        old = json.loads(report_path.read_text(encoding="utf-8"))
        # Use the stored updated_at as the archive filename; fall back to 'unknown'
        ts = old.get("updated_at", "unknown").replace(":", "-").replace("Z", "")
        versions_dir = report_dir / "versions"
        versions_dir.mkdir(exist_ok=True)
        archive_path = versions_dir / f"{ts}.json"
        archive_path.write_text(
            json.dumps(old, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # Never let archiving crash a save


def load_report(date_str: str, slug: str) -> ReportData | None:
    """Load a report from disk. Returns None if not found."""
    path = _REPORTS_ROOT / date_str / slug / "report.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReportData(**data)


def load_index(date_str: str) -> list[dict]:
    """Load the index for a given date. Returns [] if not found."""
    path = _REPORTS_ROOT / date_str / "index.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _update_index(report: ReportData) -> None:
    """Add or update this report's entry in the day's index.json."""
    date_str = report.date
    index_path = _REPORTS_ROOT / date_str / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    if index_path.exists():
        entries = json.loads(index_path.read_text(encoding="utf-8"))

    # Update existing entry or append new one
    entry = _index_entry(report)
    for i, existing in enumerate(entries):
        if existing["slug"] == report.slug:
            entries[i] = entry
            break
    else:
        entries.append(entry)

    # Sort: deal_wrap last, then by deal_value_usd descending
    entries.sort(
        key=lambda e: (
            e["report_type"] == "deal_wrap",
            -(e.get("deal_value_usd") or 0),
        )
    )

    index_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _index_entry(report: ReportData) -> dict:
    """Build the compact index entry shown on the web page."""
    versions_dir = _REPORTS_ROOT / report.date / report.slug / "versions"
    version_count = len(list(versions_dir.glob("*.json"))) if versions_dir.exists() else 0
    return {
        "slug": report.slug,
        "date": report.date,
        "report_type": report.report_type,
        "region": report.region,
        "title": report.title,
        "summary": report.key_takeaways[0] if report.key_takeaways else "",
        "deal_value_usd": report.metadata.get("deal_value_usd"),
        "updated_at": report.updated_at,
        "has_pdf": False,  # set to True by pdf.py after rendering
        "version_count": version_count,
    }
