"""Pre-aggregation phase (planner + base collectors)."""

import logging

from google.adk import runners
from google.genai import types

from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.callbacks.update_evidence import update_evidence
from dod_deep_research.core import (
    persist_section_plan_to_state,
    persist_state_delta,
    run_agent,
    get_validated_model,
    retry_missing_outputs,
)

logger = logging.getLogger(__name__)


async def run_plan_draft(
    app_name: str,
    plan_runner: runners.Runner,
    draft_runner: runners.Runner,
    user_id: str,
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
    common_sections: list[str] | None = None,
    **kwargs,
) -> runners.Session:
    """
    Run the pre-aggregation phase (planner + collectors).

    Args:
        app_name (str): App name for session creation.
        plan_runner (runners.Runner): Planner runner.
        draft_runner (runners.Runner): Draft collectors runner.
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
        runners.Session: Updated session.
    """
    logger.info("Starting pre-aggregation phase (planner + collectors)")

    session = await plan_runner.session_service.create_session(
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

    await run_agent(
        plan_runner,
        session.user_id,
        session.id,
        types.Content(
            parts=[types.Part.from_text(text="Plan the research.")],
            role="user",
        ),
        output_keys="research_plan_raw",
    )

    updated_session = await plan_runner.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )
    research_plan = get_validated_model(
        updated_session.state, ResearchPlan, "research_plan_raw"
    )
    updated_session = await persist_state_delta(
        plan_runner.session_service,
        updated_session,
        {"research_plan": research_plan.model_dump()},
    )

    updated_session = await persist_section_plan_to_state(
        plan_runner.session_service,
        updated_session,
    )  # Persist the research plan into sections into the session state base on planner output (this could be a callback)
    state = updated_session.state

    collectors_session = await draft_runner.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        state=state,
    )  # Run the draft collectors based on the updated state from the planner
    all_output_keys = [
        f"evidence_store_section_{section}" for section in (common_sections or [])
    ]

    def build_collectors_for_missing(missing_keys: list[str]) -> object:
        remaining_sections = [
            key.removeprefix("evidence_store_section_") for key in missing_keys
        ]
        return create_collector_agents(
            remaining_sections,
            after_agent_callback=update_evidence,
        )

    await run_agent(
        draft_runner,
        collectors_session.user_id,
        collectors_session.id,
        types.Content(
            parts=[types.Part.from_text(text="Collect evidence for sections.")],
            role="user",
        ),
        output_keys=all_output_keys,
        max_retries=0,
        log_attempts=False,
    )

    updated_session = await draft_runner.session_service.get_session(
        app_name=app_name,
        user_id=collectors_session.user_id,
        session_id=collectors_session.id,
    )  # Get the final updated session after draft collectors execution
    updated_session = await retry_missing_outputs(
        app_name=app_name,
        user_id=collectors_session.user_id,
        session=updated_session,
        output_keys=all_output_keys,
        build_agent=build_collectors_for_missing,
        run_message="Collect evidence for any remaining sections.",
        log_label="draft collectors",
        agent_prefix="collector_",
    )
    logger.info("Pre-aggregation phase completed")
    return updated_session
