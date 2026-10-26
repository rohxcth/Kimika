"""Kimika prompts package.

Provides:
  load_examples()              — load style anchor .md files from prompts/examples/
  format_dossier_for_prompt()  — convert a Dossier into the (primary_doc, secondary_sources)
                                  strings expected by llm.py format calls
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.dossier import Dossier

logger = logging.getLogger(__name__)

_EXAMPLES_DIR = Path(__file__).parent / "examples"


def load_examples() -> str:
    """Load all style anchor .md files from prompts/examples/ and return them combined.

    Files are sorted alphabetically and joined with a separator.
    Returns empty string if the directory is missing or has no .md files.
    Called at module import time by each prompt module so the examples are
    baked into the SYSTEM prompt without a runtime file read per call.
    """
    if not _EXAMPLES_DIR.exists():
        logger.debug("load_examples: examples/ directory not found at %s", _EXAMPLES_DIR)
        return ""

    parts: list[str] = []
    for md_file in sorted(_EXAMPLES_DIR.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8").strip()
            if text:
                parts.append(text)
        except Exception as exc:
            logger.debug("load_examples: could not read %s: %s", md_file.name, exc)

    return "\n\n---\n\n".join(parts)


def format_dossier_for_prompt(dossier: "Dossier") -> tuple[str, str]:
    """Convert a Dossier into (primary_doc_str, secondary_sources_str) for llm.py.

    Primary-authority DocChunks go into primary_doc; secondary go into secondary_sources.
    Market data from dossier["market_data"] is appended to primary_doc.

    This is the bridge between the new five-stage pipeline (Pool -> Collate ->
    Verify -> Style -> Synthesise) and the existing llm.py interface, which
    expects two formatted strings. No changes to llm.py are needed for stages
    that pass a Dossier: call format_dossier_for_prompt() first.

    Returns:
        primary_doc:        Formatted string of primary-authority chunks + market data.
        secondary_sources:  Formatted string of secondary-authority chunks.
    """
    primary_parts: list[str] = []
    secondary_parts: list[str] = []

    for chunk in dossier.get("documents", []):
        header = f"[{chunk['source']}]"
        if chunk.get("date"):
            header += f" ({chunk['date']})"
        block = f"{header}\n{chunk['text']}"

        if chunk.get("authority") == "primary":
            primary_parts.append(block)
        else:
            secondary_parts.append(block)

    # Append structured market data (bonds, FX, equities levels) to primary_doc
    market_data: dict = dossier.get("market_data") or {}
    if market_data:
        md_lines = [f"{k}: {v}" for k, v in market_data.items()]
        primary_parts.append("[Market data]\n" + "\n".join(md_lines))

    sep = "\n\n---\n\n"
    return sep.join(primary_parts), sep.join(secondary_parts)
