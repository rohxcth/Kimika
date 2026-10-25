"""Prompt templates for the five daily market column reports.

One standalone card per column: Economy, Equities, Commodities, Bonds, Currencies.
Each prompt returns a JSON report with 1 content section + bibliography.
"""

_SHARED_RULES = """\
TONE & STYLE
- Precise, dense, professional. No hype, no educational asides, no padding.
- Neutral: consensus first; where views split, give each side and how the market leans.
- Phrase views as the market's: "markets are pricing...", "the consensus expects...".

FACTS
- Use only information from the CONTEXT provided.
- If something is not in the context write exactly: "Not publicly disclosed."
- Never speculate as fact. Paraphrase sources - no verbatim reproduction.

FORMAT
- Valid JSON only - no markdown fences, no prose outside the JSON.
- No in-text citations.
- Percentages to 1 decimal place; rate and spread moves in bps.
- Dates as 26 Oct 2026.
- Do NOT use em dashes (-- or \u2014). Use a colon or plain hyphen instead.
"""

# ---------------------------------------------------------------------------
# Economy section
# ---------------------------------------------------------------------------

ECONOMY_SECTION = """\
Write a standalone Economy report card for Kimika's daily tracker.
Output valid JSON with this exact schema:

{{
  "title": "Economy: {date}",
  "key_takeaways": ["<US rate/macro headline>", "<AU rate/macro headline>", "<global or policy headline>"],
  "sections": {{
    "1_economy": "<markdown prose:\\n\\n## United States\\n<rates first: Fed funds rate, latest FOMC decision, dot plot/guidance>\\n<macro: GDP, CPI/PCE, payrolls, unemployment>\\n<policy: monetary path priced by markets; fiscal/tariffs if significant>\\n<consensus and main dissenting view>\\n\\n## Australia\\n<cash rate, latest RBA decision, statement tone>\\n<macro: CPI trimmed mean, labour force, GDP>\\n<market-implied rate path; RBA guidance>\\n<consensus>\\n\\n## Other regions\\n<only if a significant development occurred; otherwise omit>\\n\\n## Outlook and scenarios\\n<base case per consensus; 2-3 alternative scenarios and what each means for rates, currencies, asset prices and deal activity>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "Central banks & official data"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

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
Write a standalone Equities report card for Kimika's daily tracker.
Output valid JSON with this exact schema:

{{
  "title": "Equities: {date}",
  "key_takeaways": ["<headline index move>", "<key driver>", "<notable mover or sector>"],
  "sections": {{
    "1_equities": "<markdown prose:\\n\\n## Levels and moves\\n<table: index | level | 1-day change | 1-week change — US, AU, UK, Europe, Asia>\\n\\n## What moved and why\\n<US session: S&P 500, Nasdaq, Dow — drivers, sectors leading/lagging>\\n<AU session: ASX 200 — top movers, sectors>\\n<Other markets briefly>\\n\\n## Cross-asset context\\n<how yields, USD, commodities influenced equities; rotation themes>\\n\\n## Outlook\\n<what the market expects next: positioning, sentiment, near-term catalysts>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Market data | Commentary & news>"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

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
Write a standalone Commodities report card for Kimika's daily tracker.
Output valid JSON with this exact schema:

{{
  "title": "Commodities: {date}",
  "key_takeaways": ["<energy headline>", "<metals headline>", "<bulk/agriculture headline>"],
  "sections": {{
    "1_commodities": "<markdown prose:\\n\\n## Levels and moves\\n<table: commodity | price | unit | 1-day change — oil (WTI & Brent), gold, copper, iron ore, key agricultural>\\n\\n## Energy\\n<WTI and Brent: level, move, drivers (inventories, OPEC, demand)>\\n\\n## Metals\\n<gold: level, move, drivers (USD, real rates, risk sentiment)>\\n<copper and base metals: move and macro signal>\\n<iron ore: level and AU relevance>\\n\\n## Agriculture\\n<only if a significant move or event; otherwise omit>\\n\\n## Outlook\\n<supply/demand balance, key near-term risks, consensus view>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Market data | Central banks & official data>"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

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
Write a standalone Bonds report card for Kimika's daily tracker.
Output valid JSON with this exact schema:

{{
  "title": "Bonds: {date}",
  "key_takeaways": ["<US yield move/level>", "<AU yield or RBA-related>", "<credit or curve headline>"],
  "sections": {{
    "1_bonds": "<markdown prose:\\n\\n## Government bond yields\\n<table: market | 2y | 10y | 30y | 10y move — US, AU, UK, Germany, Japan>\\n\\n## United States\\n<10y Treasury level and move; curve shape (2s10s spread); drivers (Fed path, inflation expectations, supply)>\\n\\n## Australia\\n<10y ACGB level; RBA rate path priced; AGB vs UST spread>\\n\\n## Credit and spreads\\n<investment grade and high yield spreads if data available; otherwise omit>\\n\\n## Outlook\\n<rate path consensus, key duration risks, next catalysts>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "<Central banks & official data | Market data>"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

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
Write a standalone Currencies report card for Kimika's daily tracker.
Output valid JSON with this exact schema:

{{
  "title": "Currencies: {date}",
  "key_takeaways": ["<USD move/DXY>", "<AUD level and driver>", "<notable cross or EM move>"],
  "sections": {{
    "1_currencies": "<markdown prose:\\n\\n## Levels and moves\\n<table: pair | rate | 1-day change — AUD/USD, EUR/USD, GBP/USD, USD/JPY, USD/CNH, DXY>\\n\\n## US dollar\\n<DXY level and move; drivers (Fed, data, risk sentiment)>\\n\\n## Australian dollar\\n<AUD/USD level, move; key drivers (RBA, commodities, CNH, risk)>\\n<AUD crosses: AUD/JPY, AUD/EUR briefly>\\n\\n## Other majors\\n<EUR/USD and GBP/USD: drivers; USD/JPY and BoJ policy if relevant>\\n\\n## Outlook\\n<consensus view on USD direction; AUD near-term path; key event risks>",
    "2_bibliography": [
      {{"title": "<title>", "publisher": "<publisher>", "date": "<YYYY-MM-DD>", "url": "<url>", "category": "Market data"}}
    ]
  }},
  "metadata": {{"region": "global", "report_date": "{date}"}},
  "verification_log": []
}}

{shared_rules}

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
ECONOMY_SECTION = ECONOMY_SECTION.replace("{shared_rules}", _SHARED_RULES)
EQUITIES_SECTION = EQUITIES_SECTION.replace("{shared_rules}", _SHARED_RULES)
COMMODITIES_SECTION = COMMODITIES_SECTION.replace("{shared_rules}", _SHARED_RULES)
BONDS_SECTION = BONDS_SECTION.replace("{shared_rules}", _SHARED_RULES)
CURRENCIES_SECTION = CURRENCIES_SECTION.replace("{shared_rules}", _SHARED_RULES)
