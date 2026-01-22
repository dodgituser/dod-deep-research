"""Logging configuration for the application."""

import logging
import warnings


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Setup basic logging and return the module logger."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress specific warnings
    warnings.filterwarnings(
        "ignore",
        message="Your application has authenticated using end user credentials",
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=".*EXPERIMENTAL.*",
        category=UserWarning,
    )
    # Suppress noisy client logs
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    logging.getLogger("mcp.client").setLevel(logging.WARNING)
    logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)
    logging.getLogger("google_adk").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("google_adk.tools.mcp_tool").setLevel(logging.WARNING)
    logging.getLogger("google_adk.tools.mcp_tool.mcp_session_manager").setLevel(
        logging.WARNING
    )
    logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(
        logging.WARNING
    )
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    logging.getLogger("anyio").setLevel(logging.CRITICAL)
