"""Kimika dossier — Stage 2 of the report pipeline (Pool → Collate → ...).

Takes fetched raw documents and news items and assembles them into a
structured dossier dict ready for the Verify stage and then the LLM.

A dossier has:
  {
    "topic":            str,           # human-readable topic label
    "report_type":      str,           # "ma_full" | "ecm" | "dcm" | "economy" | ...
    "date":             str,           # ISO date YYYY-MM-DD
    "documents":        list[DocChunk],  # labelled, trimmed source chunks
    "market_data":      dict,          # for market column reports; empty for deals
    "word_count_target": int,          # synthesis target from WORD_COUNT_TARGETS
  }

Each DocChunk:
  {
    "source":    str,   # human label, e.g. "ASX announcement" or "GoogleNews:Reuters"
    "type":      str,   # "filing" | "data" | "news" | "commentary"
    "authority": str,   # "primary" | "secondary"
    "date":      str,   # ISO date or empty string
    "text":      str,   # trimmed to doc_trim_chars from config.yaml
  }

All trimming uses config.yaml pipeline.doc_trim_chars. One bad document
never stops the build: errors are logged and the chunk is skipped.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from app.config import cfg
from app.sources import NewsItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Word count targets per report type (from docs/report-templates.md)
# ---------------------------------------------------------------------------

WORD_COUNT_TARGETS: dict[str, int] = {
    "ma_full":    4000,
    "ecm":        2500,
    "dcm":        2500,
    "economy":    3000,
    "equities":   3000,
    "commodities": 3000,
    "bonds":      3000,
    "currencies": 3000,
    "other":      2500,
}

# ---------------------------------------------------------------------------
# DocChunk type
# ---------------------------------------------------------------------------

class DocChunk(TypedDict):
    source:    str   # human label for this chunk
    type:      str   # "filing" | "data" | "news" | "commentary"
    authority: str   # "primary" | "secondary"
    date:      str   # ISO date or empty string
    text:      str   # trimmed content


# ---------------------------------------------------------------------------
# Dossier type
# ---------------------------------------------------------------------------

class Dossier(TypedDict):
    topic:             str
    report_type:       str
    date:              str
    documents:         list[DocChunk]
    market_data:       dict
    word_count_target: int


# ---------------------------------------------------------------------------
# Document labelling helpers
# ---------------------------------------------------------------------------

# Source strings that indicate a primary filing document
_PRIMARY_SOURCE_KEYWORDS = {
    "asx announcement", "8-k", "defm14a", "prem14a", "s-4", "sc to-t",
    "sc 14d9", "scheme booklet", "sid", "scheme implementation deed",
    "independent expert", "ier", "fairness opinion", "rule 2.7", "rule 2.4",
    "rns", "prospectus", "annual report", "10-k", "10-q",
    "central bank", "rba", "federal reserve", "fomc", "abs", "bls", "bea",
    "fred", "imf", "oecd", "treasury",
}

_FILING_SOURCE_KEYWORDS = {
    "asx", "edgar", "rns", "8-k", "defm14a", "prem14a", "s-4", "sc to-t",
    "scheme booklet", "prospectus", "annual report", "10-k",
}

_DATA_SOURCE_KEYWORDS = {
    "fred", "rba", "fmp", "yfinance", "bls", "bea", "abs", "central bank",
    "federal reserve", "fomc", "treasury", "imf", "oecd",
}

_COMMENTARY_SOURCE_KEYWORDS = {
    "googlenews", "newsapi", "reuters", "ap news", "bloomberg",
    "commentary", "analyst", "strategist",
}


def _classify_chunk_type(source: str) -> str:
    """Classify a source string as filing | data | news | commentary."""
    s = source.lower()
    if any(kw in s for kw in _FILING_SOURCE_KEYWORDS):
        return "filing"
    if any(kw in s for kw in _DATA_SOURCE_KEYWORDS):
        return "data"
    if any(kw in s for kw in _COMMENTARY_SOURCE_KEYWORDS):
        return "commentary"
    return "news"


def _classify_authority(source: str) -> str:
    """Classify authority as primary | secondary."""
    s = source.lower()
    if any(kw in s for kw in _PRIMARY_SOURCE_KEYWORDS):
        return "primary"
    return "secondary"


def _trim(text: str) -> str:
    """Trim text to doc_trim_chars from config."""
    limit: int = cfg["pipeline"]["doc_trim_chars"]
    return text[:limit]


# ---------------------------------------------------------------------------
# Core dossier builders
# ---------------------------------------------------------------------------

def build_deal_dossier(
    topic: str,
    report_type: str,
    date: str,
    raw_texts: list[tuple[str, str]],
    news_items: list[NewsItem] | None = None,
) -> Dossier:
    """Build a dossier for a deal report (M&A, ECM, DCM, other).

    Args:
        topic:       Human-readable topic, e.g. "Acme Corp / Beta Ltd scheme"
        report_type: e.g. "ma_full", "ecm", "dcm"
        date:        ISO date string YYYY-MM-DD
        raw_texts:   List of (source_label, raw_text) tuples from fetchers.
                     source_label should describe the document, e.g.
                     "ASX announcement", "Scheme booklet", "GoogleNews:Reuters".
        news_items:  Optional list of NewsItem from discover_news(); converted
                     to DocChunks and appended after raw_texts.

    Returns a Dossier dict ready for the Verify stage.
    """
    documents: list[DocChunk] = []

    # Process raw text documents
    for source_label, text in raw_texts:
        if not text or not text.strip():
            logger.debug("Dossier: skipping empty chunk from %r", source_label)
            continue
        try:
            chunk = DocChunk(
                source=source_label,
                type=_classify_chunk_type(source_label),
                authority=_classify_authority(source_label),
                date=date,
                text=_trim(text),
            )
            documents.append(chunk)
        except Exception as exc:
            logger.warning("Dossier: failed to add chunk from %r: %s", source_label, exc)

    # Append news items as secondary commentary chunks
    for item in (news_items or []):
        try:
            # Prefer full article content if enriched; fall back to snippet
            body = item.get("content") or item.get("snippet", "") or ""
            title = item.get("title", "") or ""
            text = f"{title}\n{body}".strip()
            if not text:
                continue
            chunk = DocChunk(
                source=item.get("source", "news"),
                type=_classify_chunk_type(item.get("source", "")),
                authority="secondary",
                date=_normalise_date(item.get("published", "")),
                text=_trim(text),
            )
            documents.append(chunk)
        except Exception as exc:
            logger.warning("Dossier: failed to add news item %r: %s", item.get("title"), exc)

    word_target = WORD_COUNT_TARGETS.get(report_type, WORD_COUNT_TARGETS["other"])
    logger.info(
        "Dossier built: %r (%s) — %d chunks, target %dw",
        topic, report_type, len(documents), word_target,
    )
    return Dossier(
        topic=topic,
        report_type=report_type,
        date=date,
        documents=documents,
        market_data={},
        word_count_target=word_target,
    )


def build_market_dossier(
    report_type: str,
    date: str,
    raw_texts: list[tuple[str, str]],
    market_data: dict,
    news_items: list[NewsItem] | None = None,
) -> Dossier:
    """Build a dossier for a daily market column report.

    Args:
        report_type:  "economy" | "equities" | "commodities" | "bonds" | "currencies"
        date:         ISO date string YYYY-MM-DD
        raw_texts:    List of (source_label, raw_text) tuples (central bank pages,
                      official releases, etc.)
        market_data:  Dict of verified market levels/moves, e.g. from
                      discover_markets_context(). Passed through to the LLM.
        news_items:   Optional list of NewsItem for commentary context.

    Returns a Dossier dict ready for the Verify stage.
    """
    topic = f"Daily {report_type.title()} report — {date}"
    # Reuse deal dossier builder for document collation
    dossier = build_deal_dossier(
        topic=topic,
        report_type=report_type,
        date=date,
        raw_texts=raw_texts,
        news_items=news_items,
    )
    # Attach market data (not applicable for deal dossiers)
    dossier["market_data"] = market_data
    return dossier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from various date formats; return empty string on failure."""
    if not date_str:
        return ""
    # Already ISO format
    if len(date_str) >= 10 and date_str[4] == "-" and date_str[7] == "-":
        return date_str[:10]
    # RFC 2822: "Mon, 26 Oct 2026 07:00:00 GMT"
    try:
        from email.utils import parsedate
        parsed = parsedate(date_str)
        if parsed:
            return f"{parsed[0]:04d}-{parsed[1]:02d}-{parsed[2]:02d}"
    except Exception:
        pass
    return ""


def dossier_summary(dossier: Dossier) -> str:
    """Return a short human-readable summary of a dossier for logging."""
    counts: dict[str, int] = {}
    for chunk in dossier["documents"]:
        counts[chunk["type"]] = counts.get(chunk["type"], 0) + 1
    breakdown = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    return (
        f"{dossier['topic']} | {dossier['report_type']} | {dossier['date']} | "
        f"{len(dossier['documents'])} chunks ({breakdown}) | "
        f"target {dossier['word_count_target']}w"
    )
