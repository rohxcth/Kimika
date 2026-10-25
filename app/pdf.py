"""Kimika PDF renderer — produces a professional A4 PDF for each report.

Uses reportlab (pure Python, no system DLLs required).

Layout per spec section 6:
  - A4, 18mm margins, 11pt body, 1.3 line height
  - Header block: Kimika wordmark · report type · title · date · key takeaways
  - Numbered sub-sections with prose and tables
  - Shaded "Market view" and "Outlook & scenarios" boxes
  - Bibliography (grouped by category)
  - Footer: "Kimika · <title> · <date>" left, "Page X of Y" right
  - Disclaimer on last page

Public interface:
  render_report(report: ReportData) -> Path   — renders + saves report.pdf
  render_to_html(report: ReportData) -> str   — returns HTML string (for tests)
"""
from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

from app.config import cfg
from app.report import ReportData, load_report

logger = logging.getLogger(__name__)

_REPORTS_ROOT = Path(cfg["reports"]["output_dir"])

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

NAVY        = colors.HexColor("#0f2044")
NAVY_LIGHT  = colors.HexColor("#1a3a6e")
ACCENT      = colors.HexColor("#1d4ed8")   # blue accent for tables
SHADE_BG    = colors.HexColor("#f1f5f9")   # shaded box background
RULE_COLOR  = colors.HexColor("#e5e7eb")
TEXT_DARK   = colors.HexColor("#111827")
TEXT_BODY   = colors.HexColor("#374151")
TEXT_MUTED  = colors.HexColor("#6b7280")

# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN_L = MARGIN_R = 18 * mm
MARGIN_T = 20 * mm
MARGIN_B = 20 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    def _s(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, **kw)

    return {
        "wordmark": _s("wordmark",
            fontName="Helvetica-Bold", fontSize=7, textColor=NAVY,
            letterSpacing=3, leading=9, spaceAfter=2),
        "report_tag": _s("report_tag",
            fontName="Helvetica", fontSize=7, textColor=TEXT_MUTED,
            leading=9, spaceAfter=1),
        "title": _s("title",
            fontName="Helvetica-Bold", fontSize=14, textColor=TEXT_DARK,
            leading=17, spaceAfter=4),
        "date_line": _s("date_line",
            fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED,
            leading=10, spaceAfter=6),
        "takeaway": _s("takeaway",
            fontName="Helvetica", fontSize=9, textColor=TEXT_BODY,
            leading=12, leftIndent=10, spaceAfter=3),
        "section_head": _s("section_head",
            fontName="Helvetica-Bold", fontSize=7.5, textColor=TEXT_MUTED,
            letterSpacing=1.5, leading=10, spaceBefore=10, spaceAfter=4),
        "body": _s("body",
            fontName="Helvetica", fontSize=10, textColor=TEXT_BODY,
            leading=13, spaceAfter=5),
        "body_bold": _s("body_bold",
            fontName="Helvetica-Bold", fontSize=10, textColor=TEXT_DARK,
            leading=13, spaceAfter=5),
        "shaded_body": _s("shaded_body",
            fontName="Helvetica", fontSize=9.5, textColor=TEXT_BODY,
            leading=13, leftIndent=8, rightIndent=8, spaceAfter=4),
        "bib_head": _s("bib_head",
            fontName="Helvetica-Bold", fontSize=8, textColor=TEXT_MUTED,
            leading=10, spaceBefore=6, spaceAfter=3),
        "bib_entry": _s("bib_entry",
            fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED,
            leading=11, spaceAfter=2),
        "disclaimer": _s("disclaimer",
            fontName="Helvetica-Oblique", fontSize=7.5, textColor=TEXT_MUTED,
            leading=10, spaceAfter=0),
    }


# ---------------------------------------------------------------------------
# Page footer callback
# ---------------------------------------------------------------------------

class _KimikaPage:
    """Callable passed to PageTemplate — draws header rule + footer on every page."""

    def __init__(self, title: str, date_str: str, doc):
        self.title = title
        self.date_str = date_str
        self.doc = doc

    def __call__(self, canvas, doc):
        canvas.saveState()
        # Bottom footer line
        canvas.setStrokeColor(RULE_COLOR)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_L, MARGIN_B - 4 * mm, PAGE_W - MARGIN_R, MARGIN_B - 4 * mm)
        # Footer text
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(TEXT_MUTED)
        short_title = self.title[:60] + ("…" if len(self.title) > 60 else "")
        canvas.drawString(MARGIN_L, MARGIN_B - 7 * mm,
                          f"Kimika  ·  {short_title}  ·  {self.date_str}")
        page_str = f"Page {doc.page}"
        canvas.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 7 * mm, page_str)
        canvas.restoreState()


# ---------------------------------------------------------------------------
# Markdown-like text → reportlab Paragraphs
# ---------------------------------------------------------------------------

# Patterns to detect pipe-table lines
_TABLE_ROW = re.compile(r"^\|(.+)\|$")
_TABLE_SEP  = re.compile(r"^\|[-| :]+\|$")

_BOLD_INLINE = re.compile(r"\*\*(.+?)\*\*")
_DASH_LINE   = re.compile(r"^-{3,}$")


def _inline(text: str) -> str:
    """Convert **bold** markdown to reportlab <b> tags."""
    return _BOLD_INLINE.sub(r"<b>\1</b>", text)


def _parse_section(text: str, styles: dict) -> list:
    """Convert a markdown section string to a list of reportlab Flowables."""
    flowables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect pipe table block
        if _TABLE_ROW.match(line) and not _TABLE_SEP.match(line):
            table_lines = []
            while i < len(lines) and _TABLE_ROW.match(lines[i]):
                if not _TABLE_SEP.match(lines[i]):
                    cells = [c.strip() for c in lines[i].strip("|").split("|")]
                    table_lines.append(cells)
                i += 1
            if table_lines:
                flowables.append(_build_table(table_lines, styles))
            continue

        # Bullet list item  "- **key** value"
        if line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            flowables.append(Paragraph(f"• &nbsp;{_inline(content)}", styles["body"]))
            i += 1
            continue

        # Horizontal rule
        if _DASH_LINE.match(line.strip()):
            flowables.append(HRFlowable(width="100%", thickness=0.5,
                                        color=RULE_COLOR, spaceAfter=4))
            i += 1
            continue

        # Heading lines starting with #
        if line.startswith("#"):
            clean = re.sub(r"^#+\s*", "", line)
            flowables.append(Paragraph(_inline(clean), styles["body_bold"]))
            i += 1
            continue

        # Non-empty body line
        if line.strip():
            flowables.append(Paragraph(_inline(line.strip()), styles["body"]))

        i += 1

    return flowables


def _build_table(rows: list[list[str]], styles: dict) -> Table:
    """Build a reportlab Table from a list-of-rows (strings)."""
    # Convert cell text to Paragraphs for wrapping
    cell_style = ParagraphStyle("cell", fontName="Helvetica", fontSize=9,
                                 leading=12, textColor=TEXT_BODY)
    head_style = ParagraphStyle("cell_h", fontName="Helvetica-Bold", fontSize=9,
                                 leading=12, textColor=TEXT_DARK)
    data = []
    for r_idx, row in enumerate(rows):
        styled = []
        for cell in row:
            s = head_style if r_idx == 0 else cell_style
            styled.append(Paragraph(_inline(cell), s))
        data.append(styled)

    col_count = max(len(r) for r in data) if data else 1

    # Distribute column widths: first col slightly wider for label tables
    if col_count == 2:
        col_widths = [CONTENT_W * 0.38, CONTENT_W * 0.62]
    else:
        col_widths = [CONTENT_W / col_count] * col_count

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, RULE_COLOR),
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#f9fafb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    t.spaceAfter = 8
    return t


# ---------------------------------------------------------------------------
# Shaded box
# ---------------------------------------------------------------------------

def _shaded_box(heading: str, content: str, styles: dict) -> list:
    """Return flowables for a shaded callout box (Market view / Outlook)."""
    inner = []
    if heading:
        inner.append(Paragraph(heading.upper(), ParagraphStyle(
            "box_head", fontName="Helvetica-Bold", fontSize=7,
            textColor=NAVY, letterSpacing=1.5, leading=10, spaceAfter=4)))
    for line in content.splitlines():
        if line.strip():
            inner.append(Paragraph(_inline(line.strip()), styles["shaded_body"]))

    # Wrap in a single-cell table with shaded background
    cell = Table([[flowable] for flowable in inner],
                 colWidths=[CONTENT_W - 16])
    cell.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SHADE_BG),
        ("BOX",        (0, 0), (-1, -1), 0.5, RULE_COLOR),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    cell.spaceAfter = 8
    return [cell]


# Sections that get shaded callout treatment
_SHADED_SECTIONS = {"7_market_view", "8_outlook_and_scenarios"}

_SECTION_LABELS = {
    "1_deal_snapshot":           "1. Deal snapshot",
    "2_strategic_rationale":     "2. Strategic rationale",
    "3_process_and_negotiations":"3. Process & negotiations",
    "4_valuation":               "4. Valuation",
    "5_structure_terms_financing":"5. Structure, terms & financing",
    "6_advisers":                "6. Advisers",
    "7_market_view":             "7. Market view",
    "8_outlook_and_scenarios":   "8. Outlook & scenarios",
}


# ---------------------------------------------------------------------------
# Deal-wrap table (sections["entries"] is a list of dicts)
# ---------------------------------------------------------------------------

def _deal_wrap_table(entries: list[dict], styles: dict) -> Table:
    headers = ["Region", "Type", "Parties", "Size", "Key term", "Status"]
    h_style = ParagraphStyle("wh", fontName="Helvetica-Bold", fontSize=8,
                              leading=11, textColor=TEXT_DARK)
    c_style = ParagraphStyle("wc", fontName="Helvetica", fontSize=8,
                              leading=11, textColor=TEXT_BODY)

    data = [[Paragraph(h, h_style) for h in headers]]
    for e in entries:
        data.append([
            Paragraph(str(e.get("region", "")), c_style),
            Paragraph(str(e.get("deal_type", "")), c_style),
            Paragraph(str(e.get("parties", "")), c_style),
            Paragraph(str(e.get("size", "")), c_style),
            Paragraph(str(e.get("key_term", "")), c_style),
            Paragraph(str(e.get("status", "")), c_style),
        ])

    col_ws = [
        CONTENT_W * 0.08, CONTENT_W * 0.08, CONTENT_W * 0.25,
        CONTENT_W * 0.12, CONTENT_W * 0.27, CONTENT_W * 0.20,
    ]
    t = Table(data, colWidths=col_ws, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID",        (0, 0), (-1, -1), 0.5, RULE_COLOR),
        ("BACKGROUND",  (0, 0), (-1, 0),  colors.HexColor("#f9fafb")),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ---------------------------------------------------------------------------
# Bibliography
# ---------------------------------------------------------------------------

def _bibliography_flowables(bib: list[dict], styles: dict) -> list:
    if not bib:
        return []
    flowables = [
        HRFlowable(width="100%", thickness=0.5, color=RULE_COLOR, spaceBefore=8, spaceAfter=4),
        Paragraph("BIBLIOGRAPHY", styles["section_head"]),
    ]
    grouped: dict[str, list[dict]] = {}
    for entry in bib:
        cat = entry.get("category", "Other")
        grouped.setdefault(cat, []).append(entry)

    for cat, entries in grouped.items():
        flowables.append(Paragraph(cat, styles["bib_head"]))
        for e in entries:
            title = e.get("title", "")
            publisher = e.get("publisher", "")
            date = e.get("date", "")
            url = e.get("url", "")
            line = f"{title} — {publisher}, {date}"
            if url:
                line += f"  [{url}]"
            flowables.append(Paragraph(line, styles["bib_entry"]))
    return flowables


# ---------------------------------------------------------------------------
# Public: render_report → PDF file
# ---------------------------------------------------------------------------

def render_report(report: ReportData, output_dir: Path | None = None) -> Path:
    """Render a ReportData to a PDF file.

    Saves to:  reports/YYYY-MM-DD/<slug>/report.pdf
    Also updates has_pdf=True in the day's index.json.
    Returns the path to the written PDF.
    """
    if output_dir is None:
        output_dir = _REPORTS_ROOT / report.date / report.slug
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "report.pdf"

    buf = BytesIO()
    styles = _build_styles()
    page_cb = _KimikaPage(report.title, report.date, None)

    story = _build_story(report, styles)

    # Two-pass build so page_cb.doc is set correctly
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title=report.title,
        author="Kimika",
    )
    page_cb.doc = doc

    frame = Frame(MARGIN_L, MARGIN_B, CONTENT_W,
                  PAGE_H - MARGIN_T - MARGIN_B, id="main")
    doc.addPageTemplates([
        PageTemplate(id="page", frames=[frame], onPage=page_cb)
    ])
    doc.build(story)

    pdf_bytes = buf.getvalue()
    output_path.write_bytes(pdf_bytes)
    logger.info("PDF written: %s (%d bytes)", output_path, len(pdf_bytes))

    _set_has_pdf(report.date, report.slug)
    return output_path


def _build_story(report: ReportData, styles: dict) -> list:
    """Build the reportlab story (list of Flowables) for a report."""
    story = []

    # ── Header block ──────────────────────────────────────────────────────
    type_tag = {
        "ma_full":        f"M&A  ·  {report.region}",
        "deal_wrap":      "Deal Wrap",
        "economy_markets":"Economy & Markets",
    }.get(report.report_type, report.report_type.upper())

    story.append(Paragraph("KIMIKA", styles["wordmark"]))
    story.append(Paragraph(type_tag, styles["report_tag"]))
    story.append(Paragraph(report.title, styles["title"]))
    story.append(Paragraph(report.date, styles["date_line"]))

    # Key takeaways
    if report.key_takeaways:
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=NAVY_LIGHT, spaceAfter=5))
        for kt in report.key_takeaways[:3]:
            story.append(Paragraph(f"<b>·</b>&nbsp;&nbsp;{_inline(kt)}", styles["takeaway"]))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=RULE_COLOR, spaceAfter=8))
    else:
        story.append(Spacer(1, 6 * mm))

    # ── Sections ──────────────────────────────────────────────────────────
    if report.report_type == "deal_wrap":
        entries = report.sections.get("entries", [])
        if isinstance(entries, list) and entries:
            story.append(Paragraph("DEALS", styles["section_head"]))
            story.append(_deal_wrap_table(entries, styles))
    else:
        for key, content in report.sections.items():
            label = _SECTION_LABELS.get(key) or re.sub(r"^\d+_", "", key).replace("_", " ").title()
            story.append(Paragraph(label.upper(), styles["section_head"]))

            if not isinstance(content, str):
                continue

            if key in _SHADED_SECTIONS:
                story.extend(_shaded_box("", content, styles))
            else:
                flowables = _parse_section(content, styles)
                story.extend(flowables)

    # ── Bibliography ──────────────────────────────────────────────────────
    story.extend(_bibliography_flowables(report.bibliography, styles))

    # ── Disclaimer ────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE_COLOR, spaceAfter=3))
    story.append(Paragraph(
        "Prepared from public sources for information purposes only. "
        "Not financial advice. Views reflect a synthesis of public market commentary, "
        "not Kimika's own recommendations.",
        styles["disclaimer"],
    ))

    return story


# ---------------------------------------------------------------------------
# Update index.json has_pdf flag
# ---------------------------------------------------------------------------

def _set_has_pdf(date_str: str, slug: str) -> None:
    """Flip has_pdf=True for this slug in the day's index.json."""
    import json
    index_path = _REPORTS_ROOT / date_str / "index.json"
    if not index_path.exists():
        return
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        for e in entries:
            if e["slug"] == slug:
                e["has_pdf"] = True
                break
        index_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not update has_pdf flag: %s", exc)


# ---------------------------------------------------------------------------
# render_to_html — for testing without writing a real PDF
# ---------------------------------------------------------------------------

def render_to_html(report: ReportData) -> str:
    """Return a minimal HTML string representing the report structure.

    Used by tests to verify sections are present without running WeasyPrint.
    Contains all section headings, key takeaways and bibliography entries.
    """
    parts = [f"<h1>{report.title}</h1>"]
    for kt in report.key_takeaways:
        parts.append(f"<p class='takeaway'>{kt}</p>")
    for key, content in report.sections.items():
        label = _SECTION_LABELS.get(key, key)
        parts.append(f"<h2>{label}</h2>")
        if isinstance(content, str):
            parts.append(f"<div>{content}</div>")
    for b in report.bibliography:
        parts.append(f"<cite>{b.get('title', '')} — {b.get('publisher', '')}</cite>")
    parts.append("<p class='disclaimer'>Not financial advice</p>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry point: python -m app.pdf <slug> <date>
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("Usage: python -m app.pdf <slug> <date YYYY-MM-DD>")
        sys.exit(1)
    slug, date_str = sys.argv[1], sys.argv[2]
    r = load_report(date_str, slug)
    if r is None:
        # Try samples
        import json as _json
        sample = _REPORTS_ROOT / "samples" / date_str / slug / "report.json"
        if sample.exists():
            r = ReportData(**_json.loads(sample.read_text()))
    if r is None:
        print(f"Report not found: {slug} / {date_str}")
        sys.exit(1)
    path = render_report(r)
    print(f"Written: {path}")
