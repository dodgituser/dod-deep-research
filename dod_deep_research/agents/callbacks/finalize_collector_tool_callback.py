"""After-tool callback that stores finalized collector output in state."""

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext


def after_finalize_collector_tool_callback(
    tool: BaseTool,
    tool_response: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """
    Persist finalized collector responses into the session state.

    Args:
        tool (BaseTool): Tool instance that ran.
        tool_response (dict[str, Any]): Tool response payload.
        tool_context (ToolContext): Tool execution context.

    Returns:
        dict[str, Any] | None: Returning a dict replaces the tool response.
    """
    if tool.name != "finalize_collector_response":
        return None

    agent_name = tool_context.agent_name or ""
    if agent_name.startswith("collector_"):
        section_name = agent_name.replace("collector_", "", 1)
    elif agent_name.startswith("targeted_collector_"):
        section_name = agent_name.replace("targeted_collector_", "", 1)
    else:
        return None

    if isinstance(tool_response, dict) and {
        "section",
        "evidence",
    }.issubset(tool_response):
        tool_context.state[f"evidence_store_section_{section_name}"] = tool_response
    return None
