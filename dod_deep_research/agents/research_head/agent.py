"""Research Head agent for gap analysis and targeted retrieval."""

import logging
from typing import Optional

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from dod_deep_research.agents.research_head.prompt import RESEARCH_HEAD_AGENT_PROMPT
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.agents.shared_state import (
    aggregate_evidence,
    extract_section_stores,
)
from dod_deep_research.models import GeminiModels

logger = logging.getLogger(__name__)

research_head_agent = Agent(
    name="research_head_agent",
    instruction=RESEARCH_HEAD_AGENT_PROMPT,
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    output_key="research_head_plan",
    output_schema=ResearchHeadPlan,
)


def aggregate_evidence_after_collectors(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    Deterministically aggregate evidence after targeted collectors complete.

    This callback runs after the targeted collectors agent finishes. It:
    1. Reads all evidence_store_section_* keys from state
    2. Aggregates them using the aggregate_evidence function
    3. Updates the evidence_store state key

    Args:
        callback_context: Callback context with agent info and state.

    Returns:
        None to keep the agent's original output unchanged.
    """
    agent_name = callback_context.agent_name
    state = callback_context.state.to_dict()

    logger.info(f"[Callback] Aggregating evidence after agent: {agent_name}")

    # Extract all evidence_store_section_* keys
    section_stores = extract_section_stores(state)

    if not section_stores:
        logger.info("[Callback] No section stores found to aggregate")
        return None

    # Aggregate evidence deterministically
    logger.info(f"[Callback] Aggregating evidence from {len(section_stores)} sections")
    evidence_store = aggregate_evidence(section_stores)

    # Update state with aggregated evidence
    callback_context.state["evidence_store"] = evidence_store.model_dump()

    logger.info(
        f"[Callback] Evidence aggregation complete: {len(evidence_store.items)} unique items"
    )
    return None
