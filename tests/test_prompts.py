"""Tests for app/prompts/__init__.py — load_examples and format_dossier_for_prompt.

No network, no LLM, no real files required. Exercises the two public functions
added in Step 19 with synthetic data.
"""

from __future__ import annotations

import pytest

from app.prompts import format_dossier_for_prompt, load_examples


# ---------------------------------------------------------------------------
# Synthetic dossier helpers
# ---------------------------------------------------------------------------

def _chunk(source: str, authority: str, text: str, date: str = "2026-10-26") -> dict:
    return {
        "source": source,
        "type": "filing" if authority == "primary" else "commentary",
        "authority": authority,
        "date": date,
        "text": text,
    }


def _dossier(documents: list[dict], market_data: dict | None = None) -> dict:
    return {
        "topic": "Test Deal",
        "report_type": "ma_full",
        "date": "2026-10-26",
        "documents": documents,
        "market_data": market_data or {},
        "word_count_target": 4000,
    }


# ---------------------------------------------------------------------------
# load_examples
# ---------------------------------------------------------------------------

def test_load_examples_returns_string():
    result = load_examples()
    assert isinstance(result, str)


def test_load_examples_not_empty():
    """examples/ directory exists with 4 .md files — should return non-empty string."""
    result = load_examples()
    assert len(result) > 100


def test_load_examples_contains_all_four_files():
    """All four style anchors should be included."""
    result = load_examples()
    assert "deal_snapshot" in result.lower() or "deal snapshot" in result.lower()
    assert "valuation" in result.lower()
    assert "macro" in result.lower() or "economy" in result.lower()
    assert "market column" in result.lower() or "equities" in result.lower()


def test_load_examples_idempotent():
    """Calling load_examples twice returns the same content."""
    assert load_examples() == load_examples()


# ---------------------------------------------------------------------------
# format_dossier_for_prompt — basic structure
# ---------------------------------------------------------------------------

def test_format_returns_two_strings():
    d = _dossier([])
    primary, secondary = format_dossier_for_prompt(d)
    assert isinstance(primary, str)
    assert isinstance(secondary, str)


def test_format_empty_dossier_returns_empty_strings():
    d = _dossier([])
    primary, secondary = format_dossier_for_prompt(d)
    assert primary == ""
    assert secondary == ""


def test_format_primary_chunk_in_primary_doc():
    d = _dossier([_chunk("ASX announcement", "primary", "Deal text here.")])
    primary, secondary = format_dossier_for_prompt(d)
    assert "ASX announcement" in primary
    assert "Deal text here." in primary
    assert secondary == ""


def test_format_secondary_chunk_in_secondary_sources():
    d = _dossier([_chunk("GoogleNews:Reuters", "secondary", "News commentary.")])
    primary, secondary = format_dossier_for_prompt(d)
    assert "GoogleNews:Reuters" in secondary
    assert "News commentary." in secondary
    assert primary == ""


def test_format_mixed_chunks_split_correctly():
    d = _dossier([
        _chunk("ASX announcement", "primary", "Primary text."),
        _chunk("GoogleNews:Reuters", "secondary", "Secondary text."),
    ])
    primary, secondary = format_dossier_for_prompt(d)
    assert "Primary text." in primary
    assert "Secondary text." not in primary
    assert "Secondary text." in secondary
    assert "Primary text." not in secondary


def test_format_multiple_primary_chunks_joined():
    d = _dossier([
        _chunk("ASX announcement", "primary", "Text A."),
        _chunk("Scheme booklet", "primary", "Text B."),
    ])
    primary, _ = format_dossier_for_prompt(d)
    assert "Text A." in primary
    assert "Text B." in primary


def test_format_date_included_in_header():
    d = _dossier([_chunk("ASX announcement", "primary", "Text.", date="2026-10-26")])
    primary, _ = format_dossier_for_prompt(d)
    assert "2026-10-26" in primary


def test_format_empty_date_omitted_from_header():
    chunk = _chunk("ASX announcement", "primary", "Text.", date="")
    d = _dossier([chunk])
    primary, _ = format_dossier_for_prompt(d)
    # Should not have empty parens
    assert "()" not in primary


# ---------------------------------------------------------------------------
# format_dossier_for_prompt — market data
# ---------------------------------------------------------------------------

def test_format_market_data_appended_to_primary():
    d = _dossier([], market_data={"au_10y_yield": "4.42%", "audusd": "0.645"})
    primary, _ = format_dossier_for_prompt(d)
    assert "au_10y_yield" in primary
    assert "4.42%" in primary
    assert "Market data" in primary


def test_format_empty_market_data_not_appended():
    d = _dossier([], market_data={})
    primary, _ = format_dossier_for_prompt(d)
    assert "Market data" not in primary


def test_format_market_data_with_primary_chunks():
    d = _dossier(
        [_chunk("ASX announcement", "primary", "Filing text.")],
        market_data={"offer_price": "4.20"},
    )
    primary, _ = format_dossier_for_prompt(d)
    assert "Filing text." in primary
    assert "offer_price" in primary


# ---------------------------------------------------------------------------
# format_dossier_for_prompt — separator
# ---------------------------------------------------------------------------

def test_format_multiple_chunks_have_separator():
    d = _dossier([
        _chunk("ASX announcement", "primary", "A."),
        _chunk("Scheme booklet", "primary", "B."),
    ])
    primary, _ = format_dossier_for_prompt(d)
    assert "---" in primary


def test_format_single_chunk_no_trailing_separator():
    d = _dossier([_chunk("ASX announcement", "primary", "Only one.")])
    primary, _ = format_dossier_for_prompt(d)
    # Should not start or end with the separator
    assert not primary.strip().startswith("---")
    assert not primary.strip().endswith("---")


# ---------------------------------------------------------------------------
# Prompt templates contain {verified_facts}
# ---------------------------------------------------------------------------

def test_ma_full_report_has_verified_facts_slot():
    from app.prompts.ma_report import MA_FULL_REPORT
    assert "{verified_facts}" in MA_FULL_REPORT


def test_ecm_full_report_has_verified_facts_slot():
    from app.prompts.ecm_dcm_report import ECM_FULL_REPORT
    assert "{verified_facts}" in ECM_FULL_REPORT


def test_dcm_full_report_has_verified_facts_slot():
    from app.prompts.ecm_dcm_report import DCM_FULL_REPORT
    assert "{verified_facts}" in DCM_FULL_REPORT


def test_economy_section_has_verified_facts_slot():
    from app.prompts.economy_report import ECONOMY_SECTION
    assert "{verified_facts}" in ECONOMY_SECTION


def test_equities_section_has_verified_facts_slot():
    from app.prompts.economy_report import EQUITIES_SECTION
    assert "{verified_facts}" in EQUITIES_SECTION


# ---------------------------------------------------------------------------
# Prompt templates contain word count targets
# ---------------------------------------------------------------------------

def test_ma_full_report_has_word_count_targets():
    from app.prompts.ma_report import MA_FULL_REPORT
    assert "3,500" in MA_FULL_REPORT or "3500" in MA_FULL_REPORT


def test_ecm_full_report_has_word_count_targets():
    from app.prompts.ecm_dcm_report import ECM_FULL_REPORT
    assert "2,000" in ECM_FULL_REPORT or "2000" in ECM_FULL_REPORT


def test_economy_section_has_word_count_targets():
    from app.prompts.economy_report import ECONOMY_SECTION
    assert "2,500" in ECONOMY_SECTION or "2500" in ECONOMY_SECTION


# ---------------------------------------------------------------------------
# SYSTEM prompt contains style examples
# ---------------------------------------------------------------------------

def test_system_contains_style_examples():
    from app.prompts.ma_report import SYSTEM
    # SYSTEM should include content from the examples/ files
    assert "scheme of arrangement" in SYSTEM.lower() or "valuation" in SYSTEM.lower()


def test_system_has_adaptive_structure_rule():
    from app.prompts.ma_report import SYSTEM
    assert "ADAPTIVE STRUCTURE" in SYSTEM


def test_system_no_em_dash_rule():
    from app.prompts.ma_report import SYSTEM
    assert "em dash" in SYSTEM.lower()
