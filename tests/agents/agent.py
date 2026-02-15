"""Test agents for functional testing, can plug and play for different agents to run adk web ui locally."""

import json
import os
from pathlib import Path

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types


_STATE_PATH = Path(__file__).with_name("collector_state.json")
_GEMINI_FLASH_LATEST = "gemini-flash-latest"


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


def _get_ols_tools():
    """Get all MCP toolsets with full tool access."""
    headers = {"Accept": "application/json, text/event-stream"}
    endpoints = [
        (os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp"), 180),
        (os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp"), 180),
        (os.getenv("EXA_MCP_URL", "http://127.0.0.1:3019/mcp"), 60),
        (os.getenv("NEO4J_MCP_URL", "http://127.0.0.1:8000/api/mcp/"), 60),
        (os.getenv("OLS_MCP_URL", "https://www.ebi.ac.uk/ols4/api/mcp"), 60),
    ]
    tools: list[McpToolset] = []
    for url, timeout in endpoints:
        tools.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=url,
                    timeout=timeout,
                    sse_read_timeout=timeout,
                    headers=headers,
                    terminate_on_close=False,
                ),
            )
        )
    return tools


root_agent = Agent(
    name="test_tool_agent",
    instruction="You are a test agent with access to all configured MCP tools. Use these tools to answer user queries.",
    tools=_get_ols_tools(),
    model=_GEMINI_FLASH_LATEST,
    generate_content_config=types.GenerateContentConfig(
        http_options=_get_http_options(),
    ),
)


collector_agent = Agent(
    name="test_collector_agent",
    instruction="Answer user queries using all configured MCP tools.",
    tools=_get_ols_tools(),
    model=_GEMINI_FLASH_LATEST,
    generate_content_config=types.GenerateContentConfig(
        http_options=_get_http_options(),
    ),
    before_agent_callback=_before_agent_callback,
)
