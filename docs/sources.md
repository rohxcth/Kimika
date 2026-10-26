# Where to find things (public sources only)

Use **multiple independent sources** and cross-verify (rules in `CLAUDE.md`). Primary documents outrank secondary write-ups. News coverage is for discovering stories and confirming facts; deal figures come from the primary filing.

**Cast wide.** For each deal or market topic, run targeted searches across all applicable sources below. More independent sources = better cross-verification and richer reports.

## Wide web search (no-key, free)

These run for every deal and every market topic. Use targeted queries (company names, ticker, deal terms) not broad sweeps.

| Source | How to use | What it gives |
|---|---|---|
| **Google News RSS** | `https://news.google.com/rss/search?q=<query>&hl=en` | 10–20 recent articles per query, no key, free |
| **Yahoo Finance RSS** | `https://finance.yahoo.com/rss/headline?s=<ticker>` | Company news by ticker |
| **SEC EDGAR full-text search** | `https://efts.sec.gov/LATEST/search-index?q=<query>&dateRange=custom&...` | Full-text search across all filings, free official API |
| **NewsAPI** | `https://newsapi.org/v2/everything?q=<query>` (free tier: 100 req/day) | Structured news with full content, requires free key (`NEWSAPI_KEY` in `.env`) |
| **Takeovers Panel (AU)** | Public decisions and orders at takeovers.gov.au | AU deal regulatory decisions |
| **ACCC merger register** | public.accc.gov.au/MergerRegister | AU competition decisions |
| **FIRB decision register** | firb.gov.au | AU foreign investment decisions |
| **Court Connect (AU)** | Scheme court approvals | Supreme Court scheme hearing results |
| **RBA speech archive** | rba.gov.au/speeches | Governor and board member speeches |
| **Fed speech archive** | federalreserve.gov/newsevents/speeches | FOMC member speeches |
| **BoE speech archive** | bankofengland.co.uk/news/speeches | MPC member speeches |

## Style references (for prompt few-shot anchors — `app/prompts/examples/`)

Public documents with IB-quality prose that can be used as style anchors in synthesis prompts. Never reproduce; paraphrase and use only as stylistic reference.

| Type | Source |
|---|---|
| M&A valuation methodology | IER excerpts from publicly filed AU scheme booklets (ASX) |
| Deal narrative prose | ACCC merger determination documents |
| Macro analysis | RBA Statement on Monetary Policy (rba.gov.au/publications/smp) |
| Market commentary | BoE Monetary Policy Report (bankofengland.co.uk/monetary-policy-report) |
| Deal structure and process | UK Rule 2.7 announcement text (RNS) |

## Deal discovery (US · AU · UK)
| Region | Primary feeds | Secondary (discovery + confirmation) |
|---|---|---|
| US | SEC EDGAR: 8-K (Items 1.01, 2.01, 8.01), DEFM14A/PREM14A, S-4, SC TO-T/SC 14D9, 424B prospectuses, S-1 | Company press releases (public newsroom / wire pages), public business news RSS |
| AU | ASX announcements (market-sensitive), Takeovers Panel releases | Company websites, public business news RSS |
| UK | RNS announcements (Rule 2.4 possible offer, Rule 2.7 firm offer, scheme documents), Takeover Panel disclosure table | Company websites, public business news RSS |

## M&A detail
| Information | Australia | United States | United Kingdom |
|---|---|---|---|
| Headline terms | ASX announcement; Scheme Implementation Deed | 8-K + merger agreement (Exhibit 2.1) | Rule 2.7 announcement |
| **Negotiation history** | Scheme booklet "Background to the Scheme"; Target's/Bidder's statement | Proxy / S-4 **"Background of the Merger"** | Scheme document "Background to the offer" |
| **Valuation** | **Independent Expert's Report** (scheme booklet / target's statement) | **"Opinion of [Bank]"** fairness opinion sections (proxy) | Financial adviser statements; Rule 2.7 synergy and profit statements |
| Financing | Announcement, SID, related placement/debt announcements | Merger agreement "Financing", commitment letters | "Cash confirmation" in Rule 2.7 |
| Market view | Share price data; substantial holder notices; public statements by shareholders/proxy advisers | Price data; 13D filings; public proxy adviser recommendations | Price data; Form 8 disclosures; public shareholder statements |

Timing: scheme booklets, proxies and scheme documents arrive **weeks or months after** announcement. Track ongoing deals and update when they land.

## ECM
| Information | Where |
|---|---|
| Terms, discount, use of funds | Announcement + investor presentation (ASX/RNS); 8-K/424B (US) |
| Process dates | Trading halt, completion announcement, Appendix 2A, cleansing notice (AU) |
| Underwriting, fees | Offer booklet, prospectus "Underwriting" section (gross spread) |

## DCM
| Information | Where |
|---|---|
| Hybrids / capital notes (AU) | Prospectus + ASX announcements (bookbuild and final margin) |
| Corporate bonds | Company releases; SEC 424B2 pricing supplements; RNS |
| Ratings & outlook | Public rating agency press releases |
| Facilities / refinancing | ASX/RNS announcements, 8-K |

## Economy (US and AU first; rates in focus)
| Region | Sources |
|---|---|
| United States | Federal Reserve (FOMC statement, minutes, SEP/dot plot, speeches), BLS (CPI, payrolls), BEA (GDP, PCE), FRED |
| Australia | RBA (decisions, statements, minutes, SMP, speeches, statistical tables), ABS (CPI, labour force, GDP, wages) |
| UK / Europe / Asia | Bank of England, ONS, ECB, Eurostat, Bank of Japan, PBoC (when significant) |
| Rate expectations | Publicly available market-implied pricing where terms of use permit; otherwise derive from public yield data and label it |

## Policy and outlook (for macro analysis and scenarios)
| Need | Sources |
|---|---|
| Fiscal policy | US Treasury, CBO, Congress budget documents; Australian Treasury budget papers and MYEFO; UK HM Treasury, OBR |
| Trade and tariffs | USTR, US Commerce, DFAT, official government announcements |
| Forecasts and outlooks | IMF World Economic Outlook, OECD Economic Outlook, central bank forecasts (Fed SEP, RBA Statement on Monetary Policy) |
| Economist and strategist views | Publicly available economics research from banks and asset managers (e.g. the major Australian banks' public economics notes), public interviews and speeches, public news coverage of forecasts. Use several to establish consensus and the main dissenting views |
| Market-implied expectations | Publicly available rate-expectation pricing where terms allow; yield curves; break-evens from official data |

## Markets (cross-verify with ≥2 sources)
| Asset class | Sources |
|---|---|
| Equities | FMP; yfinance; exchange/index provider public pages |
| Commodities | FMP; yfinance; official sources where public (e.g. EIA for energy) |
| Debt (bonds & rates) | RBA statistical tables; US Treasury daily yields; FRED; Bank of England; FMP; yfinance |
| Currencies | FMP; yfinance; RBA/central bank reference rates; FRED |

Always record the as-at date/time of market data. Sources quoted at different times are not a conflict; compare like for like (same close).

## Blocked (never use)
AFR, Bloomberg, WSJ, FT, paywalled Reuters, The Australian, The Times, Mergermarket, PitchBook, Capital IQ, Refinitiv, or any page that needs a login.
