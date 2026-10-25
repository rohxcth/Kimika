# Kimika — App Spec

## 1. What Kimika is

A **one-page web app** that runs **every day** and publishes **separate, standalone investment-banking-lens reports**: **one report per deal**, plus **one daily Economy & Markets report** (economy, equities, commodities, debt, currencies). It finds stories from **multiple public sources**, **cross-verifies** every figure, researches deals from primary documents, and posts new reports each morning. Reports are read in the browser — one expandable card per report on the page. It's a daily read for **Rohith and investment banking analysts** to understand what is happening around them: deals, the macroeconomic landscape and policy, and where things are likely heading.

- **Brand:** Kimika
- **Deal focus:** United States, Australia, United Kingdom. No minimum deal size; cover as many deals as possible.
- **Tone:** neutral and professional, **following the market**. Kimika reads widely (filings, central banks, economists' and strategists' public commentary, market pricing, news) and reports the consensus view; where views are split, it presents each side and how the market leans. No personal recommendations.
- **Forward-looking:** every report includes an **outlook and scenarios**: what's likely next and how outcomes change under different conditions.
- **Clean reading:** no in-text citations; each report ends with a **bibliography**.
- **Purpose:** concise, professional reporting, all in one place: every report on one page, each downloadable on its own.
- **Never** uses AFR or any paywalled source.

---

## 2. The page

The page is a list of **report cards**, grouped the way Rohith reads:

```
KIMIKA

M&A   |  ECM   |  DCM   |  Economy   |  Equities   |  Commodities   |  Bonds   |  Currencies
────────────────────────────────────────────────────────────────────────────────────────────
[Card] [Card]    [Card]    [Card]        [Card]         [Card]           [Card]     [Card]
[Card]
…
← 8 vertical columns, horizontally scrollable; each column shows its report cards stacked
```

- **Report card:** title (e.g. "BHP / Anglo American: US$49bn scheme"), region badge, deal value, one-line summary. Clicking expands the full report in place.
- **Every report is self-contained** and ends with a bibliography. A small "Verification" toggle on each card shows the figure-by-figure verification log.
- Ongoing deals keep **one report per deal**: when a new stage happens (competing bid, scheme booklet, vote), the report is updated.
- Empty columns are shown with a placeholder when no reports exist for that type today.
- Clean, minimal, readable on desktop.

---

## 3. Coverage

### 3.1 Deals: one full report per deal
- Every deal discovered gets its own full report. The **largest deals by value** are covered first; smaller deals are covered as quota allows (`config.yaml`, `max_full_reports_per_run`).
- **Prioritise size.** When there are more deals than the free-tier quota allows, keep the biggest deals (by deal value in US$ equivalent) and drop the smallest first. Ongoing deals reappear with an update when they hit a new stage (competing bid, scheme booklet, IER, vote, court approval, completion).

### 3.2 Daily market columns (five standalone reports per day)

Five separate reports published each day, one per column: **Economy · Equities · Commodities · Bonds · Currencies**. Each is a standalone expandable card on the page, identical in style to deal cards. report_types: `economy`, `equities`, `commodities`, `bonds`, `currencies`.

**Economy: macroeconomic and policy analysis**
- **Priority:** United States and Australia, with **interest rates in focus**.
- **Macro landscape:** growth, inflation, labour market, consumer and business conditions, housing, the global cycle; what the latest data says about the trend, not just the print.
- **Policy:** monetary (Fed, RBA: decisions, statements, minutes, speeches, market-implied rate path), fiscal (budgets, spending, tax), trade and tariffs, regulation.
- **Outlook and scenarios:** consensus expectations and the main alternative paths (e.g. hold vs cut, inflation re-accelerates vs eases) and what each means for rates, currencies, asset prices and deal activity.
- Other regions (UK, Europe, Japan, China) when significant.

**Markets: breadth over must-haves**
- **Equities:** major indices (US, AU, UK, Europe, Asia), sector moves, notable movers and why.
- **Commodities:** energy, precious metals, base metals, iron ore, agriculture.
- **Debt:** government bond curves (US, AU, UK, DE, JP), curve shape moves, policy rate expectations, credit where publicly available.
- **Currencies:** majors, AUD crosses, dollar index.

---

## 4. Report templates (summary; full detail in `docs/report-templates.md`)

- **M&A (1–2 pages):** deal snapshot · rationale · process & negotiations timeline · valuation (methods, ranges, implied multiples, premium) · structure, terms & financing · advisers · **Market view** · **outlook & scenarios** · bibliography
- **ECM:** snapshot · why now · process · pricing & discount · underwriting & fees · **Market view** · outlook · bibliography
- **DCM:** snapshot · credit story · process (IPTs → pricing) · spread & pricing · use of proceeds · **Market view** · outlook · bibliography
- **Other:** closest template, adapted (LBO, block trade, restructuring, spin-off)
- **Daily market columns (5 separate reports):** Economy (macro landscape · policy · outlook & scenarios) · Equities · Commodities · Bonds · Currencies (each: levels/moves table · what moved and why · what the market expects next · bibliography)
- **Market view:** what the market and commentators think, synthesised from multiple sources: price reaction, arbitrage spread (target price vs offer), shareholder and proxy adviser positions, broker and analyst commentary, credit reaction. Consensus first; dissenting views noted.
- **Not public?** Say "Not publicly disclosed"; typical process goes under **General context**.
- **No in-text citations.** Bibliography at the end of each report.

---

## 5. How it works

Runs **daily at 6:30am Sydney time**. If the laptop was asleep or off, the app runs on next startup.

```
Discover → Cross-verify → Pick → Research → Write → Verify → Save (JSON)
```

1. **Discover:** pull candidates from multiple public sources (`docs/sources.md`):
   - Deals: ASX announcements, SEC EDGAR, UK RNS / Takeover Panel disclosures, several public business news RSS feeds
   - Economy: Fed, RBA and other central banks, government budget/treasury releases, statistics agencies, FRED, public economist and strategist commentary
   - Markets: FMP plus at least one independent source (yfinance, FRED, central bank data)
2. **Cross-verify:**
   - Market data: ≥2 independent sources must agree (tolerances in `config.yaml`)
   - News facts: ≥2 independent publishers, or 1 primary source
   - Deal terms: the primary filing is the source of truth, and news coverage is checked against it
   - **Conflicts:** search for more sources and go with what they support (primary outranks secondary). If none exist, pick the most authoritative source and record the choice and the reason.
3. **Pick:** Gemini Flash-Lite classifies everything in batched requests (M&A/ECM/DCM/Other, region, size, stage). Deals are ranked by **deal value (US$ equivalent)**. The largest get full reports up to the daily quota cap. Undisclosed values rank by the company's market cap as a proxy.
4. **Research:** for full reports, fetch the primary documents and trim to the relevant sections (terms, background/negotiations, IER/fairness opinion summary, financing). For every report, also read **multiple independent commentary sources** to establish the market consensus and the main alternative views.
5. **Write:** Gemini Flash writes full deal reports and the 5 daily market column reports as structured JSON following the templates; Flash-Lite handles classification and helper summaries.
6. **Verify:** derived figures computed in Python (`app/finance.py`); stated figures must have a short quote found in the source; every figure gets a status (✅ Verified · ✅ Resolved · 🔁 Recomputed · ❓ Single source), stored in the report's JSON verification log, not printed in the report body.
7. **Save:** one folder per report, `reports/YYYY-MM-DD/<report-slug>/report.json`, plus `reports/YYYY-MM-DD/index.json` listing the day's reports for the page. Ongoing deals: the report lives under the deal's slug and keeps a version history.

### Cost: zero (free tiers only)
- **AI:** Google Gemini API free tier: no billing account, no credit card. Key from Google AI Studio.
- **Quotas are the constraint:** small daily request limits per project (tighter on Flash, larger on Flash-Lite), resetting at midnight Pacific time (≈ 6–7pm Sydney, so the 6:30am run starts with a full quota). Per-model caps live in `config.yaml`; the run stops starting new full reports before the cap and publishes what's done. 429 errors are handled with back-off, never crashes.
- **Request-efficient design:** batch classification of many items into one request; one request per full report; Flash-Lite for volume work, Flash only for full reports.
- **Data:** FMP free plan, FRED, SEC EDGAR, ASX, RNS, central banks, yfinance: all free.
- **Privacy:** free-tier prompts may be used and reviewed by Google, so only public data is ever sent.
- Cache every document and LLM response by content hash; never re-process an unchanged document.
- Send trimmed sections, not whole 200-page booklets.
- Log requests per model per run so Rohith can see quota usage.

### Safeguards
- All fetching goes through `app/fetch.py`, which **refuses blocked domains** and logs every URL.
- One failed source or story never stops the run.

---

## 6. Report display

Reports are read in the browser — full content is shown inline when a card is expanded. No PDF generation in the current version (intentional decision: get the product running first; PDF export can be added later if wanted).

Report content rules still apply regardless of display format:
- No in-text citations. Clean prose.
- Bibliography at the end of each report, grouped: Filings & announcements · Central banks & official data · Market data · Commentary & news.
- Disclaimer visible on every report: *"Prepared from public sources for information purposes only. Not financial advice. Views reflect a synthesis of public market commentary, not Kimika's own recommendations."*

---

## 7. Tech stack

| Part | Choice |
|---|---|
| Backend + page | Python 3.11, **FastAPI**, one **Jinja2** template, Tailwind via CDN, minimal vanilla JS |
| Scheduling | **APScheduler**, plus a missed-run catch-up on startup |
| AI | **Google Gemini API (free tier)** via the official `google-genai` Python SDK: Flash-Lite for volume tasks, Flash for full reports; model names in `config.yaml` |
| Market & company data | **FMP API** + yfinance + FRED / central bank data (cross-checks) |
| Filings | SEC EDGAR, ASX announcements, UK RNS / Takeover Panel, central bank feeds |
| PDF | Not implemented (intentional; can be added later) |
| Storage | Plain files in `reports/YYYY-MM-DD/` (no database) |
| Tests | pytest, synthetic data, no network |

---

## 8. Folder structure

```
kimika/
├── CLAUDE.md
├── kimika-spec.md
├── README.md
├── docs/                   # glossary, sources, report templates, lessons
├── config.yaml             # schedule, models + daily request caps, limits, tolerances, blocklist
├── .env.example            # GEMINI_API_KEY=, FMP_API_KEY=, FRED_API_KEY=, SEC_USER_AGENT=
├── app/
│   ├── main.py             # FastAPI: page, scheduler + catch-up
│   ├── pipeline.py         # discover → cross-verify → pick → research → write → verify → save
│   ├── scheduler.py        # APScheduler daily run + missed-run catch-up
│   ├── sources.py          # ASX, EDGAR, RNS, central banks, FMP, yfinance, FRED, RSS
│   ├── crosscheck.py       # multi-source agreement + conflict resolution
│   ├── fetch.py            # blocklist-enforcing fetcher + cache
│   ├── finance.py          # all finance calculations
│   ├── llm.py              # Gemini calls, model routing, quota tracking, 429 back-off
│   ├── prompts/            # one prompt per report type
│   └── templates/          # page.html
├── tests/
└── reports/                # generated (commit 1–2 sample days)
```

---

## 9. Build order (stop and confirm after each step)

### Tier 1: M&A reports working end to end
1. Scaffold, `config.yaml`, `.env.example`, `.gitignore`
2. `finance.py` + tests
3. `fetch.py` (blocklist + cache) + tests, including a test proving an AFR URL is refused
4. `crosscheck.py` + tests (agreement, tolerance, conflict resolution with a third source, single-source fallback)
5. Discover M&A: SEC EDGAR + ASX + UK RNS
6. Pick → Research → Write → Verify → Save, for full M&A reports
7. `llm.py`: Gemini client, model routing, per-model request caps, 429 back-off
8. The page: 8-column layout, report cards per deal type
9. (PDF step removed — PDF export not implemented in current version)
10. Scheduler (6:30am daily) + missed-run catch-up + `--now`
11. Run on real days; fix errors; record them in `docs/lessons.md`

### Tier 2: all report types
12. ECM, DCM, Other
13. Economy & Markets report: Economy section (Fed, RBA and rates first)
14. Economy & Markets report: Equities, Commodities, Debt, Currencies sections, with multi-source checks
15. Version history for ongoing deals ("Updated" badge)

### Tier 3: optional
16. Deploy online so it runs without the laptop
17. README with screenshots and a sample PDF

---

## 10. Definition of done
- [ ] Opening the app shows today's report cards, generated automatically every day
- [ ] Reports display in full in the browser; 5 daily market column reports per day (Economy, Equities, Commodities, Bonds, Currencies); PDF export deferred
- [ ] Reports read cleanly with no in-text citations; each ends with a bibliography; every report has an outlook & scenarios section reflecting market consensus
- [ ] At least 3 M&A deal reports (US, AU, UK) with negotiation and valuation sections from primary documents; every discovered deal gets its own full report (no deal wrap)
- [ ] Market figures cross-verified against ≥2 sources; conflicts resolved and recorded
- [ ] Runs at zero cost on free tiers; quota log shows requests per model stay within limits
- [ ] Finance figures computed in Python; `pytest` passes; blocklist proven by a test; no secrets in repo
- [ ] `docs/lessons.md` has at least 3 real lessons
