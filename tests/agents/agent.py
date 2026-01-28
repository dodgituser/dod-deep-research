"""Test agents for functional testing, can plug and play for different agents to run adk web ui locally."""

import json
import os
from pathlib import Path

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from dod_deep_research.agents.collector.agent import (
    CachedMcpToolset,
    create_collector_agent,
)
from dod_deep_research.core import get_http_options
from dod_deep_research.models import GeminiModels
from google.genai import types


_STATE_PATH = Path(__file__).with_name("collector_state.json")


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


def _get_neo4j_tools():
    """Get Neo4j Cypher MCP tools."""
    neo4j_toolset = CachedMcpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("NEO4J_MCP_URL", "http://neo4j-cypher-mcp:8000/api/mcp/"),
            timeout=180,
            sse_read_timeout=180,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
    )
    return [neo4j_toolset]


root_agent = Agent(
    name="test_tool_agent",
    instruction="You are a test agent with access to Neo4j Cypher MCP tools. Use these tools to query the knowledge graph.",
    tools=_get_neo4j_tools(),
    model=GeminiModels.GEMINI_FLASH_LATEST.value.replace("models/", ""),
    generate_content_config=types.GenerateContentConfig(
        http_options=get_http_options(),
    ),
)


collector_agent = create_collector_agent(
    "market_opportunity_analysis",
    before_agent_callback=_before_agent_callback,
)
