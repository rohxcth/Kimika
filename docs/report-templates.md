# Report templates

Readers are Rohith and IB analysts reading daily to understand what's happening around them. Write precisely and densely; no basic explanations. **Neutral tone that follows the market**: read multiple sources and present the consensus view; where views are split, give each side and how the market leans. **No in-text citations**; every report ends with a **Bibliography**.

**Every report is standalone**: one report per deal, plus one daily Economy & Markets report. Each has its own header, key takeaways, body, outlook and bibliography, displayed in full in the browser. Use numbered sub-sections in the order below. If a section has nothing public, write "Not publicly disclosed" in one line; typical process may follow under **General context**.

---


## M&A deal report (one per deal)
1. **Deal snapshot** (table): acquirer, target, structure (scheme / takeover / merger / asset deal), consideration, offer price, premium (and reference), implied equity value, EV, key multiples, conditions, expected timetable, status, advisers
2. **Strategic rationale**: buyer's stated logic, stated synergies (amount and timing), target board's position
3. **Process & negotiations**: dated timeline of first approach, NBIOs, rejections, revised proposals, due diligence, exclusivity, signing, competing bidders. Sources: "Background to the Scheme" / "Background of the Merger" / UK scheme document
4. **Valuation**:
   - Expert/fairness opinion methods and ranges (DCF, trading comps, precedents, SOTP, NAV), when available
   - Implied multiples of the offer (EV/EBITDA, P/E, sector-specific), computed in `app/finance.py`
   - Premium vs undisturbed price, VWAPs, 52-week high
   - Football-field table: method → low / high vs offer
   - No expert report yet: implied multiples vs listed peers, labelled "Peer comparison (Kimika calculation from public data)"
5. **Structure, terms & financing**: conditions (FIRB/ACCC, HSR/CFIUS, CMA/NSIA, vote thresholds, court), break fees (and % of equity value), exclusivity, funding (cash, debt facilities, equity raise), links to related ECM/DCM deals
6. **Advisers**: financial and legal advisers on each side, with the role of each
7. **Market view** (shaded box): what the market and commentators think, synthesised from multiple sources: target price vs offer (arbitrage spread and what it implies), share price reactions, major shareholder / proxy adviser positions, broker and analyst commentary, credit reaction
8. **Outlook & scenarios** (shaded box): next milestones and dates; likely path per consensus; alternative scenarios (counter-bid, regulatory objection, vote fails, price bump) and what each would mean
9. **Bibliography**

## ECM deal report (one per deal)
1. **Snapshot**: type (placement, SPP, ANREO, IPO, block, follow-on), size, price, discount (vs last close and VWAP), new shares, dilution, underwritten?, lead managers
2. **Why now**: use of funds, balance-sheet position, market window
3. **Process**: halt → wall-crossing → bookbuild → pricing → allocation → settlement, with dates where public
4. **Pricing**: discount rationale vs typical discounts for comparable raises, stated demand (oversubscription, cornerstone support)
5. **Underwriting & fees** (where disclosed)
6. **Market view**: share price reaction, commentary consensus
7. **Outlook**: trading expectations, follow-on raises
8. **Bibliography**

## DCM deal report (one per deal)
1. **Snapshot**: issuer, instrument, size, currency, tenor, coupon/margin, benchmark, rating, arrangers
2. **Credit story**: leverage, ratings and outlook (public agency releases)
3. **Process**: mandate → roadshow → IPTs → guidance → pricing → book size, with margin tightening
4. **Pricing**: spread vs comparables and the issuer's curve; new issue concession
5. **Use of proceeds**; link to any M&A it funds
6. **Market view**: secondary trading, commentary consensus
7. **Outlook**: further issuance, rating trajectory
8. **Bibliography**

## Other deals
Closest template, adapted: LBO (sponsor, leverage, debt package, equity cheque), block trade (seller, discount, bookrunner risk), restructuring (creditors, terms), spin-off (structure, valuation of the parts).

---

# Economy & Markets report (one per day, 2–4 pages)
One PDF, five sections in this order: **Economy → Equities → Commodities → Debt → Currencies**. Opens with 3 key takeaways across all sections.

## Economy: macroeconomic and policy analysis
Order: **United States, Australia** (rates first), then other regions if significant.
- **Macro landscape**: growth, inflation, labour market, consumer and business conditions, housing, global cycle; what the latest data says about the trend
- **Policy**: monetary (decisions, statements, minutes, speeches, market-implied rate path), fiscal (budgets, spending, tax), trade and tariffs, regulation
- **Market and commentator consensus**: what economists and strategists broadly expect; where they disagree
- **Outlook & scenarios** (shaded box): the base case per consensus, plus key alternatives (e.g. hold vs cut; inflation re-accelerates vs eases; tariffs escalate vs ease), and what each means for rates, currencies, asset prices and deal activity

## Markets sections (Equities, Commodities, Debt, Currencies)
Breadth first: cover the major instruments in each asset class, then focus on what moved.
- **Levels and moves table** (cross-verified; as-at time stated)
- **What moved and why**: drivers, as the market reads them
- **Cross-asset links**: e.g. yields → AUD → miners
- **What the market expects next**: positioning, pricing and consensus outlook

## Bibliography (end of every report)
Grouped: Filings & announcements · Central banks & official data · Market data · Commentary & news. Each entry: title, publisher, date, link. No in-text citation markers.

---

## Verification log (internal: report JSON and page toggle only, not in the PDF)
| Figure | Value | Sources | Status | Note |
|---|---|---|---|---|
| Target undisturbed close (10 Oct 2026) | A$3.12 | ASX announcement; FMP; yfinance | ✅ Verified | |
| AU 10y yield | 4.42% | RBA; FMP (4.47%); yfinance | ✅ Resolved | FMP differed; RBA and yfinance agree |

Statuses: ✅ Verified (sources agree) · ✅ Resolved (conflict settled; note says how) · 🔁 Recomputed (calculated from verified inputs) · ❓ Single source.
