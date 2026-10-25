"""Prompt templates for M&A deal reports and the deal wrap.

These strings are passed to the LLM (app/llm.py). They encode the report
rules from CLAUDE.md and docs/report-templates.md so the model output
follows the required structure.

Every prompt:
  - Asks for JSON output matching the ReportData schema
  - Enforces neutral tone, no in-text citations, no speculation as fact
  - Requires an Outlook & scenarios section
  - Requires a bibliography grouped by category
"""

# ---------------------------------------------------------------------------
# System prompt (prepended to every M&A call)
# ---------------------------------------------------------------------------

SYSTEM = """\
You are writing a daily M&A intelligence report for investment banking analysts \
and finance professionals. Follow these rules exactly:

TONE & STYLE
- Precise, dense, professional. No hype, no educational asides, no padding.
- Neutral: present the market consensus first; where views are split, give each \
side and note how the market leans.
- Never write "Kimika thinks" or give personal recommendations.
- Phrase views as the market's: "markets are pricing…", "the consensus expects…", \
"some strategists argue…".

FACTS
- Use only information from the PRIMARY DOCUMENT and SECONDARY SOURCES provided.
- If something is not publicly disclosed, write exactly: "Not publicly disclosed."
- Never present speculation or rumour as fact.
- Do not reproduce verbatim passages from sources (paraphrase).

FORMAT
- Respond with valid JSON matching the schema below — no markdown fences, no prose outside the JSON.
- No in-text citations (no footnote numbers, no [1], no (Source Name)).
- Currency explicit: A$, US$, £. Prose: A$1.2bn / US$450m.
- Percentages to 1 decimal place; spreads and rate moves in bps.
- Dates as 26 Oct 2026; times in Sydney time (AEDT/AEST).
- Do NOT use em dashes (-- or \u2014). Use a colon or plain hyphen instead.
"""

# ---------------------------------------------------------------------------
# M&A full report prompt
# ---------------------------------------------------------------------------

MA_FULL_REPORT = """\
Write a full M&A deal report for the filing below. Output valid JSON with \
this exact schema:

{{
  "title": "<Acquirer / Target: deal value and structure, e.g. BHP / Anglo American: US$49bn scheme>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "sections": {{
    "1_deal_snapshot": "<markdown table: acquirer, target, structure, consideration, offer price, premium (state the reference price and its date), implied equity value, EV (if stated), key multiples (if computable), conditions, expected timetable, status, advisers>",
    "2_strategic_rationale": "<buyer's stated logic, synergies (amount and timing if stated), target board position>",
    "3_process_and_negotiations": "<dated timeline from the filing's background section: first approach, NBIOs, rejections, revised proposals, DD, exclusivity, signing. If not yet available: 'Not publicly disclosed.'>",
    "4_valuation": "<IER/fairness opinion methods and ranges if available; implied multiples of the offer; premium vs undisturbed price and VWAPs; football-field table if ranges available. Label Kimika calculations clearly.>",
    "5_structure_terms_financing": "<conditions (regulatory, vote, court), break fees and % of equity value, exclusivity provisions, funding source>",
    "6_advisers": "<financial and legal advisers, each side, role>",
    "7_market_view": "<synthesise the market's reaction: arb spread (current price vs offer), share price move, major shareholder / proxy adviser positions, broker commentary. Consensus first; dissenting views noted.>",
    "8_outlook_and_scenarios": "<next milestones and dates; base-case path per consensus; alternative scenarios (counter-bid, regulatory objection, vote fails, price bump) and what each means>",
    "9_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Filings & announcements|Central banks & official data|Market data|Commentary & news>"}}
    ]
  }},
  "metadata": {{
    "acquirer": "<name>",
    "target": "<name>",
    "deal_value_usd": <number or null>,
    "structure": "<scheme|takeover|merger|asset deal>",
    "region": "<US|AU|UK>",
    "status": "<announced|scheme_booklet|vote_pending|completed|lapsed>"
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
# Deal wrap entry prompt (Flash-Lite; many deals batched in one call)
# ---------------------------------------------------------------------------

DEAL_WRAP_ENTRY = """\
For each deal below, write one compact deal-wrap entry as a JSON object:

{{
  "region": "<US|AU|UK>",
  "deal_type": "<M&A|ECM|DCM|Other>",
  "parties": "<Bidder / Target or Issuer>",
  "size": "<e.g. A$1.2bn or 'undisclosed'>",
  "key_term": "<e.g. A$4.10 cash, 31.2% premium or key pricing term>",
  "status": "<e.g. SID signed | scheme booklet pending | offer open>",
  "context_line": "<optional one line of context; omit key if not useful>"
}}

Deals (one per line, JSON):
{deals_json}

Return a JSON array of objects in the same order. If a field is not publicly
disclosed, use "Not publicly disclosed".
"""

# ---------------------------------------------------------------------------
# Classification prompt (Flash-Lite; batch many raw candidates)
# ---------------------------------------------------------------------------

CLASSIFY_BATCH = """\
Classify each filing below. For each, return a JSON object:

{{
  "index": <integer — same as input>,
  "deal_type": "<M&A|ECM|DCM|Other|not_a_deal>",
  "region": "<US|AU|UK|Unknown>",
  "confidence": "<high|medium|low>",
  "reason": "<one sentence>"
}}

A deal is "not_a_deal" if it is administrative (cleansing notice, Appendix 2A/3B,
trading halt only, director change, AGM notice).

Filings:
{filings_json}

Return a JSON array.
"""
