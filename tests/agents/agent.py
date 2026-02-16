"""Test agents for functional testing, can plug and play for different agents to run adk web ui locally."""

import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from google.genai import types


_STATE_PATH = Path(__file__).with_name("collector_state.json")
_GEMINI_FLASH_LATEST = "gemini-flash-latest"
logger = logging.getLogger(__name__)

_MCP_ENV_CONFIG: list[tuple[str, int]] = [
    ("PUBMED_MCP_URL", 180),
    ("CLINICAL_TRIALS_MCP_URL", 180),
    ("EXA_MCP_URL", 60),
    ("NEO4J_MCP_URL", 60),
    ("OLS_MCP_URL", 60),
]


class CachedMcpToolset(McpToolset):
    """Caches MCP tool discovery to reduce repeated list_tools calls."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cached_tools = None
        self._tools_lock = asyncio.Lock()

    async def get_tools(self, readonly_context=None):  # type: ignore[override]
        if self._cached_tools is not None:
            return self._cached_tools

        async with self._tools_lock:
            if self._cached_tools is None:
                self._cached_tools = await super().get_tools(readonly_context)

        return self._cached_tools


def _audience_from_url(url: str) -> str:
    """
    Builds an OIDC audience from an MCP endpoint URL.

    Args:
        url (str): Full MCP endpoint URL.

    Returns:
        str: URL origin used as audience claim.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_cloud_run_url(url: str) -> bool:
    """
    Checks if the URL points to a Cloud Run endpoint.

    Args:
        url (str): MCP endpoint URL.

    Returns:
        bool: True when host is a run.app domain.
    """
    parsed = urlparse(url)
    return bool(parsed.hostname and parsed.hostname.endswith(".run.app"))


def _fetch_identity_token(audience: str) -> str:
    """
    Fetches an ID token for the provided audience.

    Args:
        audience (str): Token audience claim.

    Returns:
        str: Bearer token value.
    """
    request = google_auth_requests.Request()
    return google_id_token.fetch_id_token(request, audience)


def _build_mcp_headers(url: str) -> dict[str, str]:
    """
    Builds request headers for MCP streamable HTTP connections.

    Args:
        url (str): MCP endpoint URL.

    Returns:
        dict[str, str]: Headers including auth when required.
    """
    headers = {"Accept": "application/json, text/event-stream"}
    if _is_cloud_run_url(url):
        audience = _audience_from_url(url)
        token = _fetch_identity_token(audience)
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_http_options() -> types.HttpOptions:
    """
    Build shared HTTP options for model retries.

    Returns:
        types.HttpOptions: HTTP options with retry configuration.
    """
    return types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            initial_delay=10,
            attempts=5,
        ),
    )


def _before_agent_callback(callback_context: CallbackContext) -> None:
    state = json.loads(_STATE_PATH.read_text())
    if hasattr(callback_context, "state"):
        callback_context.state.update(state)
        return None
    if hasattr(callback_context, "session") and hasattr(
        callback_context.session, "state"
    ):
        callback_context.session.state.update(state)
    return None


def _get_resolved_mcp_endpoints() -> list[tuple[str, int]]:
    """
    Resolve MCP endpoints from required environment variables.

    Returns:
        list[tuple[str, int]]: Resolved endpoint URLs and timeouts.

    Raises:
        ValueError: If a required MCP URL env var is missing or not HTTPS.
    """
    endpoints: list[tuple[str, int]] = []
    for env_var, timeout in _MCP_ENV_CONFIG:
        url = os.getenv(env_var, "").strip()
        if not url:
            raise ValueError(f"{env_var} is required")
        if not url.startswith("https://"):
            raise ValueError(f"{env_var} must be an https URL, got: {url}")
        endpoints.append((url, timeout))
        logger.info("%s=%s", env_var, url)
    return endpoints


def _get_mcp_tools() -> list[CachedMcpToolset]:
    """Get all MCP toolsets with full tool access."""
    tools: list[CachedMcpToolset] = []
    for url, timeout in _get_resolved_mcp_endpoints():
        tools.append(
            CachedMcpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=url,
                    timeout=timeout,
                    sse_read_timeout=timeout,
                    headers=_build_mcp_headers(url),
                    terminate_on_close=False,
                ),
            )
        )
    return tools


root_agent = Agent(
    name="test_tool_agent",
    instruction="You are a test agent with access to all configured MCP tools. Use these tools to answer user queries.",
    tools=_get_mcp_tools(),
    model=_GEMINI_FLASH_LATEST,
    generate_content_config=types.GenerateContentConfig(
        http_options=_get_http_options(),
    ),
)


collector_agent = Agent(
    name="test_collector_agent",
    instruction="Answer user queries using all configured MCP tools.",
    tools=_get_mcp_tools(),
    model=_GEMINI_FLASH_LATEST,
    generate_content_config=types.GenerateContentConfig(
        http_options=_get_http_options(),
    ),
    before_agent_callback=_before_agent_callback,
)
