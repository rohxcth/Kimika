"""Prompt templates for ECM and DCM deal reports.

Uses the same SYSTEM prompt as M&A reports (imported from ma_report.py).
Each prompt asks for JSON matching the ReportData schema, routed through
app/llm.py using Flash (one request per report).

Target length: 2,000-3,000 words per report.
"""

# ---------------------------------------------------------------------------
# ECM full report prompt
# ---------------------------------------------------------------------------

ECM_FULL_REPORT = """\
Write a full ECM (equity capital markets) deal report for the filing below. \
Target length: 2,000-3,000 words across all sections. \
Output valid JSON with this exact schema:

{{
  "title": "<Issuer: raise type and size, e.g. Acme Corp: A$50m placement at $1.20>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "sections": {{
    "1_snapshot": "<~200w — markdown table: issuer, instrument, raise type (placement/SPP/ANREO/IPO/block/follow-on), size, offer price, discount (vs last close and VWAP with reference dates), new shares, dilution, underwritten, lead managers, settlement date.>",
    "2_why_now": "<~300w — use of funds, balance-sheet rationale (leverage, liquidity, upcoming debt maturity), why this structure and this market window were chosen.>",
    "3_process": "<~300w — trading halt, wall-crossing, bookbuild, pricing, allocation, settlement timeline with dates where public. Duration of each phase.>",
    "4_pricing": "<~300w — discount rationale vs typical discounts for comparable raises and market conditions; stated demand (oversubscription, cornerstone support, coverage ratio if public); what drove final pricing.>",
    "5_underwriting_and_fees": "<~200w — underwriter(s), whether the raise was underwritten and to what extent, gross spread or fee if disclosed. If not publicly disclosed, write 'Not publicly disclosed.' in one line.>",
    "6_market_view": "<~300w — share price reaction on announcement (vs offer price, vs pre-halt close); broker and analyst commentary consensus; major shareholder reactions if public.>",
    "7_outlook": "<~200w — trading expectations post-settlement, any follow-on raises flagged, what the capital will fund and on what timeline.>",
    "8_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Filings & announcements|Central banks & official data|Market data|Commentary & news>"}}
    ]
  }},
  "metadata": {{
    "issuer": "<name>",
    "raise_type": "<placement|spp|anreo|ipo|block|follow_on>",
    "deal_value_usd": <number or null>,
    "region": "<US|AU|UK>",
    "status": "<announced|bookbuild|priced|settled>"
  }},
  "verification_log": []
}}

ADAPTIVE STRUCTURE: if source material cannot fill a section to roughly half its \
target word count, merge it into the adjacent section. Never pad. \
Write "Not publicly disclosed." if information is absent.

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

PRIMARY DOCUMENT (trimmed):
{primary_doc}

SECONDARY SOURCES:
{secondary_sources}

DATE: {date}
"""

# ---------------------------------------------------------------------------
# DCM full report prompt
# ---------------------------------------------------------------------------

DCM_FULL_REPORT = """\
Write a full DCM (debt capital markets) deal report for the filing below. \
Target length: 2,000-3,000 words across all sections. \
Output valid JSON with this exact schema:

{{
  "title": "<Issuer: instrument, size and key pricing, e.g. Acme Corp: A$500m 5yr notes at 3M BBSW +180bps>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "sections": {{
    "1_snapshot": "<~200w — markdown table: issuer, instrument (senior/subordinated/hybrid/convertible), size, currency, tenor, coupon/margin, benchmark, rating (and agency), arrangers, expected pricing date, status.>",
    "2_credit_story": "<~300w — issuer leverage and credit metrics if public; rating rationale from agency press release; any rating change or outlook shift and its implications.>",
    "3_process": "<~300w — mandate announcement, roadshow dates, IPTs, guidance, pricing, book size and coverage ratio, with margin tightening narrative if public.>",
    "4_pricing": "<~300w — spread vs issuer's existing curve (new issue concession); spread vs comparable issuers in the same sector and rating bucket; what drove final pricing relative to initial thoughts.>",
    "5_use_of_proceeds": "<~200w — refinancing, capex, acquisition funding, general corporate purposes. Link to any related M&A deal if applicable.>",
    "6_market_view": "<~300w — secondary trading vs issue price/spread if available; credit market backdrop (IG/HY spread levels); investor demand commentary; sector-specific credit themes.>",
    "7_outlook": "<~200w — further issuance flagged by the issuer; rating trajectory; refinancing wall or upcoming maturity schedule; sector supply outlook.>",
    "8_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Filings & announcements|Central banks & official data|Market data|Commentary & news>"}}
    ]
  }},
  "metadata": {{
    "issuer": "<name>",
    "instrument": "<senior_notes|subordinated_notes|hybrid|convertible|facility>",
    "deal_value_usd": <number or null>,
    "region": "<US|AU|UK>",
    "status": "<announced|priced|settled>"
  }},
  "verification_log": []
}}

ADAPTIVE STRUCTURE: if source material cannot fill a section to roughly half its \
target word count, merge it into the adjacent section. Never pad. \
Write "Not publicly disclosed." if information is absent.

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

PRIMARY DOCUMENT (trimmed):
{primary_doc}

SECONDARY SOURCES:
{secondary_sources}

DATE: {date}
"""
