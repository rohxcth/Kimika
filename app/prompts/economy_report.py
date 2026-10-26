"""Prompt templates for the five daily market column reports.

One standalone card per column: Economy, Equities, Commodities, Bonds, Currencies.
Each prompt returns a JSON report with 1 content section + bibliography.
Target length: 2,500-3,500 words per column.
"""

_SHARED_RULES = """\
TONE AND STYLE
- Precise, dense, professional. No hype, no educational asides, no padding.
- Neutral: consensus first; where views split, give each side and how the market leans.
- Phrase views as the market's: "markets are pricing...", "the consensus expects...".

FACTS
- Use only information from the CONTEXT and VERIFIED FIGURES provided.
- If something is not in the context, write exactly: "Not publicly disclosed."
- Never speculate as fact. Paraphrase sources - no verbatim reproduction.
- VERIFIED FIGURES override anything else; use them as-is.

FORMAT
- Valid JSON only - no markdown fences, no prose outside the JSON.
- No in-text citations.
- Percentages to 1 decimal place; rate and spread moves in bps.
- Dates as 26 Oct 2026.
- Do NOT use em dashes (-- or \u2014). Use a colon or plain hyphen instead.

ADAPTIVE STRUCTURE
- Per-section word count targets are shown. Aim for them; never pad to hit them.
- If source material is thin, write what is supported. Omit sub-sections entirely \
rather than padding with generic commentary.
- A shorter, denser report beats a longer padded one.
"""

# ---------------------------------------------------------------------------
# Economy section
# ---------------------------------------------------------------------------

ECONOMY_SECTION = """\
Write a standalone Economy report card for Kimika's daily tracker. \
Target length: 2,500-3,500 words. \
Output valid JSON with this exact schema:

{{
  "title": "Economy: {date}",
  "key_takeaways": ["<US rate/macro headline>", "<AU rate/macro headline>", "<global or policy headline>"],
  "sections": {{
    "1_economy": "<~2,500w markdown prose:\\n\\n## United States (~800w)\\n<rates first: Fed funds rate, latest FOMC decision, dot plot/guidance, market-implied path>\\n<macro: GDP trend, CPI/PCE vs target, payrolls, unemployment, consumer conditions>\\n<policy: fiscal (spending, deficits, debt ceiling), trade/tariffs if significant>\\n<consensus view and main dissenting argument>\\n\\n## Australia (~800w)\\n<cash rate, latest RBA decision, statement tone and forward guidance>\\n<macro: trimmed mean CPI, labour force, GDP, wages, housing>\\n<market-implied rate path; economist consensus; RBA guidance vs market pricing>\\n\\n## Other regions (~400w)\\n<only if a significant development occurred: UK, Europe, China, Japan; otherwise omit entirely>\\n\\n## Outlook and scenarios (~500w)\\n<base case per consensus with supporting rationale>\\n<2-3 alternative scenarios and what each means for: rates, currencies, asset prices, deal activity>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "Central banks & official data"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

DATE: {date}

CONTEXT:
---
{primary_doc}
---
SECONDARY SOURCES:
---
{secondary_sources}
---
"""

# ---------------------------------------------------------------------------
# Equities section
# ---------------------------------------------------------------------------

EQUITIES_SECTION = """\
Write a standalone Equities report card for Kimika's daily tracker. \
Target length: 2,500-3,500 words. \
Output valid JSON with this exact schema:

{{
  "title": "Equities: {date}",
  "key_takeaways": ["<headline index move>", "<key driver>", "<notable mover or sector>"],
  "sections": {{
    "1_equities": "<~2,500w markdown prose:\\n\\n## Levels and moves\\n<table: index | level | 1-day change | 1-week change - US, AU, UK, Europe, Asia>\\n\\n## United States (~700w)\\n<S&P 500, Nasdaq, Dow: levels, moves, sector breakdown, drivers; earnings releases if relevant>\\n\\n## Australia (~700w)\\n<ASX 200: level, move, top sectors and movers; M&A-driven moves if relevant>\\n\\n## Other markets (~400w)\\n<UK, Europe, Japan, China: brief unless a significant move occurred>\\n\\n## Cross-asset context (~300w)\\n<how yields, USD, and commodities influenced equities; rotation themes>\\n\\n## Outlook (~300w)\\n<what the market expects next: positioning, sentiment, near-term catalysts and risks>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Market data | Commentary & news>"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

DATE: {date}

CONTEXT (index levels, price moves, market commentary):
---
{primary_doc}
---
SECONDARY SOURCES:
---
{secondary_sources}
---
"""

# ---------------------------------------------------------------------------
# Commodities section
# ---------------------------------------------------------------------------

COMMODITIES_SECTION = """\
Write a standalone Commodities report card for Kimika's daily tracker. \
Target length: 2,500-3,500 words. \
Output valid JSON with this exact schema:

{{
  "title": "Commodities: {date}",
  "key_takeaways": ["<energy headline>", "<metals headline>", "<bulk/agriculture headline>"],
  "sections": {{
    "1_commodities": "<~2,500w markdown prose:\\n\\n## Levels and moves\\n<table: commodity | price | unit | 1-day change - oil (WTI and Brent), gold, copper, iron ore, key agricultural>\\n\\n## Energy (~700w)\\n<WTI and Brent: level, move, drivers (inventories, OPEC+, demand outlook, geopolitics)>\\n\\n## Precious and base metals (~700w)\\n<gold: level, move, drivers (USD, real rates, risk sentiment, central bank demand)>\\n<copper and base metals: level, move and macro signal (China demand, global PMI)>\\n\\n## Bulk commodities (~400w)\\n<iron ore: level and AU-specific relevance; coking coal and thermal coal if significant>\\n\\n## Agriculture (~300w)\\n<only if a significant move or event; otherwise omit>\\n\\n## Outlook (~400w)\\n<supply/demand balance per commodity; key near-term risks; consensus view>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Market data | Central banks & official data>"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

DATE: {date}

CONTEXT (commodity prices and market data):
---
{primary_doc}
---
SECONDARY SOURCES:
---
{secondary_sources}
---
"""

# ---------------------------------------------------------------------------
# Bonds section
# ---------------------------------------------------------------------------

BONDS_SECTION = """\
Write a standalone Bonds report card for Kimika's daily tracker. \
Target length: 2,500-3,500 words. \
Output valid JSON with this exact schema:

{{
  "title": "Bonds: {date}",
  "key_takeaways": ["<US yield move/level>", "<AU yield or RBA-related>", "<credit or curve headline>"],
  "sections": {{
    "1_bonds": "<~2,500w markdown prose:\\n\\n## Government bond yields\\n<table: market | 2y | 10y | 30y | 10y move (1d) - US, AU, UK, Germany, Japan>\\n\\n## United States (~700w)\\n<10y Treasury level and move; 2s10s curve shape (level and direction); drivers (Fed path, inflation expectations, supply, foreign demand)>\\n\\n## Australia (~700w)\\n<10y ACGB level and move; RBA rate path priced; ACGB vs UST spread and trend; AGB issuance supply>\\n\\n## Other sovereign markets (~400w)\\n<UK, Germany, Japan: moves and policy drivers if significant>\\n\\n## Credit and spreads (~400w)\\n<investment grade and high yield spreads if data available; new issuance pipeline; credit conditions>\\n\\n## Outlook (~300w)\\n<rate path consensus; key duration risks; next catalysts (data, central bank meetings)>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Central banks & official data | Market data>"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

DATE: {date}

CONTEXT (government bond yields, rate expectations):
---
{primary_doc}
---
SECONDARY SOURCES:
---
{secondary_sources}
---
"""

# ---------------------------------------------------------------------------
# Currencies section
# ---------------------------------------------------------------------------

CURRENCIES_SECTION = """\
Write a standalone Currencies report card for Kimika's daily tracker. \
Target length: 2,500-3,500 words. \
Output valid JSON with this exact schema:

{{
  "title": "Currencies: {date}",
  "key_takeaways": ["<USD move/DXY>", "<AUD level and driver>", "<notable cross or EM move>"],
  "sections": {{
    "1_currencies": "<~2,500w markdown prose:\\n\\n## Levels and moves\\n<table: pair | rate | 1-day change - AUD/USD, EUR/USD, GBP/USD, USD/JPY, USD/CNH, DXY>\\n\\n## US dollar (~700w)\\n<DXY level and move; drivers (Fed path, data surprises, risk sentiment, positioning)>\\n\\n## Australian dollar (~700w)\\n<AUD/USD level and move; key drivers (RBA, commodity prices, CNH, risk appetite)>\\n<AUD crosses: AUD/JPY, AUD/EUR - brief unless significant>\\n\\n## Other majors (~500w)\\n<EUR/USD and GBP/USD: drivers (ECB, BoE, data); USD/JPY and BoJ policy if relevant>\\n\\n## Emerging markets (~300w)\\n<only if a significant move or event; otherwise omit>\\n\\n## Outlook (~300w)\\n<consensus view on USD direction; AUD near-term path; key event risks (data, central banks)>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "Market data"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

VERIFIED FIGURES (cross-referenced; use these values exactly - do not override):
{verified_facts}

DATE: {date}

CONTEXT (FX rates, market data):
---
{primary_doc}
---
SECONDARY SOURCES:
---
{secondary_sources}
---
"""

# Inject shared rules into each prompt at import time
ECONOMY_SECTION    = ECONOMY_SECTION.replace("{shared_rules}",    _SHARED_RULES)
EQUITIES_SECTION   = EQUITIES_SECTION.replace("{shared_rules}",   _SHARED_RULES)
COMMODITIES_SECTION = COMMODITIES_SECTION.replace("{shared_rules}", _SHARED_RULES)
BONDS_SECTION      = BONDS_SECTION.replace("{shared_rules}",      _SHARED_RULES)
CURRENCIES_SECTION = CURRENCIES_SECTION.replace("{shared_rules}", _SHARED_RULES)
