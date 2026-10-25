"""Tests for app/pdf.py — PDF rendering.

Uses render_to_html() (no actual PDF written in CI) plus a smoke test
that builds the reportlab story from fixture data to catch import and
layout errors without needing to write a file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pdf import (
    _build_story,
    _build_styles,
    _deal_wrap_table,
    _parse_section,
    render_to_html,
)
from app.report import ReportData

SAMPLE_DATE = "2026-10-26"
SAMPLE_SLUG = "acme-corp-beta-ltd-a-2bn-scheme-mafull-au-2026-10-26"
WRAP_SLUG   = "deal-wrap-2026-10-26"
SAMPLES_DIR = Path("reports/samples")


def _load_sample(slug: str) -> ReportData:
    path = SAMPLES_DIR / SAMPLE_DATE / slug / "report.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReportData(**data)


# ---------------------------------------------------------------------------
# render_to_html — structure checks (no PDF written)
# ---------------------------------------------------------------------------

def test_render_to_html_contains_title():
    report = _load_sample(SAMPLE_SLUG)
    html = render_to_html(report)
    assert report.title in html


def test_render_to_html_contains_key_takeaways():
    report = _load_sample(SAMPLE_SLUG)
    html = render_to_html(report)
    for kt in report.key_takeaways:
        assert kt[:30] in html


def test_render_to_html_contains_section_headings():
    report = _load_sample(SAMPLE_SLUG)
    html = render_to_html(report)
    assert "Deal snapshot" in html or "1. Deal snapshot" in html


def test_render_to_html_contains_bibliography():
    report = _load_sample(SAMPLE_SLUG)
    html = render_to_html(report)
    assert "Acme Corp" in html  # title of the bib entry


def test_render_to_html_contains_disclaimer():
    report = _load_sample(SAMPLE_SLUG)
    html = render_to_html(report)
    assert "Not financial advice" in html


def test_render_to_html_deal_wrap():
    report = _load_sample(WRAP_SLUG)
    html = render_to_html(report)
    assert report.title in html


# ---------------------------------------------------------------------------
# _build_story — smoke test: builds without error, returns flowables
# ---------------------------------------------------------------------------

def test_build_story_ma_report_returns_flowables():
    report = _load_sample(SAMPLE_SLUG)
    styles = _build_styles()
    story = _build_story(report, styles)
    assert len(story) > 5


def test_build_story_deal_wrap_returns_flowables():
    report = _load_sample(WRAP_SLUG)
    styles = _build_styles()
    story = _build_story(report, styles)
    assert len(story) > 0


def test_build_story_includes_disclaimer():
    from reportlab.platypus import Paragraph
    report = _load_sample(SAMPLE_SLUG)
    styles = _build_styles()
    story = _build_story(report, styles)
    texts = [
        getattr(f, "text", "") for f in story if isinstance(f, Paragraph)
    ]
    combined = " ".join(texts)
    assert "Not financial advice" in combined


# ---------------------------------------------------------------------------
# _parse_section — markdown parsing
# ---------------------------------------------------------------------------

def test_parse_section_plain_text():
    styles = _build_styles()
    from reportlab.platypus import Paragraph
    flowables = _parse_section("Beta Ltd acquires Acme Corp.", styles)
    assert any(isinstance(f, Paragraph) for f in flowables)


def test_parse_section_pipe_table():
    from reportlab.platypus import Table
    styles = _build_styles()
    md = "| **Acquirer** | Beta Ltd |\n|---|---|\n| **Target** | Acme Corp |"
    flowables = _parse_section(md, styles)
    assert any(isinstance(f, Table) for f in flowables)


def test_parse_section_bullet_list():
    from reportlab.platypus import Paragraph
    styles = _build_styles()
    flowables = _parse_section("- First bullet\n- Second bullet", styles)
    texts = [getattr(f, "text", "") for f in flowables if isinstance(f, Paragraph)]
    assert any("First bullet" in t for t in texts)


def test_parse_section_bold_inline():
    from reportlab.platypus import Paragraph
    styles = _build_styles()
    flowables = _parse_section("**Bold text** here.", styles)
    texts = [getattr(f, "text", "") for f in flowables if isinstance(f, Paragraph)]
    assert any("<b>Bold text</b>" in t for t in texts)


# ---------------------------------------------------------------------------
# _deal_wrap_table
# ---------------------------------------------------------------------------

def test_deal_wrap_table_smoke():
    from reportlab.platypus import Table
    styles = _build_styles()
    entries = [
        {"region": "AU", "deal_type": "M&A", "parties": "A / B",
         "size": "A$2bn", "key_term": "A$4.10 cash", "status": "SID signed"}
    ]
    t = _deal_wrap_table(entries, styles)
    assert isinstance(t, Table)


def test_deal_wrap_table_empty_entries():
    from reportlab.platypus import Table
    styles = _build_styles()
    t = _deal_wrap_table([], styles)
    assert isinstance(t, Table)


# ---------------------------------------------------------------------------
# API route: /api/render
# ---------------------------------------------------------------------------

def test_api_render_returns_pdf(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.main as main_mod
    import app.pdf as pdf_mod

    # Redirect where render_report writes the PDF (not the sample lookup root)
    monkeypatch.setattr(pdf_mod, "_REPORTS_ROOT", tmp_path)
    # Patch api_render's output_dir to use tmp_path
    original_render = pdf_mod.render_report
    def _patched_render(report, output_dir=None):
        output_dir = tmp_path / report.date / report.slug
        return original_render(report, output_dir=output_dir)
    monkeypatch.setattr(pdf_mod, "render_report", _patched_render)

    client = TestClient(app)
    r = client.get(f"/api/render/{SAMPLE_DATE}/{SAMPLE_SLUG}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 1000  # real PDF is at least 1 KB


def test_api_render_404_for_missing_slug():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get(f"/api/render/{SAMPLE_DATE}/nonexistent-slug")
    assert r.status_code == 404


def test_serve_pdf_404_when_not_generated():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get(f"/reports/2099-01-01/no-such-slug/report.pdf")
    assert r.status_code == 404
