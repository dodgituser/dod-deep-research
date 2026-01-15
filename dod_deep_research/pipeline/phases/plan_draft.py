"""Pre-aggregation phase (planner + base collectors)."""

import logging

from google.adk import Agent, runners
from google.adk.agents import SequentialAgent
from google.genai import types

from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.callbacks.update_evidence_and_gaps import (
    update_evidence_and_gaps,
)
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.schemas import get_common_sections
from dod_deep_research.core import persist_state_delta, run_agent

logger = logging.getLogger(__name__)


def get_plan_draft_agents(planner: Agent) -> SequentialAgent:
    """
    Build the pre-aggregation pipeline (planner + collectors).

    Args:
        planner (Agent): Planner agent to use.

    Returns:
        SequentialAgent: Configured pre-aggregation agent.
    """
    return SequentialAgent(
        name="plan_draft_pipeline",
        sub_agents=[
            planner,
            create_collector_agents(
                [section.value for section in get_common_sections()],
                after_agent_callback=update_evidence_and_gaps,
            ),
        ],
    )


async def run_pre_aggregation(
    app_name: str,
    plan_draft_runner: runners.Runner,
    user_id: str,
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
    common_sections: list[str] | None = None,
    **kwargs,
) -> tuple[runners.Session, list[dict]]:
    """
    Run the pre-aggregation phase (planner + collectors).

    Args:
        app_name (str): App name for session creation.
        plan_draft_runner (runners.Runner): Pre-aggregation runner.
        user_id (str): User ID.
        indication (str): Indication name.
        drug_name (str): Drug name.
        drug_form (str | None): Drug form if provided.
        drug_generic_name (str | None): Drug generic name if provided.
        indication_aliases (list[str] | None): Indication aliases.
        drug_aliases (list[str] | None): Drug aliases.
        common_sections (list[str] | None): Common section names.
        **kwargs: Extra state keys.

    Returns:
        tuple[runners.Session, list[dict]]: Updated session and JSON responses.
    """
    logger.info("Starting pre-aggregation phase (planner + collectors)")

    session = await plan_draft_runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        state={
            "indication": indication,
            "drug_name": drug_name,
            "drug_form": drug_form,
            "drug_generic_name": drug_generic_name,
            "indication_aliases": indication_aliases,
            "drug_aliases": drug_aliases,
            "common_sections": common_sections or [],
            **kwargs,
        },
    )

    json_responses = await run_agent(
        plan_draft_runner,
        session.user_id,
        session.id,
        types.Content(
            parts=[types.Part.from_text(text="Plan the research.")],
            role="user",
        ),
    )

    updated_session = await plan_draft_runner.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )
    state = updated_session.state

    research_plan = state.get("research_plan")
    if research_plan:
        try:
            plan = ResearchPlan(**research_plan)
            section_state = {
                f"research_section_{section.name}": section.model_dump()
                for section in plan.sections
            }
            updated_session = await persist_state_delta(
                plan_draft_runner.session_service,
                updated_session,
                section_state,
            )
            state = updated_session.state
        except Exception as exc:
            logger.warning("Failed to persist research section state: %s", exc)

    collectors_session = await plan_draft_runner.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        state=state.copy(),
    )
    collector_responses = await run_agent(
        plan_draft_runner,
        collectors_session.user_id,
        collectors_session.id,
        types.Content(
            parts=[types.Part.from_text(text="Collect evidence for sections.")],
            role="user",
        ),
    )
    json_responses.extend(collector_responses)

    updated_session = await plan_draft_runner.session_service.get_session(
        app_name=app_name,
        user_id=collectors_session.user_id,
        session_id=collectors_session.id,
    )
    research_plan = updated_session.state.get("research_plan")
    logger.info("Pre-aggregation phase completed")
    return updated_session, json_responses
