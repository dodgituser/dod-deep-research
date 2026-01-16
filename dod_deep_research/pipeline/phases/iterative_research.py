"""Iterative gap-driven research loop phase."""

import logging

from google.adk import runners
from google.genai import types

from dod_deep_research.agents.collector.agent import create_targeted_collector_agents
from dod_deep_research.agents.callbacks.update_evidence import update_evidence
from dod_deep_research.core import (
    build_runner,
    get_research_head_guidance,
    run_agent,
    persist_state_delta,
)
from dod_deep_research.utils.evidence import build_gap_tasks
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.utils.evidence import (
    EvidenceStore,
    build_question_coverage,
)

logger = logging.getLogger(__name__)


async def run_iterative_research(
    app_name: str,
    research_head_runner: runners.Runner,
    session: runners.Session,
    max_iterations: int = 5,
) -> runners.Session:
    """
    Run the gap-driven research loop.

    Args:
        app_name (str): App name for sessions.
        research_head_runner (runners.Runner): Research head runner.
        session (runners.Session): Session from pre-aggregation.
        max_iterations (int): Max loop iterations.

    Returns:
        runners.Session: Updated loop session.
    """
    logger.info("Starting gap-driven loop phase")

    research_head_session = await research_head_runner.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        state=session.state.copy(),
    )  # create new session for loop phase while maintaining state from previous phase this will be the same session throughout the loop

    for research_iteration in range(1, max_iterations + 1):
        logger.info("Gap-driven loop iteration %s", research_iteration)

        continue_research_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )  # Base message to prompt research head to execeute
        await run_agent(
            research_head_runner,
            research_head_session.user_id,
            research_head_session.id,
            continue_research_message,
        )

        research_head_session = await research_head_runner.session_service.get_session(
            app_name=app_name,
            user_id=research_head_session.user_id,
            session_id=research_head_session.id,
        )  # update session after research head runs to get latest state

        # Rebuild question coverage to ensure quantitative gaps are detected correctly
        plan_data = research_head_session.state.get("research_plan")
        store_data = research_head_session.state.get("evidence_store")

        if plan_data and store_data:
            question_coverage = build_question_coverage(
                ResearchPlan(**plan_data), EvidenceStore(**store_data)
            )
            logger.info(
                "Analyzing evidence coverage for %d sections", len(question_coverage)
            )

        guidance_map = get_research_head_guidance(
            research_head_session.state
        )  # section -> notes + suggested queries

        gap_tasks = build_gap_tasks(
            question_coverage, min_evidence=1, guidance_map=guidance_map
        )  # each question must have at least min_evidence piece of evidence AND meet the section min seen in SECTION_MIN_EVIDENCE (not currently enforced deterministically, only enforced through prompt)
        if not gap_tasks:
            logger.info("No gap tasks remain; ending gap-driven loop")
            break
        else:
            logger.info("Identified %d gap tasks to address", len(gap_tasks))

        targeted_collectors = create_targeted_collector_agents(
            gap_tasks,
            guidance_map=guidance_map,
            after_agent_callback=update_evidence,
        )  # create dynamic targeted collector agents based on remaining gap tasks and guidance from research head
        targeted_runner = build_runner(agent=targeted_collectors, app_name=app_name)
        targeted_session = await targeted_runner.session_service.create_session(
            app_name=app_name,
            user_id=research_head_session.user_id,
            state=research_head_session.state.copy(),
        )  # create a new session each loop for the targeted collectors while maintaining state from research head
        await run_agent(
            targeted_runner,
            targeted_session.user_id,
            targeted_session.id,
            types.Content(
                parts=[types.Part.from_text(text="Collect evidence for tasks.")],
                role="user",
            ),
        )  # run the targeted collectors to collect evidence for gap tasks

        targeted_session = await targeted_runner.session_service.get_session(
            app_name=app_name,
            user_id=targeted_session.user_id,
            session_id=targeted_session.id,
        )  # get updated state from targeted collectors

        # Propagate new evidence back to research head session
        state_delta = {}
        if "evidence_store" in targeted_session.state:
            state_delta["evidence_store"] = targeted_session.state["evidence_store"]

        if state_delta:
            research_head_session = await persist_state_delta(
                research_head_runner.session_service,
                research_head_session,
                state_delta,
            )  # reuse the same research head session but with updated evidence store
        else:
            research_head_session = (
                await research_head_runner.session_service.get_session(
                    app_name=app_name,
                    user_id=research_head_session.user_id,
                    session_id=research_head_session.id,
                )
            )

    if research_iteration >= max_iterations:
        logger.info(
            "Max iterations reached and research head was not satisfied, running final gap analysis"
        )
        continue_research_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )
        await run_agent(
            research_head_runner,
            research_head_session.user_id,
            research_head_session.id,
            continue_research_message,
        )
        research_head_session = await research_head_runner.session_service.get_session(
            app_name=app_name,
            user_id=research_head_session.user_id,
            session_id=research_head_session.id,
        )

    logger.info("Gap-driven loop phase completed")
    return research_head_session
