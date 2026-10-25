"""Prompt templates for ECM and DCM deal reports.

Uses the same SYSTEM prompt as M&A reports (imported from ma_report.py).
Each prompt asks for JSON matching the ReportData schema, routed through
app/llm.py using Flash (one request per report).
"""

# ---------------------------------------------------------------------------
# ECM full report prompt
# ---------------------------------------------------------------------------

ECM_FULL_REPORT = """\
Write a full ECM (equity capital markets) deal report for the filing below. \
Output valid JSON with this exact schema:

{{
  "title": "<Issuer: raise type and size, e.g. Acme Corp: A$50m placement at $1.20>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "sections": {{
    "1_snapshot": "<markdown table: issuer, instrument, raise type (placement/SPP/ANREO/IPO/block/follow-on), size, offer price, discount (vs last close and VWAP, with reference price and date), new shares, dilution, underwritten, lead managers, settlement date>",
    "2_why_now": "<use of funds, balance-sheet position, why this timing and structure>",
    "3_process": "<trading halt, wall-crossing, bookbuild, pricing, allocation, settlement timeline with dates where public>",
    "4_pricing": "<discount rationale vs typical discounts for comparable raises; stated demand (oversubscription, cornerstone support, coverage)>",
    "5_underwriting_and_fees": "<underwriter(s), whether underwritten, gross spread or fee if disclosed; omit if not publicly disclosed>",
    "6_market_view": "<share price reaction (vs offer price, vs last close), broker/analyst commentary consensus, major shareholder reactions if public>",
    "7_outlook": "<trading expectations post-settlement, any follow-on raises flagged, what the capital will fund and timeline>",
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
Output valid JSON with this exact schema:

{{
  "title": "<Issuer: instrument, size and key pricing, e.g. Acme Corp: A$500m 5yr notes at 3M BBSW +180bps>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "sections": {{
    "1_snapshot": "<markdown table: issuer, instrument (senior/subordinated/hybrid/convertible), size, currency, tenor, coupon/margin, benchmark, rating (and agency), arrangers, expected pricing date, status>",
    "2_credit_story": "<issuer leverage and credit metrics if public; rating rationale from agency press release; any rating change or outlook shift>",
    "3_process": "<mandate, roadshow dates, IPTs, guidance, pricing, book size (coverage), with margin tightening narrative if public>",
    "4_pricing": "<spread vs issuer's existing curve (new issue concession); spread vs comparable issuers; what drove final pricing>",
    "5_use_of_proceeds": "<refinancing, capex, acquisition funding, general corporate — link to any related M&A deal if applicable>",
    "6_market_view": "<secondary trading vs issue price/spread if available; credit market backdrop; investor demand commentary>",
    "7_outlook": "<further issuance flagged; rating trajectory; refinancing wall if relevant>",
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

PRIMARY DOCUMENT (trimmed):
{primary_doc}

SECONDARY SOURCES:
{secondary_sources}

DATE: {date}
"""
