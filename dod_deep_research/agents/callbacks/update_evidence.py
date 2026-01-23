"""Callback for aggregating evidence after collectors run."""

import logging

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.utils.evidence import (
    EvidenceStore,
    aggregate_evidence,
    build_question_coverage,
    extract_section_stores,
)

logger = logging.getLogger(__name__)


def update_evidence(
    callback_context: CallbackContext,
) -> types.Content | None:
    """
    Aggregate evidence and update evidence store after collectors complete.

    Args:
        callback_context (CallbackContext): Callback context with agent info and state.

    Returns:
        types.Content | None: None to keep the agent's original output unchanged.
    """
    agent_name = callback_context.agent_name
    state = callback_context.state.to_dict()

    section_stores = extract_section_stores(state)
    if not section_stores:
        logger.info("[Callback] No section stores found to aggregate")
        return None

    existing_store = None
    existing_store_raw = state.get("evidence_store")
    if isinstance(existing_store_raw, dict):
        existing_store = EvidenceStore(**existing_store_raw)

    evidence_store = aggregate_evidence(section_stores, existing_store=existing_store)
    callback_context.state["evidence_store"] = evidence_store.model_dump()

    research_plan = callback_context.state.get("research_plan")
    if research_plan:
        plan = ResearchPlan(**research_plan)
        store = EvidenceStore(**callback_context.state.get("evidence_store"))
        question_coverage = build_question_coverage(plan, store)
        callback_context.state["question_coverage"] = question_coverage

    logger.info(
        "[Callback] Evidence aggregation complete: %s unique items for agent '%s'",
        len(evidence_store.items),
        agent_name,
    )
    return None
