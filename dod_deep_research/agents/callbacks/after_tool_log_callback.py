"""After-tool callback that logs tool results."""

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from dod_deep_research.agents.callbacks.utils import log_agent_event


def after_tool_log_callback(
    tool: BaseTool,
    tool_response: dict[str, Any],
    tool_context: ToolContext,
    args: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Logs tool results after execution.

    Args:
        tool (BaseTool): Tool instance that ran.
        tool_response (dict[str, Any]): Tool response payload.
        tool_context (ToolContext): Tool execution context.
        args (dict[str, Any] | None): Tool arguments if provided.

    Returns:
        dict[str, Any] | None: Returning a dict replaces the tool response.
    """
    agent_name = tool_context.agent_name or "unknown"
    payload = {
        "payload": {
            "tool_name": tool.name,
            "tool_args": args,
            "tool_response": tool_response,
        }
    }
    log_agent_event(agent_name, "after_tool", payload)
    return None
