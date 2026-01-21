"""After-tool callback that tracks successful tool payloads per section."""

import json
from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext


_TRACKED_TOOLS = {
    "web_search_exa",
    "pubmed_search_articles",
    "clinicaltrials_search_studies",
}


def _has_results(tool_response: Any) -> bool:
    if isinstance(tool_response, list):
        return len(tool_response) > 0
    if not isinstance(tool_response, dict):
        return False
    if tool_response.get("isError"):
        return False
    for value in tool_response.values():
        if isinstance(value, list) and value:
            return True
    return False


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def after_tool_payloads_callback(
    tool: BaseTool,
    tool_args: dict[str, Any] | None,
    tool_context: ToolContext,
    tool_response: Any,
) -> None:
    """
    Store successful tool payloads into session state by section.

    Args:
        tool (BaseTool): Tool instance that ran.
        tool_args (dict[str, Any] | None): Arguments passed to the tool.
        tool_context (ToolContext): Tool execution context.
        tool_response (Any): Tool response payload.
    """
    if tool.name not in _TRACKED_TOOLS or not tool_args:
        return
    if not _has_results(tool_response):
        return

    agent_name = tool_context.agent_name or ""
    if agent_name.startswith("collector_"):
        section_name = agent_name.replace("collector_", "", 1)
    elif agent_name.startswith("targeted_collector_"):
        section_name = agent_name.replace("targeted_collector_", "", 1)
    else:
        return

    state_key = f"tool_payloads_{section_name}"
    payloads_by_tool = tool_context.state.get(state_key) or {}
    if not isinstance(payloads_by_tool, dict):
        payloads_by_tool = {}

    existing_payloads = payloads_by_tool.get(tool.name) or []
    if not isinstance(existing_payloads, list):
        existing_payloads = []

    canonical = _canonical_payload(tool_args)
    existing_canonicals = {
        _canonical_payload(item) for item in existing_payloads if isinstance(item, dict)
    }
    if canonical in existing_canonicals:
        return

    existing_payloads.append(tool_args)
    payloads_by_tool[tool.name] = existing_payloads
    tool_context.state[state_key] = payloads_by_tool
