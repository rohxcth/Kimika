"""Kimika pipeline: Discover → Cross-verify → Pick → Research → Write → Verify → Save.

Each stage is its own function. This module is filled out step by step.
Run manually:  python -m app.pipeline --now
"""
import argparse
import logging

logger = logging.getLogger(__name__)


def run(date_str: str | None = None) -> None:
    """Run the full pipeline for the given date (YYYY-MM-DD), or today if None."""
    logger.info("Pipeline run started (date=%s)", date_str or "today")
    # Stages are added in subsequent build steps.


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kimika pipeline")
    parser.add_argument(
        "--now", action="store_true", help="Run immediately for today's date"
    )
    parser.add_argument("--date", help="Run for a specific date (YYYY-MM-DD)")
    args = parser.parse_args()
    run(date_str=args.date)


if __name__ == "__main__":
    main()
