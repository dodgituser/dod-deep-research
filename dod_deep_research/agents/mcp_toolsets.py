"""Shared MCP toolset factories used by collector and root agents."""

import asyncio
import os

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


def create_pubmed_toolset() -> CachedMcpToolset:
    """Creates the PubMed MCP toolset."""
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp"),
            timeout=180,
            sse_read_timeout=180,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["pubmed_search_articles", "pubmed_fetch_contents"],
    )


def create_clinical_trials_toolset() -> CachedMcpToolset:
    """Creates the ClinicalTrials.gov MCP toolset."""
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp"),
            timeout=180,
            sse_read_timeout=180,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["clinicaltrials_search_studies", "clinicaltrials_get_study"],
    )


def create_exa_toolset() -> CachedMcpToolset:
    """Creates the Exa MCP toolset."""
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("EXA_MCP_URL", "http://127.0.0.1:3019/mcp"),
            timeout=10,
            sse_read_timeout=10,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["web_search_exa", "crawling_exa", "company_research_exa"],
    )


def create_neo4j_toolset() -> CachedMcpToolset:
    """Creates the Neo4j MCP toolset."""
    return CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("NEO4J_MCP_URL", "http://127.0.0.1:8000/api/mcp/"),
            timeout=60,
            sse_read_timeout=60,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["get_neo4j_schema"],
    )
