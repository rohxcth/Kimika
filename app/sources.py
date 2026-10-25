"""Kimika M&A deal discovery — SEC EDGAR, ASX, UK RNS.

Each discover_* function returns a list of RawDeal dicts for the given date.
A RawDeal is the minimal metadata needed to decide whether to research further:
  {
    "title":        str,   # announcement headline
    "url":          str,   # primary document URL
    "source":       str,   # "EDGAR" | "ASX" | "RNS"
    "region":       str,   # "US" | "AU" | "UK"
    "filing_type":  str,   # e.g. "8-K", "ASX_announcement", "RNS_Rule27"
    "date":         str,   # ISO date string YYYY-MM-DD
    "company":      str,   # primary entity name (filer or target)
    "extra":        dict,  # source-specific metadata (CIK, ticker, etc.)
  }

One failed source never stops the run: errors are logged and [] is returned.
All HTTP goes through app.fetch.fetch().
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import TypedDict

from app.config import cfg
from app.fetch import fetch, fetch_json

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
    """Build the EDGAR filing viewer URL from the hit metadata."""
    # hit_id is typically "cik/accession-number"
    cik = src.get("cik", "")
    if cik and hit_id:
        accession = hit_id.replace("-", "").replace("/", "")
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K"
    return "https://www.sec.gov/cgi-bin/browse-edgar"


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
_FED_PRESS_RELEASES_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
_RBA_DECISIONS_URL = "https://www.rba.gov.au/monetary-policy/int-rate-decisions/"
_FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series/observations"

# Key FRED series: Fed funds rate, CPI (all items), unemployment, 10y Treasury
_FRED_SERIES = {
    "FEDFUNDS": "Federal Funds Effective Rate",
    "CPIAUCSL": "US CPI (All Urban Consumers, SA)",
    "UNRATE": "US Unemployment Rate",
    "GS10": "US 10-Year Treasury Constant Maturity Rate",
}


def discover_economy_context(target_date: date) -> str:
    """Fetch macro context for the Economy & Markets report.

    Returns a trimmed string combining:
      - Federal Reserve FOMC calendar / press release page (public HTML)
      - RBA interest rate decisions page (public HTML)
      - FRED data for key US series (requires FRED_API_KEY in env; skipped if absent)

    A failure on any individual source is logged and skipped; the others still run.
    The combined text is trimmed to doc_trim_chars (from config.yaml) before return.
    """
    import os
    trim = cfg["pipeline"]["doc_trim_chars"]
    segments: list[str] = []

    # 1. Federal Reserve FOMC page
    try:
        html = fetch(_FED_PRESS_RELEASES_URL)
        segments.append(f"=== Federal Reserve FOMC Calendar ===\n{html[:3000]}")
        logger.info("Economy context: fetched Fed page (%d chars)", len(html))
    except Exception as exc:
        logger.warning("Economy context: Fed fetch failed: %s", exc)

    # 2. RBA interest rate decisions
    try:
        html = fetch(_RBA_DECISIONS_URL)
        segments.append(f"=== RBA Interest Rate Decisions ===\n{html[:3000]}")
        logger.info("Economy context: fetched RBA page (%d chars)", len(html))
    except Exception as exc:
        logger.warning("Economy context: RBA fetch failed: %s", exc)

    # 3. FRED data (optional - needs API key)
    fred_key = os.environ.get("FRED_API_KEY", "")
    if fred_key:
        fred_snippets: list[str] = []
        for series_id, label in _FRED_SERIES.items():
            try:
                data = fetch_json(
                    f"{_FRED_SERIES_URL}?series_id={series_id}"
                    f"&api_key={fred_key}&sort_order=desc&limit=3&file_type=json"
                )
                obs = data.get("observations", [])
                if obs:
                    # Most recent 3 observations
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
