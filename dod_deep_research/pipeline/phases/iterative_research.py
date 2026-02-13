"""Iterative gap-driven research loop phase."""

import logging

from google.adk import runners
from google.genai import types

from dod_deep_research.agents.collector.agent import create_targeted_collector_agents
from dod_deep_research.agents.callbacks.update_evidence import update_evidence
from dod_deep_research.core import (
    build_runner,
    get_research_head_guidance,
    retry_missing_outputs,
    run_agent,
    persist_state_delta,
)
from dod_deep_research.utils.evidence import build_gap_tasks, get_min_evidence
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.research_head.schemas import GapTask
from dod_deep_research.agents.schemas import CommonSection
from dod_deep_research.utils.evidence import (
    EvidenceStore,
    build_question_coverage,
)

logger = logging.getLogger(__name__)


async def run_iterative_research(
    app_name: str,
    research_head_parallel_runner: runners.Runner,
    research_head_qual_runner: runners.Runner,
    session: runners.Session,
    max_iterations: int = 3,
) -> runners.Session:
    """
    Run the gap-driven research loop.

    Args:
        app_name (str): App name for sessions.
        research_head_parallel_runner (runners.Runner): Parallel research head runner.
        research_head_qual_runner (runners.Runner): Qualitative research head runner.
        session (runners.Session): Session from pre-aggregation.
        max_iterations (int): Max loop iterations.

    Returns:
        runners.Session: Updated loop session.
    """
    logger.info("Starting gap-driven loop phase")

    research_head_session = await research_head_parallel_runner.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        state=session.state.copy(),
    )  # create new session for loop phase while maintaining state from previous phase this will be the same session throughout the loop
    # TODO: deep research may 1 shot

    for research_iteration in range(1, max_iterations + 1):
        logger.info("Gap-driven loop iteration %s", research_iteration)

        # Rebuild question coverage to ensure quantitative gaps are detected correctly
        plan_data = research_head_session.state.get("research_plan")
        store_data = research_head_session.state.get("evidence_store")

        if not plan_data or not store_data:
            logger.warning(
                "Missing research_plan or evidence_store; ending gap-driven loop"
            )
            break

        question_coverage = build_question_coverage(
            ResearchPlan(**plan_data), EvidenceStore(**store_data)
        )  # Section -> question -> list of evidence IDs that support the question.
        logger.info(
            "Analyzing evidence coverage for %d sections", len(question_coverage)
        )

        gap_tasks = build_gap_tasks(
            question_coverage, min_evidence=2
        )  # build the gap tasks based on the question coverage and minimum evidence required. gap tasks are deterministic.

        research_head_session = await persist_state_delta(
            research_head_parallel_runner.session_service,
            research_head_session,
            {
                "gap_tasks": [task.model_dump() for task in gap_tasks],
                "question_coverage": question_coverage,
            },
        )  # update state with new gap tasks and question coverage (from drafters or targeted collectors)

        continue_research_message = types.Content(
            parts=[types.Part.from_text(text="Provide guidance for the gap tasks.")],
            role="user",
        )  # prompt the research head to provide guidance for the gap tasks
        if gap_tasks:  # if quantitative gap tasks are identified, run both research heads to provide guidance
            await run_agent(
                research_head_parallel_runner,
                research_head_session.user_id,
                research_head_session.id,
                continue_research_message,
                output_keys=["research_head_quant_plan", "research_head_qual_plan"],
            )
            research_head_session = (
                await research_head_parallel_runner.session_service.get_session(
                    app_name=app_name,
                    user_id=research_head_session.user_id,
                    session_id=research_head_session.id,
                )
            )
        else:  # if no quantitative gap tasks are identified, run the qualitative research head to propose qualitative gaps
            await run_agent(
                research_head_qual_runner,
                research_head_session.user_id,
                research_head_session.id,
                continue_research_message,
                output_keys="research_head_qual_plan",
            )
            research_head_session = (
                await research_head_qual_runner.session_service.get_session(
                    app_name=app_name,
                    user_id=research_head_session.user_id,
                    session_id=research_head_session.id,
                )
            )

        guidance_map = get_research_head_guidance(research_head_session.state)
        if not guidance_map:
            logger.info("No guidance returned; ending gap-driven loop")
            break

        guided_tasks: list[GapTask] = []
        for section, guidance in guidance_map.items():
            guided_tasks.append(
                GapTask(
                    section=CommonSection(section),
                    missing_questions=list(guidance["missing_questions"]),
                    min_evidence=get_min_evidence(section),
                )
            )  # construct the gap tasks based on the guidance from the research head

        logger.info(
            "Running targeted collectors for %d guidance sections",
            len(guided_tasks),
        )
        guidance_keys = set(guidance_map.keys())  # Section -> guidance payload.
        all_output_keys = [
            f"evidence_store_section_{task.section}" for task in guided_tasks
        ]
        gap_tasks_by_section = {str(task.section): task for task in guided_tasks}

        targeted_collectors = create_targeted_collector_agents(
            guided_tasks,
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
                parts=[
                    types.Part.from_text(
                        text="Collect evidence for gap tasks that were identified."
                    )
                ],
                role="user",
            ),
            output_keys=all_output_keys,
            max_retries=0,
            log_attempts=False,
        )  # run the targeted collectors to collect evidence for gap tasks

        targeted_session = await targeted_runner.session_service.get_session(
            app_name=app_name,
            user_id=targeted_session.user_id,
            session_id=targeted_session.id,
        )  # get updated state from targeted collectors

        # this builds the targeted collectors for the sections that were not successful above
        def build_targeted_collectors_for_missing(missing_keys: list[str]) -> object:
            missing_sections = {
                key.removeprefix("evidence_store_section_") for key in missing_keys
            }
            missing_tasks = [
                gap_tasks_by_section[section]
                for section in missing_sections
                if section in gap_tasks_by_section
            ]
            guidance_subset = {
                section: guidance_map[section]
                for section in missing_sections
                if section in guidance_keys
            }
            return create_targeted_collector_agents(
                missing_tasks,
                guidance_map=guidance_subset,
                after_agent_callback=update_evidence,
            )

        targeted_session = await retry_missing_outputs(
            app_name=app_name,
            user_id=research_head_session.user_id,
            session=targeted_session,
            output_keys=all_output_keys,
            build_agent=build_targeted_collectors_for_missing,
            run_message="Collect evidence for gap tasks that were identified.",
            log_label="targeted collectors",
            agent_prefix="targeted_collector_",
        )  # retry the targeted collectors for the sections that were not successful above

        # Propagate new evidence back to research head session
        state_delta = {}
        if "evidence_store" in targeted_session.state:
            state_delta["evidence_store"] = targeted_session.state["evidence_store"]
        if "question_coverage" in targeted_session.state:
            state_delta["question_coverage"] = targeted_session.state[
                "question_coverage"
            ]

        # Propagate tool payloads to avoid redundant searches in next iteration
        for key, value in targeted_session.state.items():
            if key.startswith("tool_payloads_"):
                state_delta[key] = value

        if state_delta:
            research_head_session = await persist_state_delta(
                research_head_parallel_runner.session_service,
                research_head_session,
                state_delta,
            )  # reuse the same research head session but with updated evidence store
        else:
            research_head_session = (
                await research_head_parallel_runner.session_service.get_session(
                    app_name=app_name,
                    user_id=research_head_session.user_id,
                    session_id=research_head_session.id,
                )
            )

    logger.info("Gap-driven loop phase completed")
    return research_head_session
