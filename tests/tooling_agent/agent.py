"""Tooling agent for MCP tool smoke checks."""

from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import (
    StreamableHTTPConnectionParams,
)
from dod_deep_research.models import GeminiModels
from dod_deep_research.agents.collector.agent import get_collector_tools

PUBMED_MCP_URL = "http://127.0.0.1:3017/mcp"


def _pubmed_tools():
    """
    Configure PubMed MCP toolset for local smoke checks.

    Returns:
        list: PubMed MCP toolset.
    """
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=PUBMED_MCP_URL,
                headers={"Accept": "application/json, text/event-stream"},
                terminate_on_close=False,
            ),
            tool_filter=["pubmed_search_articles", "pubmed_fetch_contents"],
        )
    ]


root_agent = Agent(
    name="tooling_agent",
    tools=get_collector_tools(),
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    instruction=(
        "You are a tooling agent. Verify PubMed MCP tools by calling them with "
        "simple queries and summarize the results."
    ),
)
