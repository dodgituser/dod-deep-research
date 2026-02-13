"""Shared MCP toolset factories used by collector and root agents."""

import asyncio
import os
from urllib.parse import urlparse

from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams


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


def create_pubmed_toolset() -> CachedMcpToolset:
    """Creates the PubMed MCP toolset."""
    url = os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp")
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            timeout=180,
            sse_read_timeout=180,
            headers=_build_mcp_headers(url),
            terminate_on_close=False,
        ),
        tool_filter=["pubmed_search_articles", "pubmed_fetch_contents"],
    )


def create_clinical_trials_toolset() -> CachedMcpToolset:
    """Creates the ClinicalTrials.gov MCP toolset."""
    url = os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp")
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            timeout=180,
            sse_read_timeout=180,
            headers=_build_mcp_headers(url),
            terminate_on_close=False,
        ),
        tool_filter=["clinicaltrials_search_studies", "clinicaltrials_get_study"],
    )


def create_exa_toolset() -> CachedMcpToolset:
    """Creates the Exa MCP toolset."""
    url = os.getenv("EXA_MCP_URL", "http://127.0.0.1:3019/mcp")
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            timeout=10,
            sse_read_timeout=10,
            headers=_build_mcp_headers(url),
            terminate_on_close=False,
        ),
        tool_filter=["web_search_exa", "crawling_exa", "company_research_exa"],
    )


def create_neo4j_toolset() -> CachedMcpToolset:
    """Creates the Neo4j MCP toolset."""
    url = os.getenv("NEO4J_MCP_URL", "http://127.0.0.1:8000/api/mcp/")
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            timeout=60,
            sse_read_timeout=60,
            headers=_build_mcp_headers(url),
            terminate_on_close=False,
        ),
        tool_filter=["get_neo4j_schema"],
    )
