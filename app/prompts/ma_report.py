"""Prompt templates for M&A deal reports and the deal wrap.

These strings are passed to the LLM (app/llm.py). They encode the report
rules from CLAUDE.md and docs/report-templates.md so the model output
follows the required structure and density.

Every prompt:
  - Asks for JSON output matching the ReportData schema
  - Enforces neutral tone, no in-text citations, no speculation as fact
  - Has per-section word count targets (never pad to hit them)
  - Supports adaptive structure: merge thin sections, collapse empty ones
  - Accepts a {verified_facts} slot for cross-verified figures
"""

from app.prompts import load_examples as _load_examples

_STYLE_EXAMPLES = _load_examples()

# ---------------------------------------------------------------------------
# System prompt (prepended to every M&A and ECM/DCM call via system_instruction)
# ---------------------------------------------------------------------------

SYSTEM = """\
You are writing a daily M&A intelligence report for investment banking analysts \
and finance professionals. Follow these rules exactly.

TONE AND STYLE
- Precise, dense, professional. No hype, no educational asides, no padding.
- Neutral: present the market consensus first; where views are split, give each \
side and note how the market leans.
- Never write "Kimika thinks" or give personal recommendations.
- Phrase views as the market's: "markets are pricing...", "the consensus expects...", \
"some strategists argue...".

FACTS
- Use only information from the PRIMARY DOCUMENT, SECONDARY SOURCES, and \
VERIFIED FIGURES provided. Do not introduce external knowledge.
- If something is not publicly disclosed, write exactly: "Not publicly disclosed."
- Never present speculation or rumour as fact.
- Do not reproduce verbatim passages from sources (paraphrase).
- VERIFIED FIGURES override anything in the source documents; use them as-is.

FORMAT
- Respond with valid JSON matching the schema — no markdown fences, no prose outside the JSON.
- No in-text citations (no footnote numbers, no [1], no source names in prose).
- Currency explicit: A$, US$, GBP. Prose: A$1.2bn / US$450m.
- Percentages to 1 decimal place; spreads and rate moves in bps.
- Dates as 26 Oct 2026; times in Sydney time (AEDT/AEST).
- Do NOT use em dashes (-- or \u2014). Use a colon or plain hyphen instead.

ADAPTIVE STRUCTURE
- Per-section word count targets are shown in the schema. Aim for them; never pad to hit them.
- If source material cannot fill a section to roughly half its target, merge it into \
an adjacent section rather than padding.
- If no relevant information exists for a section, write "Not publicly disclosed." \
in one line. Do not add filler or generic context.
- A shorter, denser report beats a longer padded one.
""" + (f"""
STYLE REFERENCE (examples of expected prose density and section structure):
{_STYLE_EXAMPLES}
""" if _STYLE_EXAMPLES else "")

# ---------------------------------------------------------------------------
# M&A full report prompt
# ---------------------------------------------------------------------------

MA_FULL_REPORT = """\
Write a full M&A deal report for the filing below. \
Target length: 3,500-5,000 words across all sections. \
Output valid JSON with this exact schema:

{{
  "title": "<Acquirer / Target: deal value and structure, e.g. BHP / Anglo American: US$49bn scheme>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "sections": {{
    "1_deal_snapshot": "<~300w — markdown table: acquirer, target, structure (scheme/takeover/merger/asset deal), consideration, offer price, premium (state the reference price and its date), implied equity value, EV (if stated), key multiples (if computable), conditions, expected timetable, status, advisers. Followed by 1-2 sentences on the board recommendation.>",
    "2_strategic_rationale": "<~400w — buyer's stated logic, stated synergies (amount and timing if stated), target board position and any stated dissent.>",
    "3_process_and_negotiations": "<~500w — dated timeline from the filing's background section: first approach, NBIOs, rejections, revised proposals, DD, exclusivity, signing, competing bidders. If not yet available: 'Not publicly disclosed.'>",
    "4_valuation": "<~700w — IER/fairness opinion methods and ranges if available; implied multiples of the offer; premium vs undisturbed price, 30-day and 90-day VWAPs, 52-week high. Football-field table (method | low | high) if ranges available. Label Kimika calculations clearly. If no expert report: implied multiples vs listed peers, labelled 'Peer comparison (Kimika calculation from public data)'.>",
    "5_structure_terms_financing": "<~400w — conditions (regulatory, vote, court) with jurisdiction; break fees and % of equity value; exclusivity provisions; funding source (cash, debt, equity raise); link to related ECM/DCM deals.>",
    "6_advisers": "<~200w — financial and legal advisers on each side; role of each (e.g. fairness opinion, financing, structuring).>",
    "7_market_view": "<~400w — synthesise from multiple sources: arb spread (current target price vs offer value; what the implied probability of completion is); share price reactions of acquirer and target; major shareholder or proxy adviser positions; broker and analyst commentary; credit reaction if relevant. Consensus first; dissenting views noted.>",
    "8_outlook_and_scenarios": "<~400w — next milestones and expected dates; base-case path per consensus; alternative scenarios (counter-bid, regulatory objection, vote fails, price bump, deal collapse) and what each means for shareholders and the sector.>",
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

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

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
  "index": <integer - same as input>,
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
