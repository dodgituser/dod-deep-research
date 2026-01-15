"""Iterative gap-driven research loop phase."""

import logging

from google.adk import runners
from google.genai import types

from dod_deep_research.agents.collector.agent import create_targeted_collector_agents
from dod_deep_research.agents.callbacks.update_evidence_and_gaps import (
    update_evidence_and_gaps,
)
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.core import build_runner, get_research_head_guidance, run_agent
from dod_deep_research.utils.evidence import GapTask

logger = logging.getLogger(__name__)


async def run_iterative_loop(
    app_name: str,
    runner_research_head: runners.Runner,
    session: runners.Session,
    max_iterations: int = 5,
) -> tuple[runners.Session, list[dict]]:
    """
    Run the gap-driven research loop.

    Args:
        app_name (str): App name for sessions.
        runner_research_head (runners.Runner): Research head runner.
        session (runners.Session): Session from pre-aggregation.
        max_iterations (int): Max loop iterations.

    Returns:
        tuple[runners.Session, list[dict]]: Updated loop session and JSON responses.
    """
    logger.info("Starting gap-driven loop phase")

    session_loop = await runner_research_head.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        state=session.state.copy(),
    )

    json_responses: list[dict] = []
    for loop_iteration in range(1, max_iterations + 1):
        logger.info("Gap-driven loop iteration %s", loop_iteration)

        loop_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )
        loop_responses = await run_agent(
            runner_research_head, session_loop.user_id, session_loop.id, loop_message
        )
        json_responses.extend(loop_responses)

        session_loop = await runner_research_head.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )  # update session after agent runs to get latest state

        gap_tasks_raw = (
            session_loop.state.get("gap_tasks") or []
        )  # get gap tasks from research head output in state
        gap_tasks: list[GapTask] = []
        for task in gap_tasks_raw:
            gap_tasks.append(GapTask(**task))
        if not gap_tasks:
            logger.info("No gap tasks remain; ending gap-driven loop")
            break

        guidance_map = {}
        research_head_plan_dict = session_loop.state.get("research_head_plan")
        if research_head_plan_dict:
            ResearchHeadPlan(**research_head_plan_dict)
            guidance_map = get_research_head_guidance(session_loop.state)

        targeted_collectors = create_targeted_collector_agents(
            gap_tasks,
            guidance_map=guidance_map,
            after_agent_callback=update_evidence_and_gaps,
        )
        runner_targeted = build_runner(agent=targeted_collectors, app_name=app_name)
        targeted_session = await runner_targeted.session_service.create_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            state=session_loop.state.copy(),
        )
        await run_agent(
            runner_targeted,
            targeted_session.user_id,
            targeted_session.id,
            types.Content(
                parts=[types.Part.from_text(text="Collect evidence for tasks.")],
                role="user",
            ),
        )
        session_loop = await runner_research_head.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )

    if loop_iteration >= max_iterations:
        logger.info(
            "Max iterations reached and research head was not satisfied, running final gap analysis"
        )
        loop_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )
        loop_responses = await run_agent(
            runner_research_head, session_loop.user_id, session_loop.id, loop_message
        )
        json_responses.extend(loop_responses)
        session_loop = await runner_research_head.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )

    logger.info("Gap-driven loop phase completed")
    return session_loop, json_responses
