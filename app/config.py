"""Load and expose the YAML config and environment variables.

Usage:
    from app.config import cfg, require_env

    model = cfg["gemini"]["flash_model"]
    api_key = require_env("GEMINI_API_KEY")
"""
import os
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Module-level singleton — import this everywhere.
cfg: dict = load_config()


def require_env(name: str) -> str:
    """Return env var value, or raise clearly if missing.

    Keys live in .env (loaded by python-dotenv at app startup, never here).
    This function only reads; it never prints or logs the value.
    """
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and fill it in."
        )
    return value
