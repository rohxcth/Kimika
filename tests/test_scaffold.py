"""Step 1 scaffold tests.

Checks:
- config.yaml loads and has all required top-level keys
- Gemini model names are strings (not None / empty)
- Daily caps are positive integers
- Blocklist contains the required paywalled domains
- No secrets appear in any source file (no literal API key patterns)
- require_env raises clearly when a variable is missing
"""
import os
import re
from pathlib import Path

import pytest
import yaml


CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
APP_DIR = Path(__file__).parent.parent / "app"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cfg():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_config_loads(cfg):
    assert isinstance(cfg, dict), "config.yaml must parse to a dict"


def test_required_top_level_keys(cfg):
    required = ["schedule", "gemini", "crosscheck", "pipeline", "blocklist", "reports"]
    for key in required:
        assert key in cfg, f"config.yaml missing top-level key: {key}"


def test_gemini_model_names_are_strings(cfg):
    assert isinstance(cfg["gemini"]["flash_model"], str) and cfg["gemini"]["flash_model"]
    assert isinstance(cfg["gemini"]["flash_lite_model"], str) and cfg["gemini"]["flash_lite_model"]


def test_gemini_daily_caps_positive(cfg):
    assert cfg["gemini"]["flash_daily_cap"] > 0
    assert cfg["gemini"]["flash_lite_daily_cap"] > 0


def test_blocklist_contains_required_domains(cfg):
    blocklist = cfg["blocklist"]
    required_blocked = ["afr.com", "bloomberg.com", "wsj.com", "ft.com"]
    for domain in required_blocked:
        assert any(domain in entry for entry in blocklist), (
            f"blocklist must include {domain}"
        )


def test_schedule_keys(cfg):
    sched = cfg["schedule"]
    assert "run_hour" in sched and "run_minute" in sched and "timezone" in sched


# ---------------------------------------------------------------------------
# No secrets in source files
# ---------------------------------------------------------------------------

# Real API keys look like long hex/base58 strings or start with known prefixes.
# We match anything that looks like a live key assignment.
_KEY_PATTERN = re.compile(
    r'(GEMINI_API_KEY|FMP_API_KEY|FRED_API_KEY)\s*=\s*[A-Za-z0-9_\-]{20,}',
    re.IGNORECASE,
)


def test_no_secrets_in_source_files():
    """No Python source file should contain a real-looking API key value."""
    source_files = list(APP_DIR.rglob("*.py"))
    offending = []
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _KEY_PATTERN.search(text):
            offending.append(str(path))
    assert not offending, f"Possible secrets found in: {offending}"


def test_no_secrets_in_config():
    """config.yaml must not contain literal API key values."""
    text = CONFIG_PATH.read_text(encoding="utf-8")
    assert not _KEY_PATTERN.search(text), "config.yaml contains a literal API key value"


# ---------------------------------------------------------------------------
# require_env
# ---------------------------------------------------------------------------

def test_require_env_raises_when_missing(monkeypatch):
    """require_env must raise EnvironmentError for an unset variable."""
    monkeypatch.delenv("KIMIKA_NONEXISTENT_VAR", raising=False)
    from app.config import require_env
    with pytest.raises(EnvironmentError, match="KIMIKA_NONEXISTENT_VAR"):
        require_env("KIMIKA_NONEXISTENT_VAR")


def test_require_env_returns_value(monkeypatch):
    monkeypatch.setenv("KIMIKA_TEST_VAR", "hello")
    from app.config import require_env
    assert require_env("KIMIKA_TEST_VAR") == "hello"


# ---------------------------------------------------------------------------
# App imports
# ---------------------------------------------------------------------------

def test_app_package_importable():
    import app  # noqa: F401


def test_pipeline_importable():
    from app import pipeline  # noqa: F401


def test_main_importable():
    # main.py tries to load dotenv; that's fine if it's absent
    from app import main  # noqa: F401
