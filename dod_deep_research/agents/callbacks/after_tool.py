"""After-tool callback that logs tool results."""

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from dod_deep_research.agents.callbacks.utils import format_payload, log_agent_event


def after_tool_callback(
    tool: BaseTool, tool_response: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """
    Logs tool results after execution.

    Args:
        tool (BaseTool): Tool instance that ran.
        tool_response (dict[str, Any]): Tool response payload.
        tool_context (ToolContext): Tool execution context.

    Returns:
        dict[str, Any] | None: Returning a dict replaces the tool response.
    """
    agent_name = tool_context.agent_name or "unknown"
    session_id = getattr(tool_context, "session_id", None) or "unknown"
    payload = {
        "type": "after_tool",
        "agent_name": agent_name,
        "payload": {
            "tool_name": tool.name,
            "tool_context": tool_context,
            "tool_response": tool_response,
        },
    }
    log_agent_event(session_id, agent_name, format_payload(payload))
    return None
