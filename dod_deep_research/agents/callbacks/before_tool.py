"""Before-tool callback that logs tool name and args."""

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from dod_deep_research.agents.callbacks.utils import format_payload, log_agent_event


def before_tool_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """
    Logs tool invocation details before execution.

    Args:
        tool (BaseTool): Tool instance being called.
        args (dict[str, Any]): Tool arguments.
        tool_context (ToolContext): Tool execution context.

    Returns:
        dict[str, Any] | None: Returning a dict skips tool execution.
    """
    agent_name = tool_context.agent_name or "unknown"
    payload = {
        "type": "before_tool",
        "agent_name": agent_name,
        "payload": {
            "tool_name": tool.name,
            "tool_context": tool_context,
            "tool_args": args,
        },
    }
    log_agent_event(agent_name, "before_tool", format_payload(payload))
    return None
