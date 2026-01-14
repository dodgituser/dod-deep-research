"""Callback for aggregating evidence after collector agents run."""

import logging

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from dod_deep_research.utils.evidence import aggregate_evidence, extract_section_stores

logger = logging.getLogger(__name__)


def aggregate_evidence_after_collectors(
    callback_context: CallbackContext,
) -> types.Content | None:
    """
    Deterministically aggregate evidence after targeted collectors complete.

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

    evidence_store = aggregate_evidence(section_stores)
    callback_context.state["evidence_store"] = evidence_store.model_dump()

    logger.info(
        f"[Callback] Evidence aggregation complete: {len(evidence_store.items)} unique items for agent '{agent_name}'"
    )
    return None
