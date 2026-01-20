"""Tool callbacks for ClinicalTrials.gov guardrails."""

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from dod_deep_research.agents.callbacks.utils import log_agent_event

CLINICAL_TRIALS_TOOL_NAME = "clinicaltrials_search_studies"
MAX_CLINICAL_TRIALS_PAGE_SIZE = 10
DEFAULT_CLINICAL_TRIALS_FIELDS = [
    "NCTId",
    "BriefTitle",
    "OverallStatus",
    "Condition",
    "InterventionName",
    "Phase",
    "EnrollmentCount",
    "StudyType",
]


def before_clinical_trials_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """
    Enforce ClinicalTrials.gov query limits before tool execution.

    Args:
        tool (BaseTool): Tool instance being called.
        args (dict[str, Any]): Tool arguments.
        tool_context (ToolContext): Tool execution context.

    Returns:
        dict[str, Any] | None: Returning a dict skips tool execution.
    """
    if tool.name != CLINICAL_TRIALS_TOOL_NAME:
        return None

    original_args = dict(args)
    page_size = args.get("pageSize")
    if not isinstance(page_size, int) or page_size <= 0 or page_size > 10:
        args["pageSize"] = MAX_CLINICAL_TRIALS_PAGE_SIZE

    fields = args.get("fields")
    if not isinstance(fields, list) or not fields:
        args["fields"] = DEFAULT_CLINICAL_TRIALS_FIELDS

    agent_name = tool_context.agent_name or "unknown"
    log_agent_event(
        agent_name,
        "before_tool_modify",
        {
            "payload": {
                "tool_name": tool.name,
                "original_args": original_args,
                "modified_args": dict(args),
            }
        },
    )
    return None


def after_clinical_trials_tool_callback(
    tool: BaseTool,
    tool_response: dict[str, Any],
    tool_context: ToolContext,
) -> dict[str, Any] | None:
    """
    Filter ClinicalTrials.gov results by previously seen NCT IDs.

    Args:
        tool (BaseTool): Tool instance that ran.
        tool_response (dict[str, Any]): Tool response payload.
        tool_context (ToolContext): Tool execution context.

    Returns:
        dict[str, Any] | None: Returning a dict replaces the tool response.
    """
    if tool.name != CLINICAL_TRIALS_TOOL_NAME:
        return None

    structured = tool_response.get("structuredContent") or {}
    paged = structured.get("pagedStudies") or {}
    studies = paged.get("studies")
    if not isinstance(studies, list):
        return None

    seen_ids = tool_context.state.get("seen_nct_ids") or []
    seen_set = {value for value in seen_ids if isinstance(value, str)}

    filtered: list[dict[str, Any]] = []
    new_ids: list[str] = []
    skipped: list[str] = []
    for study in studies:
        if not isinstance(study, dict):
            continue
        nct_id = (
            study.get("protocolSection", {})
            .get("identificationModule", {})
            .get("nctId")
        )
        if isinstance(nct_id, str) and nct_id in seen_set:
            skipped.append(nct_id)
            continue
        filtered.append(study)
        if isinstance(nct_id, str):
            new_ids.append(nct_id)

    if not skipped and not new_ids:
        return None

    if new_ids:
        tool_context.state["seen_nct_ids"] = sorted(seen_set.union(new_ids))

    structured["pagedStudies"] = {**paged, "studies": filtered}
    tool_response["structuredContent"] = structured
    if skipped:
        tool_response["content"] = []

    agent_name = tool_context.agent_name or "unknown"
    log_agent_event(
        agent_name,
        "after_tool_filter",
        {
            "payload": {
                "tool_name": tool.name,
                "skipped_nct_ids": skipped,
                "new_nct_ids": new_ids,
                "remaining_count": len(filtered),
            }
        },
    )
    return tool_response
