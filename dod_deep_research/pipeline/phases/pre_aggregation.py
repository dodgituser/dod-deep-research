"""Pre-aggregation phase (planner + base collectors)."""

import logging

from google.adk import Agent, runners
from google.adk.agents import SequentialAgent
from google.genai import types

from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.callbacks.aggregate_evidence_after_collectors import (
    aggregate_evidence_after_collectors,
)
from dod_deep_research.agents.planner.agent import planner_agent
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.schemas import get_common_sections
from dod_deep_research.core import persist_state_delta, run_agent

logger = logging.getLogger(__name__)


def get_pre_aggregation_agent(planner: Agent | None = None) -> SequentialAgent:
    """
    Build the pre-aggregation pipeline (planner + collectors).

    Args:
        planner (Agent | None): Planner override if provided.

    Returns:
        SequentialAgent: Configured pre-aggregation agent.
    """
    planner_agent_to_use = planner or planner_agent
    return SequentialAgent(
        name="pre_aggregation_pipeline",
        sub_agents=[
            planner_agent_to_use,
            create_collector_agents(
                [section.value for section in get_common_sections()],
                after_agent_callback=aggregate_evidence_after_collectors,
            ),
        ],
    )


async def run_pre_aggregation(
    app_name: str,
    runner_planner: runners.Runner,
    runner_collectors: runners.Runner,
    user_id: str,
    session_id: str,
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
        runner_planner (runners.Runner): Planner runner.
        runner_collectors (runners.Runner): Collectors runner.
        user_id (str): User ID.
        session_id (str): Session ID.
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

    session = await runner_planner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
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
        runner_planner,
        session.user_id,
        session.id,
        types.Content(
            parts=[types.Part.from_text(text="Plan the research.")],
            role="user",
        ),
    )

    updated_session = await runner_planner.session_service.get_session(
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
                runner_planner.session_service,
                updated_session,
                section_state,
            )
            state = updated_session.state
        except Exception as exc:
            logger.warning("Failed to persist research section state: %s", exc)

    collectors_session = await runner_collectors.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
        state=state.copy(),
    )
    collector_responses = await run_agent(
        runner_collectors,
        collectors_session.user_id,
        collectors_session.id,
        types.Content(
            parts=[types.Part.from_text(text="Collect evidence for sections.")],
            role="user",
        ),
    )
    json_responses.extend(collector_responses)

    updated_session = await runner_collectors.session_service.get_session(
        app_name=app_name,
        user_id=collectors_session.user_id,
        session_id=collectors_session.id,
    )
    logger.info("Pre-aggregation phase completed")
    return updated_session, json_responses
