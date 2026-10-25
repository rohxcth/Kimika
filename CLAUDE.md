# Kimika — rules for Claude Code

Kimika is a **one-page web app** that runs **every day** and publishes **separate, standalone reports**: **one report per deal** (US, Australia, UK), plus **one daily Economy & Markets report** (sections: Economy, Equities, Commodities, Debt, Currencies). **Each report downloads as its own professional PDF**, sent to **investment banking analysts and finance professionals**. It discovers stories from **multiple public sources**, cross-verifies every figure, researches deals from primary documents, and posts each morning. Full design: `kimika-spec.md`.

**Keep it simple.** One page, plain files for storage, no database, no accounts, no extra pages. Don't add features the spec doesn't ask for.

You are building this app. The app's own prompts (`app/prompts/`) must follow the report rules below.

## Context files
- Deal process & valuation terms: @docs/glossary.md
- Where each kind of information lives: @docs/sources.md
- Report structure for every section: @docs/report-templates.md
- Rules learned from past mistakes: @docs/lessons.md

## Who you're building for
- **Rohith** (the builder): a CS + Maths student preparing for investment banking recruiting. He must understand and defend every part of this app in an interview. When you implement finance logic, explain it in one or two sentences with a concrete example. Be direct and concise.
- **The readers**: Rohith and IB analysts, reading every day to understand what is happening around them. Write at their level: precise, dense, no basic explanations, no hype.

## How to work
1. **One step at a time**, following the tiered build order in `kimika-spec.md` section 9. Finish the step, run `pytest -q`, show the result (test output or the rendered page), then stop and wait for confirmation.
2. **Tier discipline.** Finish Tier 1 before Tier 2. Tier 3 only when asked.
3. Small, readable functions. Comment the finance logic. No clever abstractions.
4. **Never let one failed source or story crash a run.** Log it and continue.
5. After each step, suggest a one-line DEVLOG entry. Rohith writes `DEVLOG.md` himself; it is his evidence of contribution.
6. When Rohith corrects a mistake, offer to record it in `docs/lessons.md`.
7. **Use the subagents** in `.claude/agents/`:
   - `finance-reviewer` after any step that adds or changes a finance calculation, and before marking Tier 1 done
   - `source-scout` before using any data source not already in `docs/sources.md`
   - `report-critic` after the pipeline produces reports, especially when changing prompts

   Summarise their findings for Rohith and fix "Errors" / "Top 3 fixes" before moving on.

## Hard rules: building the app
- **Public sources only.** Never fetch AFR, Bloomberg, WSJ, FT, paywalled Reuters, The Australian, or any login-protected source. All network access goes through `app/fetch.py`, which enforces the blocklist in `config.yaml`. Never bypass it.
- **Respectful access.** Official APIs/feeds where they exist, low request volume, an honest User-Agent (SEC EDGAR requires one with a contact email), respect robots.txt and terms of use.
- **No secrets in code or git.** Keys live in `.env` only (gitignored). Never read, print, log or commit them. Provide `.env.example` with placeholders.
- **Finance numbers are computed in Python** (`app/finance.py`), never by the LLM.
- **Tests use synthetic data, no network.** Mock the Gemini client, FMP, EDGAR, ASX, RNS and feeds.
- **Zero cost.** Kimika must run entirely on free tiers. The AI model is **Google Gemini on the free tier** (no billing account, no credit card). Never add a paid API, never enable billing, never suggest a paid plan as the fix.
- **Free-tier rate limits are the budget.** Gemini's free tier has small daily request quotas per project (tight on Flash, larger on Flash-Lite), resetting at midnight Pacific time. Therefore:
  - Model names and per-model daily request caps live in `config.yaml`, never hard-coded. Check current model names and SDK usage with Context7, and current limits in Google AI Studio.
  - **Flash-Lite** for volume work: discovery, classification (batch many items into one request), markets sections. **Flash** only for full deal reports and the 5 daily market column reports (Economy, Equities, Commodities, Bonds, Currencies).
  - Count every request; stop starting new full reports before the cap is hit and publish what's done. Handle 429 (quota) errors gracefully: back off, never crash.
  - Cache documents and model responses by content hash. Trim documents to relevant sections before sending them.
  - Don't use Gemini's paid features (e.g. Google Search grounding); research uses Kimika's own fetchers.
- **Free-tier data may be reviewed by Google.** Only ever send public data to the model: never keys, `.env` contents or personal information.
- **Laptop-friendly scheduling.** The app runs on Rohith's laptop. If the daily run was missed (laptop asleep or off), run it on the next startup.

## Hard rules: cross-verification
- **Market data:** every level and % move is checked against **at least 2 independent public sources** (e.g. FMP and yfinance, or an official source such as RBA, FRED or a central bank).
- **News facts** (what happened, dates, amounts): confirmed by **at least 2 independent public publishers**, or by 1 primary source (company announcement, filing, central bank statement).
- **Deal terms:** the **primary filing** (announcement, SID, merger agreement, scheme booklet, proxy, prospectus) is the source of truth. Check news coverage is consistent with it.
- **When sources conflict:** look for additional independent sources and go with what they support; primary sources outrank secondary. If no further source exists, pick the most authoritative source using judgement, and **record which value was chosen and why** in the report's verification log.
- Every figure records its sources and gets a status: ✅ Verified (sources agree) · ✅ Resolved (conflict settled, choice recorded) · 🔁 Recomputed (calculated from verified inputs) · ❓ Single source (only one source found).

## Hard rules: report content (enforce in prompts and in the verify step)
1. **Purpose.** A daily read for Rohith and IB analysts to understand what is happening around them: deals, the macro landscape and policy, and where things are likely heading.
2. **IB lens on deals.** Cover the process, negotiations, valuation, structure and financing, using the deal's real numbers.
3. **Macro and policy analysis.** The economy section analyses the macroeconomic landscape and policy (monetary, fiscal, trade and regulatory), not just data releases.
4. **Read widely, reflect the market.** Before writing, read multiple independent sources (filings, central bank communications, economists' and strategists' public commentary, market pricing, news coverage). The report's view is a **synthesis of what the market and informed commentators are saying**: it follows consensus, and where views are split, it presents each side and roughly how the market leans.
5. **Neutral tone.** Measured and professional. No hype, no personal recommendations, no "Kimika thinks". Phrase views as the market's: "markets are pricing…", "the consensus expects…", "some strategists argue…".
6. **Outlook and scenarios.** Every report ends with what is likely to happen next and how outcomes change under different conditions (e.g. "if the RBA holds vs cuts", "if a counter-bid emerges", "if the ACCC objects"). Forecasts and probabilities come from public sources or market pricing, never invented.
7. **Primary documents first** for facts: announcements, scheme booklets, Independent Expert's Reports, SEC proxies and fairness opinions, UK Rule 2.7 announcements and scheme documents, prospectuses, central bank statements.
8. **Never present speculation as fact.** If something isn't public, say "Not publicly disclosed".
9. **No in-text citations.** No footnote numbers, bracketed references or source names cluttering the prose. Each report ends with a **Bibliography** listing the sources used. Verification details live in the report's data file and the page's verification toggle.
10. **Copyright.** Paraphrase sources. No reproduced passages.
11. **Concise and professional.** No padding, no educational asides.
12. **Breadth, prioritised by size.** Cover as many deals and as much of the markets as the free-tier limits allow. When not everything fits, prioritise the **largest deals by value** (US$ equivalent).

## PDF
PDF export is not implemented (intentional decision for initial product). Reports are read in the browser. If added later, follow the content rules: no in-text citations, bibliography at end, disclaimer on every report.

## Commands
- `uvicorn app.main:app --reload` starts the app
- `python -m app.pipeline --now` runs the pipeline once (dev)
- `pytest -q` runs the tests (must pass before a step is done)

## Conventions
- Currency always explicit (A$, US$, £). Prose: A$1.2bn / US$450m. Calculations: full numbers.
- Percentages to 1 decimal place; spreads and rate moves in bps.
- Premium = (offer − reference) / reference. Discount = (reference − offer) / reference. Always state the reference price and its date.
- Dates as 26 Oct 2026; times in Sydney time (AEDT/AEST).
