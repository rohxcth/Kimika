"""Kimika discovery — SEC EDGAR, ASX, UK RNS, Google News RSS, NewsAPI.

Two return types:
  RawDeal  — structured filing metadata for deal discovery (EDGAR/ASX/RNS).
  NewsItem — lightweight news/commentary item for dossier pooling (wide search).

One failed source never stops the run: errors are logged and [] is returned.
All HTTP goes through app.fetch.fetch().
"""

from __future__ import annotations

import logging
import re as _re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import TypedDict

from app.config import cfg
from app.fetch import BlockedDomainError, extract_text, fetch, fetch_json, resolve_redirect

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RawDeal type
# ---------------------------------------------------------------------------

class RawDeal(TypedDict):
    title: str
    url: str
    source: str
    region: str
    filing_type: str
    date: str
    company: str
    extra: dict


class _NewsItemRequired(TypedDict):
    title: str
    url: str
    source: str    # e.g. "GoogleNews:Reuters" | "NewsAPI:Bloomberg" | "EDGAR_fulltext"
    published: str # date string as returned by the source
    snippet: str   # brief description or excerpt (max 500 chars)


class NewsItem(_NewsItemRequired, total=False):
    """Lightweight news/commentary item returned by wide-search sources.

    Used in the dossier pooling stage to gather context for report synthesis.
    The optional ``content`` field is populated by _enrich_news_items() after
    discover_news() collects all items; it holds full article body text so the
    dossier has more than just headline snippets.
    """
    content: str   # full article body fetched from the URL; preferred over snippet


# ---------------------------------------------------------------------------
# M&A keyword filters
# ---------------------------------------------------------------------------

# EDGAR: form types that signal M&A activity
_EDGAR_MA_FORMS = {"8-K", "DEFM14A", "PREM14A", "S-4", "SC TO-T", "SC 14D9"}

# ASX: keywords in announcement headers that signal M&A activity
_ASX_MA_KEYWORDS = {
    "acquisition", "acquire", "scheme", "takeover", "merger", "bid",
    "offer", "transaction", "amalgamat", "combine", "absorb",
}

# RNS: category/headline keywords that signal M&A (Rule 2.4 / Rule 2.7)
_RNS_MA_KEYWORDS = {
    "possible offer", "firm offer", "rule 2.4", "rule 2.7",
    "acquisition", "merger", "takeover", "scheme",
    "recommended", "cash offer", "all-share offer",
}


def _is_ma_asx(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _ASX_MA_KEYWORDS)


def _is_ma_rns(headline: str, category: str = "") -> bool:
    combined = (headline + " " + category).lower()
    return any(kw in combined for kw in _RNS_MA_KEYWORDS)


# ---------------------------------------------------------------------------
# SEC EDGAR discovery
# ---------------------------------------------------------------------------

_EDGAR_SEARCH_URL = (
    "https://efts.sec.gov/LATEST/search-index?q=%22acquisition%22+%22merger%22"
    "&forms={forms}&dateRange=custom&startdt={date}&enddt={date}&_source=file_date,period_of_report,"
    "entity_name,file_num,form_type,period_of_report,biz_location,inc_states"
)
_EDGAR_FILING_BASE = "https://www.sec.gov/Archives/edgar/data"


def discover_edgar(target_date: date) -> list[RawDeal]:
    """Search SEC EDGAR for M&A-related filings on target_date.

    Queries the EDGAR full-text search index for 8-K, DEFM14A, PREM14A,
    S-4 and SC TO-T filed on that date mentioning "acquisition" or "merger".
    Returns a RawDeal for each hit.

    Rate limit: 0.5s between requests per EDGAR ToS.
    """
    date_str = target_date.isoformat()
    forms = "%2C".join(sorted(_EDGAR_MA_FORMS))  # URL-encoded comma
    url = (
        f"https://efts.sec.gov/LATEST/search-index?"
        f"q=%22acquisition%22+OR+%22merger%22+OR+%22scheme%22"
        f"&forms={forms}"
        f"&dateRange=custom&startdt={date_str}&enddt={date_str}"
    )
    try:
        data = fetch_json(url)
    except Exception as exc:
        logger.warning("EDGAR discovery failed for %s: %s", date_str, exc)
        return []

    deals: list[RawDeal] = []
    hits = data.get("hits", {}).get("hits", [])
    for hit in hits:
        src = hit.get("_source", {})
        form_type = src.get("form_type", "")
        if form_type not in _EDGAR_MA_FORMS:
            continue
        entity = src.get("entity_name", "Unknown")
        file_num = src.get("file_num", "")
        period = src.get("period_of_report", date_str)
        filing_url = _edgar_filing_url(hit.get("_id", ""), src)

        deals.append(RawDeal(
            title=f"{entity} — {form_type}",
            url=filing_url,
            source="EDGAR",
            region="US",
            filing_type=form_type,
            date=date_str,
            company=entity,
            extra={"file_num": file_num, "period": period, "cik": src.get("cik", "")},
        ))

        time.sleep(cfg["edgar"]["rate_limit_seconds"])

    logger.info("EDGAR: found %d M&A filings on %s", len(deals), date_str)
    return deals


def _edgar_filing_url(hit_id: str, src: dict) -> str:
    """Build the EDGAR filing index URL from EFTS hit metadata.

    hit_id format from EFTS: "{CIK}/{accession-with-dashes}"
    e.g. "0001018724/0001018724-24-000005"

    Returns the machine-readable filing index JSON URL:
    https://www.sec.gov/Archives/edgar/data/{CIK}/{accession-no-dashes}/index.json

    This is then fetched by the pipeline; _fetch_edgar_document() parses it
    to find and retrieve the actual 8-K body or Ex. 99.1 press release.
    """
    if "/" in hit_id:
        cik_part, accession_part = hit_id.split("/", 1)
        accession_no_dashes = accession_part.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_part}/{accession_no_dashes}/index.json"
        )
    # Fallback: use CIK from source dict for company-level filing list
    cik = src.get("cik", "")
    if cik:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K&dateb=&owner=include&count=5"
    return ""


def fetch_edgar_document(index_url: str) -> str:
    """Fetch the actual filing document text from an EDGAR index.json URL.

    Parses the filing index to find the best document in priority order:
    1. Ex. 99.1 (press release — contains the deal announcement text)
    2. The main 8-K form document
    3. Any .htm or .txt document in the filing

    Returns extracted clean text, or empty string on failure.
    This is the correct way to get US filing content — the index.json URL
    points to a specific filing, not a company search page.
    """
    if not index_url or "index.json" not in index_url:
        # Not an index URL — fetch and extract directly (best-effort)
        try:
            return extract_text(fetch(index_url))[:cfg["pipeline"]["doc_trim_chars"]]
        except Exception:
            return ""

    base_url = index_url.replace("/index.json", "")
    try:
        index = fetch_json(index_url)
        time.sleep(cfg["edgar"]["rate_limit_seconds"])
    except Exception as exc:
        logger.warning("EDGAR index.json fetch failed %s: %s", index_url, exc)
        return ""

    files = index.get("files", [])
    if not files:
        return ""

    # Priority: Ex-99.1 press release > 8-K main doc > any htm/txt
    def _priority(f: dict) -> int:
        desc = (f.get("description") or "").lower()
        name = (f.get("name") or "").lower()
        if "ex-99.1" in desc or "exhibit 99.1" in desc or "press release" in desc:
            return 0
        if f.get("type") in ("8-K", "8-K/A"):
            return 1
        if name.endswith(".htm") or name.endswith(".html"):
            return 2
        if name.endswith(".txt"):
            return 3
        return 9

    candidates = sorted(files, key=_priority)
    for f in candidates[:3]:   # try up to 3 docs; stop on first success
        name = f.get("name", "")
        if not name:
            continue
        doc_url = f"{base_url}/{name}"
        try:
            raw = fetch(doc_url)
            text = extract_text(raw)
            if len(text) > 200:
                logger.info("EDGAR document fetched: %s (%d chars)", doc_url, len(text))
                return text[:cfg["pipeline"]["doc_trim_chars"]]
            time.sleep(cfg["edgar"]["rate_limit_seconds"])
        except Exception as exc:
            logger.debug("EDGAR doc fetch failed %s: %s", doc_url, exc)

    return ""


# ---------------------------------------------------------------------------
# ASX discovery
# ---------------------------------------------------------------------------

_ASX_FEED_URL = "https://www.asx.com.au/asx/1/announcement?count=50&market_sensitive=true"


def discover_asx(target_date: date) -> list[RawDeal]:
    """Fetch ASX market-sensitive announcements for target_date and filter for M&A.

    The ASX feed returns today's announcements; we filter by date and
    M&A keywords in the headline.
    """
    date_str = target_date.isoformat()
    try:
        data = fetch_json(_ASX_FEED_URL)
    except Exception as exc:
        logger.warning("ASX discovery failed for %s: %s", date_str, exc)
        return []

    deals: list[RawDeal] = []
    announcements = data if isinstance(data, list) else data.get("data", [])

    for ann in announcements:
        # Date filter: only announcements from target_date
        ann_date = _parse_asx_date(ann.get("date", ""))
        if ann_date and ann_date.date() != target_date:
            continue

        title = ann.get("header", ann.get("title", ""))
        if not _is_ma_asx(title):
            continue

        ticker = ann.get("code", "")
        doc_url = ann.get("url", "")
        if not doc_url:
            doc_url = f"https://www.asx.com.au/asx/1/company/{ticker}/announcements?count=20&market_sensitive=true"

        deals.append(RawDeal(
            title=title,
            url=doc_url,
            source="ASX",
            region="AU",
            filing_type="ASX_announcement",
            date=date_str,
            company=ann.get("issuer_full_name", ticker),
            extra={"ticker": ticker, "id": ann.get("id", "")},
        ))

    logger.info("ASX: found %d M&A announcements on %s", len(deals), date_str)
    return deals


def _parse_asx_date(date_str: str) -> datetime | None:
    """Parse an ASX date string; return None on failure."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


# ---------------------------------------------------------------------------
# UK RNS discovery
# ---------------------------------------------------------------------------

# LSE provides RNS data via a public JSON API used by their news page
_RNS_API_URL = (
    "https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/newsarticles"
    "?categories=REG&maxResults=100"
)


def discover_rns(target_date: date) -> list[RawDeal]:
    """Fetch UK RNS regulatory announcements for target_date and filter for M&A.

    Looks for Rule 2.4 (possible offer) and Rule 2.7 (firm offer) announcements
    plus generic M&A keywords in the headline.
    """
    date_str = target_date.isoformat()
    try:
        data = fetch_json(_RNS_API_URL)
    except Exception as exc:
        logger.warning("RNS discovery failed for %s: %s", date_str, exc)
        return []

    deals: list[RawDeal] = []
    articles = data if isinstance(data, list) else data.get("articles", data.get("content", []))

    for art in articles:
        # Date filter
        pub_date = _parse_rns_date(art.get("publishedDate", art.get("date", "")))
        if pub_date and pub_date.date() != target_date:
            continue

        headline = art.get("headline", art.get("title", ""))
        category = art.get("category", art.get("type", ""))
        if not _is_ma_rns(headline, category):
            continue

        # Determine filing type from category / headline
        filing_type = _rns_filing_type(headline, category)
        company = art.get("companyName", art.get("issuer", "Unknown"))
        ticker = art.get("tidm", art.get("ticker", ""))
        doc_url = art.get("url", art.get("link", ""))
        if not doc_url and ticker:
            doc_url = f"https://www.londonstockexchange.com/exchange/news/market-news/market-news-detail/{ticker}/{art.get('id','')}.html"

        deals.append(RawDeal(
            title=headline,
            url=doc_url,
            source="RNS",
            region="UK",
            filing_type=filing_type,
            date=date_str,
            company=company,
            extra={"ticker": ticker, "id": art.get("id", ""), "category": category},
        ))

    logger.info("RNS: found %d M&A announcements on %s", len(deals), date_str)
    return deals


def _parse_rns_date(date_str: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str[:26].rstrip("Z"), fmt.rstrip("Z"))
        except (ValueError, TypeError):
            continue
    return None


def _rns_filing_type(headline: str, category: str) -> str:
    h = headline.lower()
    if "rule 2.7" in h or "firm offer" in h or "firm intention" in h:
        return "RNS_Rule27"
    if "rule 2.4" in h or "possible offer" in h:
        return "RNS_Rule24"
    return "RNS_announcement"


# ---------------------------------------------------------------------------
# Economy context discovery (Fed, RBA, FRED)
# ---------------------------------------------------------------------------

# Public URLs - no login required
_FED_MONETARY_RSS = "https://www.federalreserve.gov/feeds/press_monetary.xml"
_RBA_DECISIONS_URL = "https://www.rba.gov.au/monetary-policy/int-rate-decisions/"
# Regex to find RBA decision statement links in the decisions index HTML
_RBA_STATEMENT_LINK_RE = _re.compile(
    r'href="(/monetary-policy/int-rate-decisions/\d{4}/[^"]+\.html)"'
)
_FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series/observations"

# Key FRED series for economy context — 6 most recent observations each
_FRED_SERIES = {
    "FEDFUNDS":  "Federal Funds Effective Rate (%)",
    "CPIAUCSL":  "US CPI All Urban Consumers SA (index)",
    "CPILFESL":  "US Core CPI ex-Food/Energy SA (index)",
    "PCEPI":     "US PCE Price Index (index)",
    "UNRATE":    "US Unemployment Rate (%)",
    "PAYEMS":    "US Nonfarm Payrolls (thousands)",
    "RSAFS":     "US Retail Sales SA (millions USD)",
    "HOUST":     "US Housing Starts (thousands, SAAR)",
    "ICSA":      "US Initial Jobless Claims (thousands)",
    "GS10":      "US 10-Year Treasury CMT (%)",
    "DGS2":      "US 2-Year Treasury CMT (%)",
    "GDPC1":     "US Real GDP (billions 2017 USD, quarterly)",
}

# US Treasury yield curve XML feed — no API key, official source
# Returns the full curve: 1m, 2m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y
_TREASURY_YIELD_CURVE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/"
    "interest-rates/pages/xml?data=daily_treasury_yield_curve"
    "&field_tdr_date_value={yyyymm}"
)
_TREASURY_YIELD_FIELDS = {
    "BC_1MONTH": "1m", "BC_2MONTH": "2m", "BC_3MONTH": "3m",
    "BC_6MONTH": "6m", "BC_1YEAR": "1y", "BC_2YEAR": "2y",
    "BC_3YEAR": "3y", "BC_5YEAR": "5y", "BC_7YEAR": "7y",
    "BC_10YEAR": "10y", "BC_20YEAR": "20y", "BC_30YEAR": "30y",
}

# US sector ETFs for equities breadth analysis
_SECTOR_TICKERS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLV":  "Health Care",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
    "XLP":  "Consumer Staples",
    "XLY":  "Consumer Discretionary",
}

# yfinance tickers for market data
_EQUITY_TICKERS = {
    "^GSPC": "S&P 500",
    "^AXJO": "ASX 200",
    "^FTSE": "FTSE 100",
    "^N225": "Nikkei 225",
    "^HSI": "Hang Seng",
    "^NDX": "Nasdaq 100",
}
_COMMODITY_TICKERS = {
    "GC=F": "Gold (USD/oz)",
    "CL=F": "WTI Crude (USD/bbl)",
    "BZ=F": "Brent Crude (USD/bbl)",
    "HG=F": "Copper (USD/lb)",
    "SI=F": "Silver (USD/oz)",
}
_BOND_TICKERS = {
    "^TNX": "US 10-Year Treasury Yield (%)",
    "^TYX": "US 30-Year Treasury Yield (%)",
    "^FVX": "US 5-Year Treasury Yield (%)",
    "^IRX": "US 3-Month T-Bill Yield (%)",
}
_FX_TICKERS = {
    "AUDUSD=X": "AUD/USD",
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCNH=X": "USD/CNH",
    "DX-Y.NYB": "US Dollar Index (DXY)",
}


def discover_economy_context(target_date: date) -> str:
    """Fetch macro context for the Economy & Markets report.

    Returns a trimmed string combining:
      - Latest Federal Reserve monetary press release (FOMC statement or minutes),
        fetched via the Fed's monetary press releases RSS feed. This gives the
        actual statement text, not just the calendar index page.
      - Latest RBA interest rate decision statement, found by parsing the
        decisions index page and following the link to the most recent statement.
      - FRED data for key US series (requires FRED_API_KEY in env; skipped if absent)

    A failure on any individual source is logged and skipped; the others still run.
    The combined text is trimmed to doc_trim_chars (from config.yaml) before return.
    """
    import os
    trim = cfg["pipeline"]["doc_trim_chars"]
    segments: list[str] = []

    # 1. Federal Reserve — parse monetary press releases RSS to get latest statement URLs,
    # then fetch the actual statement document (not the calendar index page).
    try:
        xml_text = fetch(_FED_MONETARY_RSS)
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        statement_urls: list[str] = []
        if channel is not None:
            for item in channel.findall("item")[:3]:
                link = (item.findtext("link") or "").strip()
                if link:
                    statement_urls.append(link)
        for url in statement_urls[:2]:
            try:
                doc = extract_text(fetch(url))
                segments.append(f"=== Federal Reserve Press Release ({url}) ===\n{doc[:5000]}")
                logger.info("Economy context: fetched Fed statement %s (%d chars)", url, len(doc))
            except Exception as exc:
                logger.warning("Economy context: Fed statement fetch failed %s: %s", url, exc)
    except Exception as exc:
        logger.warning("Economy context: Fed RSS fetch failed: %s", exc)

    # 2. RBA — parse decisions index page to find the latest statement link, then fetch it.
    try:
        index_html = fetch(_RBA_DECISIONS_URL)
        matches = _RBA_STATEMENT_LINK_RE.findall(index_html)
        if matches:
            latest_path = matches[0]  # first match = most recent (page order)
            rba_url = f"https://www.rba.gov.au{latest_path}"
            try:
                doc = extract_text(fetch(rba_url))
                segments.append(f"=== RBA Interest Rate Decision ({rba_url}) ===\n{doc[:5000]}")
                logger.info("Economy context: fetched RBA statement %s (%d chars)", rba_url, len(doc))
            except Exception as exc:
                logger.warning("Economy context: RBA statement fetch failed: %s", exc)
        else:
            # Fallback: use the index page itself (less useful but better than nothing)
            segments.append(f"=== RBA Interest Rate Decisions ===\n{extract_text(index_html)[:3000]}")
            logger.info("Economy context: RBA no statement links found; using index page")
    except Exception as exc:
        logger.warning("Economy context: RBA fetch failed: %s", exc)

    # 3. US Treasury yield curve (no key needed — official public XML feed)
    try:
        yyyymm = target_date.strftime("%Y%m")
        xml_text = fetch(_TREASURY_YIELD_CURVE_URL.format(yyyymm=yyyymm))
        root = ET.fromstring(xml_text)
        # Parse the most recent entry; entries are in <m:properties> elements
        # The namespace varies; find any element whose local name ends in the field name
        curve_rows: list[str] = []
        # Grab all text from the XML, look for field patterns
        xml_str = xml_text  # search raw XML for field values
        for field, label in _TREASURY_YIELD_FIELDS.items():
            m = _re.search(rf"<[^>]*{field}[^>]*>([0-9.]+)<", xml_str)
            if m:
                curve_rows.append(f"{label}: {m.group(1)}%")
        if curve_rows:
            segments.append("=== US Treasury Yield Curve ===\n" + "  ".join(curve_rows))
            logger.info("Economy context: fetched Treasury yield curve (%d points)", len(curve_rows))
    except Exception as exc:
        logger.warning("Economy context: Treasury yield curve failed: %s", exc)

    # 4. FRED data (optional - needs API key; 6 most recent observations per series)
    fred_key = os.environ.get("FRED_API_KEY", "")
    if fred_key:
        fred_snippets: list[str] = []
        for series_id, label in _FRED_SERIES.items():
            try:
                data = fetch_json(
                    f"{_FRED_SERIES_URL}?series_id={series_id}"
                    f"&api_key={fred_key}&sort_order=desc&limit=6&file_type=json"
                )
                obs = data.get("observations", [])
                if obs:
                    rows = "; ".join(
                        f"{o['date']}: {o['value']}"
                        for o in obs if o.get("value") not in (".", None)
                    )
                    fred_snippets.append(f"{label} ({series_id}): {rows}")
            except Exception as exc:
                logger.warning("Economy context: FRED %s failed: %s", series_id, exc)
        if fred_snippets:
            segments.append("=== FRED Macroeconomic Data ===\n" + "\n".join(fred_snippets))
    else:
        logger.info("Economy context: FRED_API_KEY not set - skipping FRED data")

    combined = "\n\n".join(segments)
    return combined[:trim]


# ---------------------------------------------------------------------------
# Market data context discovery (yfinance + FMP)
# ---------------------------------------------------------------------------

# Registry of verifiable market figures.
# Each entry: figure_name → (yfinance_ticker, fmp_symbol_or_None, section)
# figure_name is chosen so infer_figure_type() in verify.py assigns the right
# tolerance automatically: "audusd_rate" → fx, "us_10y_yield_pct" → yield, etc.
_VERIFIABLE_FIGURES: dict[str, tuple[str, str | None, str]] = {
    # FX — yfinance + FMP cross-verify (0.5% tolerance)
    "audusd_rate":        ("AUDUSD=X",  "AUDUSD",   "currencies"),
    "eurusd_rate":        ("EURUSD=X",  "EURUSD",   "currencies"),
    "gbpusd_rate":        ("GBPUSD=X",  "GBPUSD",   "currencies"),
    # Commodities — yfinance + FMP cross-verify (1% tolerance)
    "gold_usd_oz":        ("GC=F",      "GCUSD",    "commodities"),
    "wti_crude_usd_bbl":  ("CL=F",      "CLUSD",    "commodities"),
    # Bonds — yfinance only; ^TNX returns yield in % (e.g. 4.38 = 4.38%)
    "us_10y_yield_pct":   ("^TNX",      None,       "bonds"),
    "us_30y_yield_pct":   ("^TYX",      None,       "bonds"),
    # Equities — yfinance only; index level (price tolerance)
    "sp500_level":        ("^GSPC",     None,       "equities"),
    "asx200_level":       ("^AXJO",     None,       "equities"),
    "nasdaq100_level":    ("^NDX",      None,       "equities"),
}


def discover_market_figures() -> dict[str, dict[str, dict[str, float]]]:
    """Fetch structured market figures from multiple sources for cross-verification.

    Returns a nested dict: section → {figure_name → {source_name: value}}.
    This is the structured counterpart to discover_markets_context() — while
    that function returns prose strings for the LLM, this returns numbers
    ready for verify_claim_groups() in pipeline.py.

    Cross-verified figures (≥2 sources, Verified/Resolved status expected):
      currencies:  AUD/USD, EUR/USD, GBP/USD via yfinance + FMP
      commodities: Gold (USD/oz), WTI crude (USD/bbl) via yfinance + FMP

    Single-source figures (honest Single-source status):
      bonds:    US 10y and 30y Treasury yields via yfinance
      equities: S&P 500, ASX 200, Nasdaq 100 levels via yfinance

    A failed fetch is logged and omitted; the figure still appears with
    whatever sources succeeded — never crashes the pipeline.
    """
    import os

    # Step 1: yfinance prices
    yf_figures: dict[str, float] = {}
    try:
        import yfinance as _yf
        for fig_name, (yf_ticker, _, _section) in _VERIFIABLE_FIGURES.items():
            try:
                hist = _yf.Ticker(yf_ticker).history(period="5d")
                if not hist.empty:
                    yf_figures[fig_name] = float(hist["Close"].iloc[-1])
            except Exception as exc:
                logger.debug("market_figures: yfinance %s failed: %s", yf_ticker, exc)
    except ImportError:
        logger.info("market_figures: yfinance not installed")

    # Step 2: FMP prices (only for figures that have an FMP symbol)
    fmp_figures: dict[str, float] = {}
    fmp_key = os.environ.get("FMP_API_KEY", "")
    if fmp_key:
        fmp_symbol_to_fig: dict[str, str] = {
            fmp_sym: fig_name
            for fig_name, (_yf_t, fmp_sym, _section) in _VERIFIABLE_FIGURES.items()
            if fmp_sym is not None
        }
        if fmp_symbol_to_fig:
            try:
                sym_str = ",".join(fmp_symbol_to_fig.keys())
                data = fetch_json(
                    f"{cfg['fmp']['base_url']}/quote/{sym_str}?apikey={fmp_key}"
                )
                if isinstance(data, list):
                    for q in data:
                        sym = q.get("symbol", "")
                        price = q.get("price")
                        if sym in fmp_symbol_to_fig and price is not None:
                            fmp_figures[fmp_symbol_to_fig[sym]] = float(price)
            except Exception as exc:
                logger.warning("market_figures: FMP batch quote failed: %s", exc)

    # Step 3: Assemble into per-section claim groups
    sections: dict[str, dict[str, dict[str, float]]] = {
        "equities": {}, "commodities": {}, "bonds": {}, "currencies": {},
    }
    for fig_name, (_yf_t, _fmp_sym, section) in _VERIFIABLE_FIGURES.items():
        readings: dict[str, float] = {}
        if fig_name in yf_figures:
            readings["yfinance"] = yf_figures[fig_name]
        if fig_name in fmp_figures:
            readings["FMP"] = fmp_figures[fig_name]
        if readings:
            sections[section][fig_name] = readings

    logger.info(
        "market_figures: %s",
        ", ".join(f"{s}={len(v)}" for s, v in sections.items()),
    )
    return sections


def _fetch_yfinance_tickers(tickers: dict[str, str]) -> str:
    """Fetch latest price + 1-day change for a dict of {ticker: label}.

    Uses yfinance. Returns a formatted string; empty string if yfinance
    is not installed or all fetches fail.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.info("yfinance not installed - skipping yfinance market data")
        return ""

    rows: list[str] = []
    for ticker, label in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                continue
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) >= 2 else last
            change = last - prev
            pct = (change / prev * 100) if prev else 0
            rows.append(f"{label}: {last:.4g} ({pct:+.2f}%)")
        except Exception as exc:
            logger.debug("yfinance %s failed: %s", ticker, exc)
    return "\n".join(rows)


def discover_markets_context(target_date: date) -> dict[str, str]:
    """Fetch market data context for each of the 4 market columns.

    Returns a dict: {"equities": str, "commodities": str, "bonds": str, "currencies": str}

    Each value is a compact string of price levels and moves suitable for
    passing to the LLM as context. Empty strings degrade gracefully.
    Sources: yfinance (no key, always attempted) + FMP (if FMP_API_KEY set).
    """
    import os
    fmp_key = os.environ.get("FMP_API_KEY", "")
    trim = cfg["pipeline"]["doc_trim_chars"]

    def _fmp_quote(symbols: list[str]) -> str:
        """Fetch FMP quotes for a list of symbols; return formatted string."""
        if not fmp_key or not symbols:
            return ""
        sym_str = ",".join(symbols)
        try:
            data = fetch_json(
                f"{cfg['fmp']['base_url']}/quote/{sym_str}?apikey={fmp_key}"
            )
            if not isinstance(data, list):
                return ""
            rows = [
                f"{q.get('name', q.get('symbol', ''))}: "
                f"{q.get('price', 'N/A')} "
                f"({q.get('changesPercentage', 0):+.2f}%)"
                for q in data if q.get("price") is not None
            ]
            return "\n".join(rows)
        except Exception as exc:
            logger.debug("FMP quote failed for %s: %s", sym_str, exc)
            return ""

    # Equities — indices + US sector breakdown
    equities_yf = _fetch_yfinance_tickers(_EQUITY_TICKERS)
    equities_fmp = _fmp_quote(["SPY", "QQQ", "IWM"])
    sector_yf = _fetch_yfinance_tickers(_SECTOR_TICKERS)
    equities = "\n\n".join(filter(None, [
        "=== Equity Indices (yfinance) ===\n" + equities_yf if equities_yf else "",
        "=== Equity ETFs (FMP cross-check) ===\n" + equities_fmp if equities_fmp else "",
        "=== US Sector Performance (yfinance) ===\n" + sector_yf if sector_yf else "",
    ]))

    # Commodities
    commod_yf = _fetch_yfinance_tickers(_COMMODITY_TICKERS)
    commod_fmp = _fmp_quote(["GCUSD", "CLUSD"])
    commodities = "\n\n".join(filter(None, [
        "=== Commodity Futures (yfinance) ===\n" + commod_yf if commod_yf else "",
        "=== Commodity FMP cross-check ===\n" + commod_fmp if commod_fmp else "",
    ]))

    # Bonds — US Treasury yields + AU yield + FRED short-end
    bonds_yf = _fetch_yfinance_tickers(_BOND_TICKERS)
    fred_key = os.environ.get("FRED_API_KEY", "")
    fred_bond_rows: list[str] = []
    if fred_key:
        for series_id, label in [
            ("IRLTLT01AUM156N", "AU 10-Year Govt Bond Yield"),
            ("DGS2",            "US 2-Year Treasury CMT"),
            ("DGS1",            "US 1-Year Treasury CMT"),
        ]:
            try:
                data = fetch_json(
                    f"{_FRED_SERIES_URL}?series_id={series_id}"
                    f"&api_key={fred_key}&sort_order=desc&limit=3&file_type=json"
                )
                obs = [o for o in data.get("observations", []) if o.get("value") not in (".", None)]
                if obs:
                    fred_bond_rows.append(
                        f"{label}: {obs[0]['value']}% ({obs[0]['date']})"
                    )
            except Exception as exc:
                logger.debug("FRED bond %s failed: %s", series_id, exc)
    bonds = "\n\n".join(filter(None, [
        "=== US Treasury Yields (yfinance) ===\n" + bonds_yf if bonds_yf else "",
        "=== Bond Yields (FRED) ===\n" + "\n".join(fred_bond_rows) if fred_bond_rows else "",
    ]))

    # Currencies
    fx_yf = _fetch_yfinance_tickers(_FX_TICKERS)
    fx_fmp = _fmp_quote(["AUDUSD", "EURUSD", "GBPUSD"])
    currencies = "\n\n".join(filter(None, [
        "=== FX Rates (yfinance) ===\n" + fx_yf if fx_yf else "",
        "=== FX FMP cross-check ===\n" + fx_fmp if fx_fmp else "",
    ]))

    return {
        "equities":    equities[:trim],
        "commodities": commodities[:trim],
        "bonds":       bonds[:trim],
        "currencies":  currencies[:trim],
    }


# ---------------------------------------------------------------------------
# Wide web search — Google News RSS (no key)
# ---------------------------------------------------------------------------

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return _re.sub(r"<[^>]+>", "", text).strip()


def discover_google_news_rss(query: str, max_results: int = 20) -> list[NewsItem]:
    """Search Google News RSS for articles matching query.

    Returns up to max_results NewsItems. No API key required. Free.
    Blocked domains are applied later when fetching full article content;
    here we collect titles, links and snippets from the feed metadata only.
    """
    url = _GOOGLE_NEWS_RSS.format(query=urllib.parse.quote(query))
    try:
        xml_text = fetch(url)
    except Exception as exc:
        logger.warning("Google News RSS failed for %r: %s", query, exc)
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("Google News RSS: XML parse error for %r: %s", query, exc)
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    items: list[NewsItem] = []
    for item in channel.findall("item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = _strip_html(item.findtext("description") or "")[:500]
        source_el = item.find("source")
        source_name = (source_el.text or "").strip() if source_el is not None else "Google News"

        if title and link:
            items.append(NewsItem(
                title=title,
                url=link,
                source=f"GoogleNews:{source_name}",
                published=pub_date,
                snippet=description,
            ))

    logger.info("Google News RSS: %d articles for %r", len(items), query)
    return items


# ---------------------------------------------------------------------------
# Wire press releases — PR Newswire and BusinessWire RSS (no key, direct URLs)
# ---------------------------------------------------------------------------

# Financial-news category feeds from the two main US press release wire services.
# Unlike Google News RSS, these return direct article URLs (not redirects).
# Company press releases on these wires are primary sources for deal announcements.
_PRNEWSWIRE_RSS = "https://www.prnewswire.com/rss/news-releases-list.rss?category=FIN"
_BUSINESSWIRE_RSS = "https://www.businesswire.com/rss/home/?rss=G7"


def _parse_wire_rss(xml_text: str, source_prefix: str, query: str, max_results: int) -> list[NewsItem]:
    """Parse a PR Newswire or BusinessWire RSS feed and filter by query terms."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("%s RSS: XML parse error: %s", source_prefix, exc)
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    query_terms = [t.lower() for t in query.split() if len(t) > 3]
    items: list[NewsItem] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = _strip_html(item.findtext("description") or "")[:500]

        if not title or not link:
            continue
        # Relevance filter: skip items with no query term in title or description
        combined = (title + " " + description).lower()
        if query_terms and not any(t in combined for t in query_terms):
            continue

        items.append(NewsItem(
            title=title,
            url=link,
            source=f"{source_prefix}:{title[:30]}",
            published=pub_date,
            snippet=description,
        ))
        if len(items) >= max_results:
            break

    return items


def discover_prnewswire(query: str, max_results: int = 10) -> list[NewsItem]:
    """Search PR Newswire financial RSS for press releases matching query.

    Returns direct article URLs — no Google redirect. Primary source for
    US company deal announcements, ECM pricing, and regulatory approvals.
    Paraphrase only; never reproduce full release text verbatim.
    """
    try:
        xml_text = fetch(_PRNEWSWIRE_RSS)
        items = _parse_wire_rss(xml_text, "PRNewswire", query, max_results)
        logger.info("PR Newswire: %d relevant items for %r", len(items), query)
        return items
    except Exception as exc:
        logger.warning("PR Newswire RSS failed for %r: %s", query, exc)
        return []


def discover_businesswire(query: str, max_results: int = 10) -> list[NewsItem]:
    """Search BusinessWire financial RSS for press releases matching query.

    Returns direct article URLs — no Google redirect. Complements PR Newswire;
    many M&A press releases are distributed through BusinessWire rather than PRN.
    Paraphrase only; never reproduce full release text verbatim.
    """
    try:
        xml_text = fetch(_BUSINESSWIRE_RSS)
        items = _parse_wire_rss(xml_text, "BusinessWire", query, max_results)
        logger.info("BusinessWire: %d relevant items for %r", len(items), query)
        return items
    except Exception as exc:
        logger.warning("BusinessWire RSS failed for %r: %s", query, exc)
        return []


# ---------------------------------------------------------------------------
# Wide web search — NewsAPI (free tier: 100 req/day, requires NEWSAPI_KEY)
# ---------------------------------------------------------------------------

_NEWSAPI_URL = "https://newsapi.org/v2/everything"


def discover_newsapi(query: str, max_results: int = 20) -> list[NewsItem]:
    """Search NewsAPI for articles matching query.

    Requires NEWSAPI_KEY environment variable. Skips gracefully if absent.
    Free tier allows 100 requests/day.
    """
    import os
    api_key = os.environ.get("NEWSAPI_KEY", "")
    if not api_key:
        logger.debug("NewsAPI: NEWSAPI_KEY not set — skipping")
        return []

    params = urllib.parse.urlencode({
        "q": query,
        "pageSize": min(max_results, 100),
        "sortBy": "publishedAt",
        "language": "en",
        "apiKey": api_key,
    })
    try:
        data = fetch_json(f"{_NEWSAPI_URL}?{params}")
    except Exception as exc:
        logger.warning("NewsAPI failed for %r: %s", query, exc)
        return []

    if data.get("status") != "ok":
        logger.warning("NewsAPI: status %r for %r", data.get("status"), query)
        return []

    items: list[NewsItem] = []
    for art in data.get("articles", []):
        title = (art.get("title") or "").strip()
        url_str = (art.get("url") or "").strip()
        if not title or not url_str:
            continue
        source_name = ((art.get("source") or {}).get("name") or "NewsAPI").strip()
        items.append(NewsItem(
            title=title,
            url=url_str,
            source=f"NewsAPI:{source_name}",
            published=(art.get("publishedAt") or "").strip(),
            snippet=(art.get("description") or "")[:500],
        ))

    logger.info("NewsAPI: %d articles for %r", len(items), query)
    return items


# ---------------------------------------------------------------------------
# Wide web search — EDGAR full-text (any query, any form type)
# ---------------------------------------------------------------------------

_EDGAR_FULLTEXT_URL = "https://efts.sec.gov/LATEST/search-index"


def discover_edgar_fulltext(query: str, max_results: int = 10) -> list[NewsItem]:
    """Full-text search EDGAR for filings mentioning query.

    Unlike discover_edgar() which is M&A-specific, this searches any
    form type — useful for pooling all recent filings about a specific
    company or deal when building a dossier.
    Rate limit: 0.5s between requests per EDGAR ToS.
    """
    params = urllib.parse.urlencode({"q": f'"{query}"'})
    url = f"{_EDGAR_FULLTEXT_URL}?{params}"
    try:
        data = fetch_json(url)
    except Exception as exc:
        logger.warning("EDGAR full-text failed for %r: %s", query, exc)
        return []

    items: list[NewsItem] = []
    hits = data.get("hits", {}).get("hits", [])
    for hit in hits[:max_results]:
        src = hit.get("_source", {})
        entity = src.get("entity_name", "Unknown")
        form_type = src.get("form_type", "filing")
        file_date = src.get("file_date", "")
        cik = src.get("cik", "")
        filing_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form_type}"
            if cik else "https://www.sec.gov/cgi-bin/browse-edgar"
        )
        items.append(NewsItem(
            title=f"{entity} — {form_type} ({file_date})",
            url=filing_url,
            source="EDGAR_fulltext",
            published=file_date,
            snippet=f"{form_type} filing by {entity}",
        ))
        time.sleep(cfg["edgar"]["rate_limit_seconds"])

    logger.info("EDGAR full-text: %d filings for %r", len(items), query)
    return items


# ---------------------------------------------------------------------------
# Combined news discovery — all wide-search sources for a query
# ---------------------------------------------------------------------------

def _enrich_news_items(items: list[NewsItem], max_items: int = 5) -> None:
    """Fetch and clean full article text for the top ``max_items`` news items in-place.

    Fetches the article HTML, strips nav/script/footer boilerplate via extract_text(),
    and stores clean prose in item["content"]. This typically reduces a 50,000-char
    HTML page to 2,000-5,000 chars of actual article text.

    Skips EDGAR browse-page items (not articles) and any URL that fetch()
    rejects (blocked domains handled by app/fetch.py automatically).
    A failed fetch is logged and skipped — the item keeps its snippet.
    """
    trim = cfg["pipeline"]["doc_trim_chars"]
    fetched = 0
    for item in items:
        if fetched >= max_items:
            break
        url = item.get("url", "")
        # Skip EDGAR browse/search pages — they're filing indexes, not article text
        if "sec.gov/cgi-bin" in url or "efts.sec.gov" in url:
            continue
        try:
            # Google News RSS links are opaque redirect URLs — resolve to the real
            # article URL first. A browser User-Agent is required for Google to redirect.
            if "news.google.com/rss/articles/" in url:
                try:
                    url = resolve_redirect(url)
                except BlockedDomainError:
                    logger.debug("News enrichment: resolved to blocked domain, skipping %s", url[:80])
                    continue
            raw = fetch(url)
            clean = extract_text(raw)
            if clean and len(clean) > 200:
                item["content"] = clean[:trim]
                fetched += 1
                logger.debug("Enriched news item: %s (%d chars)", item.get("title", "")[:60], len(clean))
        except Exception as exc:
            logger.debug("News enrichment failed for %s: %s", url[:80], exc)


def discover_news(query: str, max_results_per_source: int = 20) -> list[NewsItem]:
    """Pool news and commentary from all wide-search sources for a query.

    Combines Google News RSS + NewsAPI + EDGAR full-text. A failure in any
    single source is logged and skipped; others still run.
    Results are deduplicated by URL, then the top 3 are enriched with full
    article text via _enrich_news_items().
    """
    results: list[NewsItem] = []
    seen_urls: set[str] = set()

    sources = [
        ("GoogleNews",   lambda q: discover_google_news_rss(q, max_results_per_source)),
        ("NewsAPI",      lambda q: discover_newsapi(q, max_results_per_source)),
        ("EDGAR",        lambda q: discover_edgar_fulltext(q, max_results_per_source // 2)),
    ]
    for name, fn in sources:
        try:
            for item in fn(query):
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    results.append(item)
        except Exception as exc:
            logger.error("%s news discovery raised unexpectedly: %s", name, exc)

    # Enrich top 5 items with full article content
    _enrich_news_items(results, max_items=3)

    logger.info("discover_news: %d unique items for %r", len(results), query)
    return results


# ---------------------------------------------------------------------------
# Deal market data — share price history for target / acquirer
# ---------------------------------------------------------------------------

def _infer_ticker(deal: RawDeal) -> str | None:
    """Best-effort ticker inference from deal metadata.

    Checks deal["extra"]["ticker"] first (set by the classifier or ASX discovery),
    then falls back to the company field for AU deals.

    Finance note: ASX discovery sets extra["ticker"] to the raw ASX code (e.g. "BHP")
    without the yfinance-required ".AX" suffix. For any AU deal, ".AX" is appended
    if not already present — yfinance returns US ADR data for bare "BHP" but the
    correct ASX-listed shares are under "BHP.AX".
    """
    explicit = str((deal.get("extra") or {}).get("ticker", "") or "").strip()
    if deal.get("region") == "AU":
        code = explicit or (deal.get("company") or "").strip().upper()
        if code and 2 <= len(code) <= 6:
            # Ensure .AX suffix for ASX equities — never double-append
            return code if "." in code else f"{code}.AX"
    if explicit:
        return explicit
    return None


def discover_deal_market_data(deal: RawDeal) -> str:
    """Fetch 3-month share price history for the target (and acquirer if known).

    Returns a formatted string ready to add to the dossier as a primary data chunk.
    This gives the LLM the undisturbed price, any pre-announcement run-up, and the
    post-announcement arbitrage spread — all needed for premium and spread analysis.

    Finance note: undisturbed price = last close before the announcement date.
    Premium = (offer − undisturbed) / undisturbed. Arbitrage spread = offer − current
    price; a tight spread signals the market believes the deal will complete.

    Falls back gracefully if tickers are not available or yfinance fails.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.info("deal market data: yfinance not installed")
        return ""

    segments: list[str] = []

    def _price_table(ticker: str, label: str) -> str:
        try:
            hist = yf.Ticker(ticker).history(period="3mo")
            if hist.empty:
                return ""
            rows = [
                f"{dt.strftime('%Y-%m-%d')}: close {row['Close']:.4g}  vol {int(row['Volume']):,}"
                for dt, row in hist.iterrows()
            ]
            return f"=== {label} ({ticker}) — 3-Month Price History ===\n" + "\n".join(rows)
        except Exception as exc:
            logger.debug("deal market data: %s failed: %s", ticker, exc)
            return ""

    target_ticker = _infer_ticker(deal)
    if target_ticker:
        table = _price_table(target_ticker, f"Target: {deal.get('company', target_ticker)}")
        if table:
            segments.append(table)

    acquirer_ticker = (deal.get("extra") or {}).get("acquirer_ticker", "")
    if acquirer_ticker:
        table = _price_table(str(acquirer_ticker), f"Acquirer ({acquirer_ticker})")
        if table:
            segments.append(table)

    result = "\n\n".join(segments)
    if result:
        logger.info("deal market data: fetched price data for %s", deal.get("company", ""))
    return result


# ---------------------------------------------------------------------------
# ASX per-company polling — catch scheme booklets and IERs for ongoing deals
# ---------------------------------------------------------------------------

_ASX_COMPANY_ANNOUNCEMENTS_URL = (
    "https://www.asx.com.au/asx/1/company/{ticker}/announcements"
    "?count=20&market_sensitive=true"
)

# Announcement headline keywords that indicate a rich secondary document
_ASX_FOLLOWUP_KEYWORDS = {
    "scheme booklet", "independent expert", "target's statement",
    "bidder's statement", "supplementary booklet", "scheme document",
    "notice of meeting", "proxy",
}


def discover_asx_followup_filings(ticker: str) -> list[RawDeal]:
    """Poll the ASX per-company announcements feed for scheme booklets and IERs.

    The initial deal announcement arrives via discover_asx(). The rich documents
    (scheme booklet, Independent Expert's Report, target/bidder statements) are
    filed as separate ASX announcements weeks later. This function polls the
    company-specific feed for those follow-up documents.

    Call once per active deal per daily run. Rate-limit: 0.5s between tickers.
    Returns RawDeal items with url pointing to the ASX PDF document.
    """
    ticker = ticker.upper().replace(".AX", "")
    url = _ASX_COMPANY_ANNOUNCEMENTS_URL.format(ticker=ticker)
    try:
        data = fetch_json(url)
    except Exception as exc:
        logger.debug("ASX follow-up: fetch failed for %s: %s", ticker, exc)
        return []

    deals: list[RawDeal] = []
    announcements = data if isinstance(data, list) else data.get("data", [])
    for ann in announcements:
        header = (ann.get("header") or "").lower()
        if not any(kw in header for kw in _ASX_FOLLOWUP_KEYWORDS):
            continue
        doc_url = ann.get("url", "")
        if not doc_url:
            continue
        # Construct full PDF URL if relative
        if doc_url.startswith("/"):
            doc_url = f"https://www.asx.com.au{doc_url}"
        file_date = (ann.get("date") or "")[:10]
        deals.append(RawDeal(
            title=ann.get("header", "ASX filing"),
            url=doc_url,
            source="ASX_followup",
            region="AU",
            filing_type="scheme_booklet",
            date=file_date,
            company=ticker,
            extra={"ticker": ticker, "announcement_id": ann.get("id", "")},
        ))

    time.sleep(cfg["edgar"]["rate_limit_seconds"])   # reuse EDGAR rate limit
    logger.info("ASX follow-up: %d scheme/IER docs for %s", len(deals), ticker)
    return deals


# ---------------------------------------------------------------------------
# Combined discovery
# ---------------------------------------------------------------------------

def discover_all(target_date: date) -> list[RawDeal]:
    """Run all three discovery sources and combine results.

    A failure in any single source is logged and returns []; the others
    still run. The combined list is returned unsorted (ranking happens in
    the pipeline's pick step).
    """
    results: list[RawDeal] = []
    for fn, name in [
        (discover_edgar, "EDGAR"),
        (discover_asx, "ASX"),
        (discover_rns, "RNS"),
    ]:
        try:
            found = fn(target_date)
            results.extend(found)
        except Exception as exc:
            # Defensive: the inner functions already catch their own errors,
            # but we guard here too so one bad source never kills the run.
            logger.error("%s discovery raised unexpectedly: %s", name, exc)
    return results
