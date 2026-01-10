"""Logging configuration for the application."""

import logging


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Setup basic logging and return the module logger."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress verbose logs from Google GenAI and httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(
        logging.WARNING
    )
