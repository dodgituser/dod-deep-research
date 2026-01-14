"""Iterative gap-driven research loop phase."""

import logging

from google.adk import runners
from google.genai import types

from dod_deep_research.agents.collector.agent import create_targeted_collector_agents
from dod_deep_research.utils.evidence import aggregate_evidence_after_collectors
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.core import build_runner, persist_state_delta, run_agent

logger = logging.getLogger(__name__)


async def run_iterative_research_loop(
    app_name: str,
    runner_loop: runners.Runner,
    session: runners.Session,
    max_iterations: int = 5,
) -> tuple[runners.Session, list[dict]]:
    """
    Run the gap-driven research loop.

    Args:
        app_name (str): App name for sessions.
        runner_loop (runners.Runner): Research head runner.
        session (runners.Session): Session from pre-aggregation.
        max_iterations (int): Max loop iterations.

    Returns:
        tuple[runners.Session, list[dict]]: Updated loop session and JSON responses.
    """
    logger.info("Starting gap-driven loop phase")

    session_loop = await runner_loop.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
        state=session.state.copy(),
    )

    json_responses: list[dict] = []
    loop_iteration = 0

    while loop_iteration < max_iterations:
        loop_iteration += 1
        logger.info("Gap-driven loop iteration %s", loop_iteration)

        loop_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )
        loop_responses = await run_agent(
            runner_loop, session_loop.user_id, session_loop.id, loop_message
        )
        json_responses.extend(loop_responses)

        updated_loop_session = await runner_loop.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )
        session_loop = await persist_state_delta(
            runner_loop.session_service,
            session_loop,
            updated_loop_session.state,
        )

        research_head_plan_dict = session_loop.state.get("research_head_plan")
        if not research_head_plan_dict:
            logger.info("No research_head_plan found after analysis")
            continue

        try:
            research_head_plan = ResearchHeadPlan(**research_head_plan_dict)
        except Exception as exc:
            logger.warning("Failed to parse research_head_plan: %s", exc)
            continue

        if not research_head_plan.gaps:
            logger.info("ResearchHead determined gaps are resolved")
            break

        logger.info(
            "Running targeted collectors for %s gaps", len(research_head_plan.gaps)
        )
        targeted_collectors = create_targeted_collector_agents(
            research_head_plan.gaps,
            after_agent_callback=aggregate_evidence_after_collectors,
        )
        runner_targeted = build_runner(agent=targeted_collectors, app_name=app_name)
        targeted_session = await runner_targeted.session_service.create_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=f"{session_loop.id}_targeted_{loop_iteration}",
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
        updated_targeted_session = await runner_targeted.session_service.get_session(
            app_name=app_name,
            user_id=targeted_session.user_id,
            session_id=targeted_session.id,
        )
        session_loop = await persist_state_delta(
            runner_loop.session_service,
            session_loop,
            updated_targeted_session.state,
        )

    if loop_iteration >= max_iterations:
        logger.info("Max iterations reached, running final gap analysis")
        loop_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )
        loop_responses = await run_agent(
            runner_loop, session_loop.user_id, session_loop.id, loop_message
        )
        json_responses.extend(loop_responses)
        session_loop = await runner_loop.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )

    logger.info("Gap-driven loop phase completed")
    return session_loop, json_responses
