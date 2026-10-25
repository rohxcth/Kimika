"""Kimika HTTP fetcher — the single entry point for all network access.

Every URL in the pipeline must go through `fetch()`. It:
  1. Checks the URL against the blocklist in config.yaml and refuses blocked domains.
  2. Caches responses on disk by SHA-256 of the URL, respecting the TTL in config.yaml.
  3. Sets a polite User-Agent (falls back to a default if SEC_USER_AGENT is unset).
  4. Logs every outbound request so we can audit what Kimika fetches.

Never import requests or urllib directly elsewhere in the app — use fetch() instead.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.config import cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Blocklist (loaded once from config at import time)
# ---------------------------------------------------------------------------

_BLOCKLIST: list[str] = [d.lower() for d in cfg.get("blocklist", [])]

# Cache directory alongside the reports folder
_CACHE_DIR = Path(cfg["reports"]["output_dir"]).parent / "cache" / "fetch"
_CACHE_TTL_SECONDS = cfg["pipeline"]["cache_ttl_hours"] * 3600

# Default User-Agent; SEC EDGAR requires a real contact address via env var.
_DEFAULT_UA = "Kimika/1.0 (research tool; contact: kimika@example.com)"


class BlockedDomainError(ValueError):
    """Raised when a URL matches a blocklisted domain."""


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def fetch(
    url: str,
    *,
    timeout: int = 30,
    use_cache: bool = True,
    headers: dict | None = None,
) -> str:
    """Fetch `url` and return the response body as a string.

    Raises:
        BlockedDomainError: if the URL's domain is on the blocklist.
        requests.HTTPError:  on a non-2xx response.
        requests.Timeout:    if the request exceeds `timeout` seconds.

    Cached responses are stored in `cache/fetch/` and reused within the TTL
    defined in config.yaml. Pass `use_cache=False` to always hit the network.
    """
    _check_blocklist(url)

    if use_cache:
        cached = _cache_get(url)
        if cached is not None:
            logger.debug("cache hit: %s", url)
            return cached

    logger.info("fetch: %s", url)
    ua = os.environ.get("SEC_USER_AGENT", _DEFAULT_UA)
    req_headers = {"User-Agent": ua}
    if headers:
        req_headers.update(headers)

    resp = requests.get(url, headers=req_headers, timeout=timeout)
    resp.raise_for_status()
    body = resp.text

    if use_cache:
        _cache_set(url, body)

    return body


def fetch_json(
    url: str,
    *,
    timeout: int = 30,
    use_cache: bool = True,
    headers: dict | None = None,
) -> dict | list:
    """Fetch `url` and parse the response as JSON."""
    body = fetch(url, timeout=timeout, use_cache=use_cache, headers=headers)
    return json.loads(body)


# ---------------------------------------------------------------------------
# Blocklist enforcement
# ---------------------------------------------------------------------------

def _check_blocklist(url: str) -> None:
    """Raise BlockedDomainError if `url` matches any blocklisted domain.

    Matches the hostname and any subdomain:
      afr.com blocks www.afr.com, markets.afr.com, etc.
    """
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    host = host.lower()

    for blocked in _BLOCKLIST:
        # Match exact domain or any subdomain (host ends with .blocked or == blocked)
        if host == blocked or host.endswith("." + blocked):
            raise BlockedDomainError(
                f"Blocked domain '{blocked}' in URL: {url}\n"
                "Kimika uses public sources only (see docs/sources.md)."
            )


def is_blocked(url: str) -> bool:
    """Return True if the URL's domain is on the blocklist (no exception)."""
    try:
        _check_blocklist(url)
        return False
    except BlockedDomainError:
        return True


# ---------------------------------------------------------------------------
# Disk cache (keyed by SHA-256 of URL)
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> Path:
    key = hashlib.sha256(url.encode()).hexdigest()
    return _CACHE_DIR / key[:2] / (key + ".json")


def _cache_get(url: str) -> str | None:
    """Return cached body if it exists and is within TTL, else None."""
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - data["fetched_at"]
        if age > _CACHE_TTL_SECONDS:
            logger.debug("cache expired (%.0fs old): %s", age, url)
            return None
        return data["body"]
    except Exception as exc:
        logger.warning("cache read error for %s: %s", url, exc)
        return None


def _cache_set(url: str, body: str) -> None:
    """Write body to the cache."""
    path = _cache_path(url)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"url": url, "fetched_at": time.time(), "body": body}),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("cache write error for %s: %s", url, exc)


def clear_cache() -> int:
    """Delete all cached fetch responses. Returns the number of files removed."""
    if not _CACHE_DIR.exists():
        return 0
    removed = 0
    for p in _CACHE_DIR.rglob("*.json"):
        p.unlink()
        removed += 1
    return removed
