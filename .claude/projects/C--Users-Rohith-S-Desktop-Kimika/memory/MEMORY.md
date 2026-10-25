# Kimika — Claude Code memory

## Project state
- **Last completed step:** Step 6 (pipeline + report + llm stub + prompts, 227 passing)
- **Next step:** Step 7 — llm.py: real Gemini client, model routing, quota tracking, 429 back-off (big step — show plan, need GEMINI_API_KEY in .env)

## Key facts
- Python 3.14 (C:\Program Files\Python314\python.exe); use `python -m pytest -q`
- Installed packages: pytest, pyyaml, fastapi, python-dotenv (pip, global)
- `.env.example` cannot be written by Claude — settings.json `Write(./.env.*)` deny rule catches it. Rohith must create it manually (or loosen the rule). The file content is in `.env.example` note below.
- `.gitignore`, `CLAUDE.md`, `kimika-spec.md`, `docs/` all pre-existed; do not overwrite them.
- `config.yaml` lives at repo root; loaded via `app/config.py` → `cfg` singleton.

## .env.example content (for Rohith to create manually)
```
GEMINI_API_KEY=your_gemini_api_key_here
FMP_API_KEY=your_fmp_api_key_here
FRED_API_KEY=your_fred_api_key_here
SEC_USER_AGENT=Kimika/1.0 your@email.com
```

## Conventions confirmed
- Finance calculations: `app/finance.py` only, never the LLM
- All network: `app/fetch.py` with blocklist from `config.yaml`
- Tests: synthetic data only, no network, no real keys
- Currency: A$, US$, £ explicit; percentages 1 dp; bps for spreads/rate moves
