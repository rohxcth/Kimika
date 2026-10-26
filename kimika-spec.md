# Kimika — App Spec

## 1. What Kimika is

A **one-page web app** that runs **every day** and publishes **separate, standalone investment-banking-lens reports**: **one report per deal**, plus **five daily market column reports** (Economy, Equities, Commodities, Bonds, Currencies). It pools data from as many public sources as possible, collates them into a dossier, cross-verifies every figure in Python, then synthesises comprehensive reports using Gemini Flash. Reports are read in the browser — one expandable card per report on the page. It's a daily read for **Rohith and investment banking analysts** to understand what is happening around them: deals, the macroeconomic landscape and policy, and where things are likely heading.

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
- **Update existing reports every morning.** On each daily run, re-pool and re-synthesise every ongoing deal report — not just new announcements. New source material (price moves, shareholder disclosures, news coverage, regulatory updates) is incorporated and the report is rewritten. The prior version is archived in version history.

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

- **M&A (3,500–5,000w, 7–9 pages):** transaction overview + snapshot table · strategic rationale · background to the transaction (negotiation timeline) · valuation analysis (IER/fairness opinion, football field, implied multiples, 2–3 tables) · transaction structure and financing · adviser roles · market reaction and positioning · outlook and scenarios (4 named paths) · bibliography
- **ECM (2,000–3,000w, 4–5 pages):** transaction overview · use of proceeds and strategic context · execution and process · pricing analysis · market reaction · outlook · bibliography
- **DCM (2,000–3,000w, 4–5 pages):** transaction overview · credit story · process and bookbuild · pricing analysis · use of proceeds · market reaction and outlook · bibliography
- **Other:** closest template, adapted (LBO, block trade, restructuring, spin-off)
- **Daily market columns (5 separate reports, 2,500–3,500w each):** Economy (macro landscape · policy · commentator consensus · outlook and scenarios) · Equities · Commodities · Bonds · Currencies (each: summary · levels/moves table · what moved and why · cross-asset links · consensus and positioning · outlook and scenarios · bibliography)
- **Adaptive structure:** canonical structures are the target. When source material is thin, merge or collapse sections rather than padding. A shorter denser report beats a longer padded one. Reports grow richer as new documents land (scheme booklet, IER, proxy); the version history tracks each update.
- **Not public?** Collapse to one sentence: "Not yet filed; section will be updated when lodged." Never pad with speculation.
- **No in-text citations.** Bibliography at the end of each report.

---

## 5. How it works

Runs **daily at 6:30am Sydney time**. If the laptop was asleep or off, the app runs on next startup.

```
Pool → Collate → Verify (Python) → Style → Synthesise → Save (JSON)
```

1. **Pool:** fetch every available public source for the deal or topic (`docs/sources.md`). Deals: ASX announcements, SEC EDGAR, UK RNS/Takeover Panel, scheme booklets, IERs, fairness opinions, news from multiple RSS feeds (Google News, NewsAPI, Yahoo Finance), substantial holder notices. Markets: FMP + yfinance + central bank feeds + FRED + public economist commentary + news RSS. Cast wide: more sources = richer cross-verification and richer prose.
2. **Collate** (`app/dossier.py`): aggregate into a structured dossier. Label each chunk: source, type (filing/data/news/commentary), authority (primary/secondary), date. Trim documents to relevant sections before any LLM call (terms, negotiation background, IER summary — not whole 200-page booklets).
3. **Verify** (`app/verify.py`, Python only — no LLM): cross-reference every figure across sources. Market data: ≥2 independent sources must agree (tolerances in `config.yaml`). News facts: ≥2 publishers or 1 primary source. Deal terms: primary filing is truth; news is checked against it. Conflicts: additional sources → go with the majority; primary outranks secondary; if unresolvable, pick the most authoritative and record the choice. Output: `verified_facts` dict + verification log. The LLM receives resolved values only, never raw conflicts.
4. **Style:** load 2–3 example paragraphs from `app/prompts/examples/` (one per section type: deal snapshot, valuation, macro outlook) and inject into the synthesis prompt as few-shot anchors.
5. **Synthesise:** Gemini Flash writes full deal reports and the 5 daily market column reports as structured JSON, following the canonical section structure and word count targets in `docs/report-templates.md`. Flash-Lite handles classification and helper summaries. The prompt instructs the model to follow the adaptive structure rules: merge or collapse thin sections, never pad.
6. **Save:** one folder per report, `reports/YYYY-MM-DD/<report-slug>/report.json`, plus `reports/YYYY-MM-DD/index.json`. Ongoing deals keep version history; each update archives the prior version.

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
│   ├── sources.py          # ASX, EDGAR, RNS, central banks, FMP, yfinance, FRED, RSS, NewsAPI
│   ├── dossier.py          # Stage 2: collate fetched docs into labelled dossier per report
│   ├── crosscheck.py       # multi-source agreement + conflict resolution
│   ├── verify.py           # Stage 3: cross-reference figures in Python → verified_facts dict
│   ├── fetch.py            # blocklist-enforcing fetcher + cache
│   ├── finance.py          # all finance calculations
│   ├── llm.py              # Gemini calls, model routing, quota tracking, 429 back-off
│   ├── prompts/            # one prompt per report type
│   │   └── examples/       # style anchor paragraphs (deal snapshot, valuation, macro outlook)
│   └── templates/          # page.html, report.html
├── tests/
└── reports/                # generated (commit 1–2 sample days)
```

---

## 9. Build order (stop and confirm after each step)

### Tier 1: M&A reports working end to end
1. Scaffold, `config.yaml`, `.env.example`, `.gitignore`
2. `finance.py` + tests
3. `fetch.py` (blocklist + cache) + tests, including a test proving an AFR URL is refused
4. `crosscheck.py` + `verify.py` + tests (agreement, tolerance, conflict resolution with a third source, single-source fallback; `verify.py` outputs `verified_facts` dict fed to the LLM)
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
