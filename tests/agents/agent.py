"""Test agents for functional testing, can plug and play for different agents to run adk web ui locally."""

import json
from pathlib import Path

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext

from dod_deep_research.agents.collector.agent import create_collector_agent
from dod_deep_research.agents.mcp_toolsets import create_ols_toolset
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


def _get_ols_tools():
    """Get OLS MCP tools with full tool access."""
    return [create_ols_toolset()]


root_agent = Agent(
    name="test_tool_agent",
    instruction="You are a test agent with access to OLS MCP tools. Use these tools to answer user queries.",
    tools=_get_ols_tools(),
    model=GeminiModels.GEMINI_FLASH_LATEST.value.replace("models/", ""),
    generate_content_config=types.GenerateContentConfig(
        http_options=get_http_options(),
    ),
)


collector_agent = create_collector_agent(
    "market_opportunity_analysis",
    before_agent_callback=_before_agent_callback,
)
