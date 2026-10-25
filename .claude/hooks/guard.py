#!/usr/bin/env python3
"""PreToolUse guard for Kimika.

Blocks (exit code 2, reason sent back to Claude):
  1. Reading, editing, writing or committing .env files (API keys).
  2. Fetching paywalled / blocked news domains (AFR, Bloomberg, WSJ, FT, ...).

.env.example is allowed: it only holds placeholders.
"""
import json
import re
import sys
from urllib.parse import urlparse

BLOCKED_DOMAINS = [
    "afr.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "theaustralian.com.au",
    "thetimes.co.uk",
    "barrons.com",
    "economist.com",
    "mergermarket.com",
    "pitchbook.com",
    "capitaliq.com",
    "spglobal.com/marketintelligence",
    "refinitiv.com",
]

# Matches .env or .env.local etc. as a path component, but not .env.example
ENV_FILE = re.compile(r"(?:^|[\s/\"'=<>|;&(])\.env(?:\.(?!example\b)[\w-]+)?(?=$|[\s\"'|;&)<>])")


def block(reason: str) -> None:
    print(f"Blocked by Kimika guard: {reason}", file=sys.stderr)
    sys.exit(2)


def is_env_path(path: str) -> bool:
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def blocked_domain(text: str):
    lowered = text.lower()
    for domain in BLOCKED_DOMAINS:
        host = domain.split("/")[0]
        # match the domain itself or any subdomain (www.afr.com, markets.ft.com)
        if re.search(rf"(?:^|[/.\s\"'@]){re.escape(host)}(?:$|[/:\s\"'?#])", lowered):
            if "/" in domain and domain not in lowered:
                continue
            return domain
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # never break Claude Code on unexpected input

    tool = data.get("tool_name", "")
    args = data.get("tool_input", {}) or {}

    # 1. Secrets: file tools
    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = args.get("file_path") or args.get("notebook_path") or ""
        if is_env_path(path):
            block(".env holds API keys. Rohith manages it himself; use .env.example for placeholders.")

    # 1. Secrets + 2. blocked domains: shell commands
    if tool == "Bash":
        cmd = args.get("command", "")
        if ENV_FILE.search(cmd):
            block("shell command touches .env (API keys). Load keys in code via python-dotenv instead.")
        domain = blocked_domain(cmd)
        if domain:
            block(f"{domain} is a paywalled/blocked source. Kimika uses public sources only (see docs/sources.md).")

    # 2. Blocked domains: web tools
    if tool in ("WebFetch", "WebSearch"):
        target = args.get("url", "") or args.get("query", "")
        if tool == "WebFetch":
            host = (urlparse(target).hostname or "").lower()
            target = host + urlparse(target).path.lower()
        domain = blocked_domain(" " + target)
        if domain and tool == "WebFetch":
            block(f"{domain} is a paywalled/blocked source. Kimika uses public sources only (see docs/sources.md).")

    sys.exit(0)


if __name__ == "__main__":
    main()
