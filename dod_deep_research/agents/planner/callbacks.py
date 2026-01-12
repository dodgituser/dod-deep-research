"""Planner-specific callbacks."""

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from dod_deep_research.agents.callbacks.after_agent import (
    after_agent_callback as base_after_agent_callback,
)
from dod_deep_research.agents.planner.schemas import ResearchPlan


def planner_after_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """
    Log planner state and store per-section state for collectors.

    Args:
        callback_context (CallbackContext): Callback context with agent and session data.

    Returns:
        types.Content | None: Returning content replaces the agent's output.
    """
    base_after_agent_callback(callback_context)

    state = callback_context.state
    if not isinstance(state, dict):
        return None

    research_plan = state.get("research_plan")
    if not research_plan:
        return None

    plan = ResearchPlan(**research_plan)
    for section in plan.sections:
        state[f"research_section_{section.name}"] = section.model_dump()

    return None
