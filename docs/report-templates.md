# Report templates

Readers are Rohith and IB analysts reading daily to understand what's happening around them. Write precisely and densely; no basic explanations. **Neutral tone that follows the market**: read multiple sources and present the consensus view; where views are split, give each side and how the market leans. **No in-text citations**; every report ends with a **Bibliography**.

**Every report is standalone**: one report per deal, plus five daily market column reports. Each has its own header, key takeaways, body, outlook and bibliography, displayed in full in the browser.

---

## Adaptive structure rules

**The canonical structures below are the ideal target.** Apply them in full when source material supports it. When it does not:

- **Merge** a thin section into an adjacent one rather than writing filler.
- **Collapse** a section to a single sentence when only a headline fact is known: e.g. "Scheme booklet not yet filed; this section will be updated when lodged with ASX."
- **Drop** a section entirely if it is structurally irrelevant to this deal (e.g. no IER for a same-day announcement — drop the valuation deep-dive, fold implied multiples into the snapshot).
- **Never pad** to reach a word count. A shorter, denser report is always better than a longer padded one.
- **Reports grow richer over time.** Every morning the pipeline re-pools and re-synthesises all ongoing deals — not just new announcements. New price data, news coverage, shareholder disclosures, and regulatory updates are incorporated into the existing report. When a scheme booklet, IER, proxy or fairness opinion lands, the valuation and background sections expand accordingly. The version history archives each prior version; the "Updated" badge tells the reader.

Word count targets are for a fully-sourced report. An announcement-day report on a newly-announced deal will naturally be shorter — that is correct, not a failure.

---

## Pipeline: how a report is built (Pool → Collate → Verify → Style → Synthesise)

1. **Pool** — fetch every available public source for this deal or topic (filings, news, market data, commentary). See `docs/sources.md` for the full source list per report type.
2. **Collate** (`app/dossier.py`) — aggregate into a structured dossier: label each chunk by source, type (filing/data/news/commentary), authority (primary/secondary), and date. Trim documents to relevant sections only before any LLM call.
3. **Verify** (`app/verify.py`, Python only, no LLM) — cross-reference every figure across sources; resolve conflicts; assign status (Verified/Resolved/Recomputed/Single source); output `verified_facts` dict. The LLM never sees raw conflicts — only resolved values.
4. **Style** — inject 2–3 example paragraphs from `app/prompts/examples/` (one per section type: deal snapshot, valuation, macro outlook) as few-shot anchors in the synthesis prompt.
5. **Synthesise** (Gemini Flash) — pass the dossier + `verified_facts` + style examples; instruct the model to follow the canonical section structure and word count targets; produce structured JSON.

---

## M&A deal report (one per deal)

**Target: 3,500–5,000 words, 7–9 pages.**

| # | Section | Target | Content |
|---|---|---|---|
| 1 | **Transaction overview** | 350w + snapshot table | Acquirer, target, structure (scheme/takeover/merger/asset), consideration, offer price, premium (vs undisturbed close — state the date), implied equity value, EV, key multiples (EV/EBITDA, P/E), conditions, expected timetable, current status, financial and legal advisers on each side |
| 2 | **Strategic rationale** | 500w | Buyer's stated logic and synergies (amount, timing, credibility); target's business and why now; industry dynamics; target board recommendation and any conditions attached |
| 3 | **Background to the transaction** | 500w | Full negotiation timeline with every date that is public: first approach, NBIOs, rejections, revised proposals, due diligence, exclusivity, signing, competing bidders. Source: "Background to the Scheme" / "Background of the Merger" / UK scheme document |
| 4 | **Valuation analysis** | 700w + 2-3 tables | IER or fairness opinion methods and ranges (DCF, trading comps, precedent transactions, SOTP/NAV) when filed; football field table (method → low/high vs offer); implied multiples of the offer vs listed peers; premium vs undisturbed price, 1-month VWAP, 52-week high. Pre-booklet: implied multiples from announcement only, labelled "Kimika calculation from public data" |
| 5 | **Transaction structure and financing** | 400w | Consideration breakdown (cash/scrip/mix); funding sources (cash on hand, debt facilities, equity raise — link to related ECM/DCM reports); conditions precedent (FIRB, ACCC, HSR, CFIUS, CMA, shareholder vote, court sanction); break fee (amount and % of equity value); exclusivity provisions |
| 6 | **Adviser roles** | 150w | Financial and legal advisers, each side, each role stated |
| 7 | **Market reaction and positioning** | 450w | Target share price response; acquirer reaction; arbitrage spread vs offer and what it implies about completion probability; major shareholder and proxy adviser positions; broker and analyst commentary synthesised from multiple sources; credit reaction where public |
| 8 | **Outlook and scenarios** | 500w | Base case timeline to completion; 4 named scenarios: (a) completes on current terms, (b) price bump or counter-bid, (c) regulatory objection or deal blocked, (d) vote fails or deal collapses — for each, trigger conditions and consequences |
| 9 | **Bibliography** | — | Grouped: Filings & announcements · Official & regulatory · Market data · Commentary & news |

---

## ECM deal report (one per deal)

**Target: 2,000–3,000 words, 4–5 pages.**

| # | Section | Target | Content |
|---|---|---|---|
| 1 | **Transaction overview** | 300w + table | Type (placement, SPP, ANREO, IPO, block, follow-on), size, price, discount vs last close and VWAP (state reference date), new shares issued, post-raise dilution, underwritten (Y/N), lead managers |
| 2 | **Use of proceeds and strategic context** | 400w | What the money is for; balance sheet position pre- and post-raise; why now (pipeline, debt maturity, M&A funding, opportunistic window); link to any M&A this funds |
| 3 | **Execution and process** | 350w | Trading halt → wall-crossing → bookbuild → pricing → allocation → settlement, with dates where public; book coverage and demand signals (oversubscription, cornerstone support) |
| 4 | **Pricing analysis** | 400w | Discount rationale vs typical for comparable raises (size, sector, market conditions); pricing relative to the company's own recent trading; cornerstones or strategic investors named |
| 5 | **Market reaction** | 350w | Share price response on resumption; commentary synthesis; how the market read the raise |
| 6 | **Outlook** | 300w | Trading expectations post-raise; SPP uptake if applicable; follow-on raise risk; use-of-proceeds milestones |
| 7 | **Bibliography** | — | |

---

## DCM deal report (one per deal)

**Target: 2,000–3,000 words, 4–5 pages.**

| # | Section | Target | Content |
|---|---|---|---|
| 1 | **Transaction overview** | 300w + table | Issuer, instrument type, size, currency, tenor, coupon/margin, benchmark, credit rating, arrangers/joint lead managers |
| 2 | **Credit story** | 400w | Leverage, ratings and outlook (public agency releases), business context that supports or strains the credit |
| 3 | **Process and bookbuild** | 350w | Mandate → roadshow → IPTs → guidance → pricing → final book size, with margin tightening and dates |
| 4 | **Pricing analysis** | 400w | Spread vs the issuer's existing curve; new issue concession; comparables pricing; what demand signals say about the credit |
| 5 | **Use of proceeds** | 250w | What the debt funds; link to any M&A it finances |
| 6 | **Market reaction and outlook** | 400w | Secondary trading; commentary consensus; further issuance likelihood; rating trajectory |
| 7 | **Bibliography** | — | |

---

## Other deals

Closest template, adapted. For LBOs add: sponsor, leverage, debt package, equity cheque, target IRR. For block trades: seller, discount, bookrunner risk. For restructurings: creditors, terms, pre- and post-restructuring cap stack. For spin-offs: structure, valuation of the parts.

---

## Daily market column reports (five separate reports per day)

Five standalone reports, one per column: **Economy · Equities · Commodities · Bonds · Currencies**. Each is its own expandable card on the page, with its own slug, report_type, 3 key takeaways, body, and bibliography. report_types: `economy`, `equities`, `commodities`, `bonds`, `currencies`. Generated together by `_write_market_reports()` in pipeline.py.

**Target: 2,500–3,500 words per column, 5–6 pages.**

### Economy: macroeconomic and policy analysis

Order: United States, Australia (rates first), then other regions if significant.

| # | Section | Target | Content |
|---|---|---|---|
| 1 | **Summary** | 300w | 3 key takeaways: the most important things that happened or matter most |
| 2 | **Macro landscape** | 600w | Growth, inflation, labour market, consumer and business conditions, housing, global cycle; what the latest data says about the trend, not just the print |
| 3 | **Policy** | 600w | Monetary (Fed/RBA: decisions, statements, minutes, speeches, market-implied rate path), fiscal (budgets, spending, tax), trade and tariffs, regulation |
| 4 | **Market and commentator consensus** | 500w | What economists and strategists broadly expect; where they disagree; 3+ independent perspectives synthesised; market-implied expectations |
| 5 | **Outlook and scenarios** | 500w | Base case per consensus; 4 named alternatives (e.g. hold vs cut, inflation re-accelerates, tariffs escalate) — trigger conditions and consequences for rates, currencies, asset prices, deal activity |
| 6 | **Bibliography** | — | |

### Markets sections (Equities, Commodities, Bonds, Currencies)

Breadth first: cover all major instruments in the asset class, then focus on what moved.

| # | Section | Target | Content |
|---|---|---|---|
| 1 | **Summary** | 300w | 3 key takeaways |
| 2 | **Levels and moves** | table | Major instruments: levels, 1d/1w/1m moves; as-at time stated; cross-verified from ≥2 sources |
| 3 | **What moved and why** | 600w | Drivers of the main moves, as the market reads them |
| 4 | **Cross-asset links** | 400w | How moves in this asset class connect to others (e.g. yields → AUD → miners) |
| 5 | **Market consensus and positioning** | 500w | What the market expects next; positioning signals; 3+ independent perspectives |
| 6 | **Outlook and scenarios** | 500w | Base case; key alternatives with triggers and consequences |
| 7 | **Bibliography** | — | |

---

## Bibliography (end of every report)

Grouped: Filings & announcements · Central banks & official data · Market data · Commentary & news. Each entry: title, publisher, date, link. No in-text citation markers anywhere in the report body.

---

## Verification log (internal: report JSON and page toggle only)

| Figure | Value | Sources | Status | Note |
|---|---|---|---|---|
| Target undisturbed close (10 Oct 2026) | A$3.12 | ASX announcement; FMP; yfinance | Verified | |
| AU 10y yield | 4.42% | RBA; FMP (4.47%); yfinance | Resolved | FMP differed; RBA and yfinance agree |

Statuses: Verified (sources agree) · Resolved (conflict settled; note says how) · Recomputed (calculated from verified inputs) · Single source.
