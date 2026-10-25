# Kimika deal glossary

Reference for extraction prompts, validation logic and report wording. When a term is ambiguous in an announcement, use the definition here.

## ECM (equity capital markets)

| Term | Meaning | Example / note |
|---|---|---|
| Placement | New shares issued to selected institutional/sophisticated investors, without a prospectus. Fast, usually done during a trading halt. | "$50m placement at $1.20" |
| SPP (Share Purchase Plan) | Lets existing retail shareholders buy new shares, usually at the placement price, capped at $30,000 per holder. | Often paired with a placement so retail isn't diluted unfairly. |
| Entitlement offer | Pro-rata offer to all existing holders, e.g. "1 for 5" = 1 new share per 5 held. Can be renounceable (rights tradeable) or non-renounceable. | ANREO = accelerated non-renounceable entitlement offer (institutional part first). |
| Offer price | Price per new share. | |
| Discount | (reference price − offer price) / reference price × 100. | Ref $1.00, offer $0.90 → 10% discount. |
| Last close | Last traded closing price before the announcement. Stocks are usually halted during a raise, so this may be several days before the announcement date. | Use the last day with volume > 0. |
| VWAP | Volume-weighted average price: Σ(price × volume) / Σ(volume) over N trading days. | Kimika approximates it with daily close × volume, which is not exact. |
| Underwritten | A bank guarantees the raise amount, taking up any shortfall. | |
| Lead manager / bookrunner | The bank(s) running the raise. | e.g. Canaccord, Bell Potter, Morgans, UBS. |
| Dilution | New shares / shares on issue before the raise. | |
| LR 7.1 / 7.1A | ASX Listing Rule placement capacity: generally 15% of capital in 12 months without shareholder approval, plus up to 10% more under 7.1A if approved at the AGM (eligible smaller entities). | Info note only; Kimika never declares a breach. |
| Cleansing notice | Notice that lets placement shares be traded freely. Not a deal in itself. | Classify as `not_a_deal`. |
| Block trade | Sale of an existing large shareholding via a bank. No new shares issued. | Secondary, not primary, capital. |

## M&A

| Term | Meaning | Example / note |
|---|---|---|
| Scheme of arrangement | Friendly acquisition approved by target shareholders (75% of votes cast + 50% of holders voting, unless the court waives the headcount test) and the court. All-or-nothing. | Expect conditions: shareholder vote, court approval, independent expert. |
| Takeover bid | Offer made directly to target shareholders. Can be on-market or off-market, friendly or hostile. | Expect a minimum acceptance condition (often 50.1% or 90%) unless unconditional. |
| Bidder's / Target's statement | Formal takeover documents from the acquirer and target respectively. | |
| Scheme Implementation Deed (SID) | Binding agreement between acquirer and target to proceed with a scheme. | Usually contains break fee and exclusivity terms. |
| Consideration | What target holders receive: cash, scrip (acquirer shares) or both. | Scrip value moves with the acquirer's share price. |
| Scrip ratio | Acquirer shares received per target share. | 0.5 × acquirer at $10 = $5 of scrip. |
| Premium | (offer value − reference price) / reference price × 100. | |
| Undisturbed price | Target's price before deal news or rumours leaked. Premiums are measured against it so they aren't understated by a run-up. | Look for "undisturbed close on [date]". |
| Implied equity value | Offer price per share × shares on issue (fully diluted if stated). | |
| Enterprise value (EV) | Equity value + net debt (+ other adjustments). | Only extract if stated. |
| Break fee | Fee paid by target if the deal fails for specified reasons. Takeovers Panel guidance treats ~1% of equity value as a general benchmark. | Report % only, don't judge. |
| Exclusivity | No-shop / no-talk / matching rights given to the acquirer. | |
| Conditions precedent | E.g. FIRB approval, ACCC clearance, shareholder vote, court approval, independent expert concluding "in the best interests". | |
| Board recommendation | Usually "unanimously recommends, in the absence of a superior proposal and subject to the independent expert…" | |

## DCM (debt capital markets)

| Term | Meaning | Example / note |
|---|---|---|
| Senior notes / bonds | Debt securities ranking ahead of subordinated debt and equity. | |
| Subordinated notes | Rank behind senior debt; higher coupon. | |
| Hybrid | Debt-like security with equity features (e.g. bank capital notes, convertible to equity in stress). | Major banks issue these regularly. |
| Convertible notes | Debt that can convert into shares at a set price. | Capture conversion price if stated. |
| Fixed coupon | Constant interest rate, e.g. 6.25% p.a. | |
| Floating coupon | Benchmark + margin, e.g. 3M BBSW + 250bps. | 100bps = 1%. |
| BBSW | Bank Bill Swap Rate, the main AUD floating benchmark. | |
| Tenor | Time from issue to maturity. | 5-year notes issued Nov 2026 mature ~Nov 2031. |
| Arranger / joint lead manager | Bank(s) running the issue. | |
| Facility / refinancing | Bank loan arrangements (term loan, revolver). Material if large relative to the company. | |

## Classification rules of thumb
- A **trading halt** "pending an announcement regarding a capital raising / acquisition" → Halts to Watch, not a deal report.
- **Placement + SPP** in one announcement → one ECM deal, `raise_type = placement_and_spp`.
- **Acquisition funded by a placement** → two deals (M&A + ECM), linked in the report.
- **Appendix 2A / 3B / cleansing notices** → `not_a_deal` (administrative follow-ups).
- When unsure between deal types, mark confidence `low` rather than guessing.

## How a deal runs inside a bank (process)

| Term | Meaning | Note |
|---|---|---|
| Mandate / engagement letter | The client formally hires the bank, setting scope and fees. | Fees are often a % of deal value for M&A, a gross spread for ECM/DCM. |
| Buy-side / sell-side | Advising the acquirer vs advising the seller/target. | Sell-side banks run the process; buy-side banks advise on price and financing. |
| Competitive auction | Sell-side process: teaser → NDA → information memorandum → indicative bids → shortlist → due diligence (data room) → binding bids → signing. | Bilateral deals skip the auction and negotiate one-on-one. |
| NBIO | Non-binding indicative offer: the first price, subject to due diligence. | ASX targets often announce receipt of an NBIO and whether they granted due diligence. |
| Unsolicited approach / bear hug | A public or private offer the board didn't invite, sometimes made public to pressure the board. | Often followed by "rejected as undervaluing the company". |
| Due diligence (DD) | Buyer's review of financials, legal, operations and tax in a data room. | Exclusivity usually covers this period. |
| BAFO | Best and final offer. | Final round in an auction. |
| Exclusivity | No-shop, no-talk, notification and matching rights for the bidder. | Protects the bidder's time and costs. |
| Fairness opinion | US: a bank's opinion that the price is fair from a financial point of view, with the analyses behind it. | Disclosed in the proxy, including fees. |
| Independent Expert's Report (IER) | AU: required for schemes involving related parties and commonly commissioned anyway; concludes whether the deal is "fair and reasonable" / "in the best interests". | The best public source of AU valuation work. |
| Wall-crossing | Bringing investors "over the wall" with inside information before an ECM deal is announced. | They're restricted from trading until it's public. |
| Bookbuild | Banks collect investor bids (price and size) to set the price and allocate. | Book size vs deal size = coverage, a demand signal. |
| Initial price thoughts (IPTs) → guidance → pricing | DCM marketing stages; the margin typically tightens as demand builds. | E.g. IPT 3M BBSW + 200bps area → priced at +180bps. |
| New issue concession | Extra spread a new bond pays versus the issuer's existing bonds to attract buyers. | |
| Pitch book | Materials a bank uses to win a mandate: valuation views, buyers list, market update. | Analysts build these. |

## Valuation

| Term | Meaning | Worked example |
|---|---|---|
| DCF | Value = present value of forecast free cash flows + terminal value, discounted at WACC. | Highly sensitive to WACC and terminal growth; experts show ranges. |
| WACC | Weighted average cost of capital: blend of cost of equity (CAPM) and after-tax cost of debt. | |
| Terminal value | Value of cash flows beyond the forecast period (perpetuity growth or exit multiple). | Often 60–80% of a DCF's value. |
| Trading comps | Value from multiples of listed peers (EV/EBITDA, P/E, EV/Revenue). | Peer EV/EBITDA 8x × target EBITDA A$500m = A$4.0bn EV. |
| Precedent transactions | Multiples paid in past comparable takeovers. | Includes a control premium, so usually higher than trading comps. |
| Control premium | Extra paid above the trading price to get control. | ASX takeovers often in the ~20–40% range, but varies widely. |
| Synergies | Cost savings or revenue gains from combining. Buyers share some with target holders via the price. | Only report synergy amounts the parties stated. |
| Sum-of-the-parts (SOTP) | Value each division separately and add up. | Conglomerates, diversified miners. |
| NAV (resources) | Net asset value of mines/fields from life-of-asset DCFs. | Common in mining and energy IERs. |
| LBO analysis | Value a PE buyer could pay to hit target returns (IRR ~20%) given leverage. | Sets a "floor" when PE is a likely bidder. |
| Football field | Bar chart of value ranges by method, with the offer price marked. | The standard summary page of a valuation. |
| Equity value vs EV | Equity value = price × shares. EV = equity value + net debt (+ minorities, preferred, less associates). | Multiples like EV/EBITDA use EV; P/E uses equity value. |
| Accretion / dilution | Whether the deal increases or decreases the acquirer's EPS. | Driven by price paid, financing mix, synergies. |
| Fair and reasonable | IER test: fair = offer ≥ assessed value of the target (control basis); reasonable = advantages outweigh disadvantages even if not fair. | |

## US and UK deal terms

| Term | Meaning | Note |
|---|---|---|
| Rule 2.4 announcement (UK) | Announcement that a possible offer is being considered. | Starts the 28-day "put up or shut up" (PUSU) clock. |
| PUSU (UK) | The bidder must announce a firm offer (Rule 2.7) or walk away within 28 days, unless extended. | Walking away usually means a 6-month lockout. |
| Rule 2.7 announcement (UK) | Firm intention to make an offer: binding terms, financing confirmed. | Includes the cash confirmation from the financial adviser. |
| UK scheme vote | 75% by value of shares voted and a majority in number of holders voting, then court sanction. | |
| CMA / NSIA (UK) | Competition review (Competition and Markets Authority); national security review (National Security and Investment Act). | |
| HSR (US) | Hart-Scott-Rodino antitrust filing and waiting period. | Second requests extend the timeline significantly. |
| CFIUS (US) | Committee reviewing foreign investment for national security. | |
| Tender offer (US) | Offer made directly to shareholders (SC TO-T); target responds on SC 14D-9. | Faster than a merger vote. |
| 13D (US) | Filing by a holder crossing 5% with intent to influence. | Activists and bidders. |
| Go-shop | Period after signing in which the target may solicit better offers. | Common in PE deals. |
| Reverse termination fee | Fee paid by the buyer if the deal fails, e.g. on regulatory or financing grounds. | |
| Merger arbitrage spread | Gap between the target's share price and the offer value. | A wider spread signals the market sees more risk to completion. |
| Substantial holder notice (AU) | Disclosure when a holder crosses 5% or moves by 1%. | Signals stake-building or support. |
