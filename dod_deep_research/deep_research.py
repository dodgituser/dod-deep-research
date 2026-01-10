"""Deep research pipeline entry point."""

import asyncio
import json
import uuid

import typer
from google.genai import types

from google.adk import runners
from google.adk.events import Event, EventActions

from dod_deep_research.core import build_runner, run_agent, get_output_file

from dod_deep_research.agents.aggregator.schemas import EvidenceStore
from dod_deep_research.agents.collector.agent import create_targeted_collectors_agent
from dod_deep_research.agents.research_head.agent import (
    aggregate_evidence_after_collectors,
    research_head_agent,
)
from dod_deep_research.agents.planner.schemas import get_common_sections
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.agents.sequence_agents import (
    post_aggregation_agent,
    pre_aggregation_agent,
)
from dod_deep_research.agents.shared_state import (
    DeepResearchOutput,
    SharedState,
    aggregate_evidence,
    extract_section_stores,
)
from dod_deep_research.agents.writer.schemas import WriterOutput
from dod_deep_research.prompts.indication_prompt import generate_indication_prompt
from dod_deep_research.loggy import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)
app = typer.Typer()


async def run_pre_aggregation(
    app_name: str,
    runner_pre: runners.Runner,
    user_id: str,
    session_id: str,
    indication: str,
    drug_name: str,
    drug_form: str | None,
    drug_generic_name: str | None,
    **kwargs,
) -> tuple[runners.Session, list[dict]]:
    """Run the pre-aggregation phase (planner + collectors)."""
    prompt_text = generate_indication_prompt(
        disease=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
    )
    logger.debug(f"Generated prompt: {prompt_text}")

    new_message = types.Content(
        parts=[types.Part.from_text(text=prompt_text)],
        role="user",
    )

    logger.info("Starting pre-aggregation phase (planner + collectors)")
    common_sections = [section.value for section in get_common_sections()]
    session = await runner_pre.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state={
            "indication": indication,
            "drug_name": drug_name,
            "common_sections": common_sections,
            **kwargs,
        },
    )
    logger.info(f"Created session: {session.id}")

    json_responses = await run_agent(
        runner_pre, session.user_id, session.id, new_message
    )

    logger.info("Pre-aggregation phase completed")

    updated_session = await runner_pre.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )

    logger.info("Running deterministic evidence aggregation")
    state = updated_session.state
    logger.info(f"Session state keys: {list(state.keys())}")

    section_stores = extract_section_stores(state)
    logger.info(f"Aggregating evidence from {len(section_stores)} sections")
    evidence_store = aggregate_evidence(section_stores)
    logger.info(
        f"Aggregation complete: {len(evidence_store.items)} unique evidence items"
    )

    evidence_event = Event(
        actions=EventActions(
            state_delta={"evidence_store": evidence_store.model_dump()}
        )
    )
    await runner_pre.session_service.append_event(updated_session, evidence_event)

    # Refresh session to get the latest state
    updated_session = await runner_pre.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )

    logger.info(f"Updated session {updated_session.id} state with aggregated evidence")

    return updated_session, json_responses


async def run_iterative_research_loop(
    app_name: str,
    runner_loop: runners.Runner,
    session: runners.Session,
) -> tuple[runners.Session, list[dict]]:
    """Run the gap-driven research loop."""
    logger.info("Starting gap-driven loop phase")

    session_loop = await runner_loop.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
        state=session.state.copy(),
    )
    logger.info(f"Created session in gap-driven loop runner: {session_loop.id}")

    json_responses = []
    loop_iteration = 0
    max_iterations = 5

    while loop_iteration < max_iterations:
        loop_iteration += 1
        logger.info(f"Gap-driven loop iteration {loop_iteration}")

        research_head_plan_dict = session_loop.state.get("research_head_plan")
        if research_head_plan_dict:
            try:
                research_head_plan = ResearchHeadPlan(**research_head_plan_dict)
                if research_head_plan.tasks and research_head_plan.continue_research:
                    logger.info(
                        f"Running {len(research_head_plan.tasks)} targeted collectors"
                    )
                    targeted_collectors = create_targeted_collectors_agent(
                        research_head_plan.tasks,
                        after_agent_callback=aggregate_evidence_after_collectors,
                    )
                    runner_targeted = build_runner(
                        agent=targeted_collectors, app_name=app_name
                    )

                    targeted_session = (
                        await runner_targeted.session_service.create_session(
                            app_name=app_name,
                            user_id=session_loop.user_id,
                            session_id=f"{session_loop.id}_targeted_{loop_iteration}",
                            state=session_loop.state.copy(),
                        )
                    )

                    await run_agent(
                        runner_targeted,
                        targeted_session.user_id,
                        targeted_session.id,
                        types.Content(
                            parts=[
                                types.Part.from_text(text="Collect evidence for tasks.")
                            ],
                            role="user",
                        ),
                    )

                    updated_targeted_session = (
                        await runner_targeted.session_service.get_session(
                            app_name=app_name,
                            user_id=targeted_session.user_id,
                            session_id=targeted_session.id,
                        )
                    )

                    merge_event = Event(
                        actions=EventActions(state_delta=updated_targeted_session.state)
                    )
                    await runner_loop.session_service.append_event(
                        session_loop, merge_event
                    )

                    # Refresh session_loop
                    session_loop = await runner_loop.session_service.get_session(
                        app_name=app_name,
                        user_id=session_loop.user_id,
                        session_id=session_loop.id,
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to process research_head_plan or run collectors: {e}"
                )

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
        session_loop.state = updated_loop_session.state

        research_head_plan_dict = session_loop.state.get("research_head_plan")
        if research_head_plan_dict:
            research_head_plan = ResearchHeadPlan(**research_head_plan_dict)
            if not research_head_plan.continue_research:
                logger.info("ResearchHead determined gaps are resolved, exiting loop")
                break

    logger.info("Gap-driven loop phase completed")
    return session_loop, json_responses


async def run_post_aggregation(
    app_name: str,
    runner_post: runners.Runner,
    user_id: str,
    session_loop: runners.Session,
) -> tuple[runners.Session, list[dict]]:
    """Run the post-aggregation phase (writer)."""
    logger.info("Starting post-aggregation phase (writer)")

    session_post = await runner_post.session_service.create_session(
        app_name=app_name,
        user_id=session_loop.user_id,
        session_id=session_loop.id,
        state=session_loop.state.copy(),
    )
    logger.info(f"Created session in post-aggregation runner: {session_post.id}")

    continuation_message = types.Content(
        parts=[types.Part.from_text(text="Continue with writing.")],
        role="user",
    )

    json_responses = await run_agent(
        runner_post, session_post.user_id, session_post.id, continuation_message
    )

    final_session = await runner_post.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_post.id,
    )
    # Fallback to session_post if get_session returns None (though unlikely with InMemoryRunner)
    final_session = final_session or session_post

    return final_session, json_responses


async def run_pipeline_async(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    **kwargs,
) -> SharedState:
    """
    Run the sequential agent pipeline asynchronously and return populated shared state.

    Args:
        indication: The disease indication to research.
        drug_name: The drug name (e.g., "IL-2", "Aspirin").
        drug_form: The specific form of the drug (e.g., "low-dose IL-2").
        drug_generic_name: The generic name of the drug (e.g., "Aldesleukin").
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    logger.info(
        f"Initializing pipeline: indication={indication}, drug_name={drug_name}, "
        f"drug_form={drug_form}, drug_generic_name={drug_generic_name}"
    )

    app_name = "deep_research"
    user_id = "user"
    session_id = str(uuid.uuid4())
    runner_pre = build_runner(agent=pre_aggregation_agent, app_name=app_name)
    runner_loop = build_runner(agent=research_head_agent, app_name=app_name)
    runner_post = build_runner(agent=post_aggregation_agent, app_name=app_name)

    events_file = get_output_file(indication)
    logger.info(f"Events will be saved to: {events_file}")

    # Phase 1: Pre-aggregation
    session, pre_responses = await run_pre_aggregation(
        app_name=app_name,
        runner_pre=runner_pre,
        user_id=user_id,
        session_id=session_id,
        indication=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
        **kwargs,
    )

    # Phase 2: Iterative Research Loop
    session_loop, loop_responses = await run_iterative_research_loop(
        app_name=app_name,
        runner_loop=runner_loop,
        session=session,
    )

    # Phase 3: Post-aggregation
    final_session, post_responses = await run_post_aggregation(
        app_name=app_name,
        runner_post=runner_post,
        user_id=user_id,
        session_loop=session_loop,
    )

    logger.info("Pipeline execution completed")
    all_responses = pre_responses + loop_responses + post_responses
    events_file.write_text(json.dumps(all_responses, indent=2))
    logger.info(f"Pipeline events saved to: {events_file}")

    state = final_session.state

    # Inject evidence deterministically from evidence_store into writer output
    writer_output_dict = state.get("deep_research_output")
    evidence_store_dict = state.get("evidence_store")

    if writer_output_dict and evidence_store_dict:
        writer_output = WriterOutput(**writer_output_dict)
        evidence_store = EvidenceStore(**evidence_store_dict)

        deep_research_output = DeepResearchOutput(
            **writer_output.model_dump(),
            evidence=evidence_store.items,
        )

        output_event = Event(
            actions=EventActions(
                state_delta={"deep_research_output": deep_research_output.model_dump()}
            )
        )
        await runner_post.session_service.append_event(final_session, output_event)

        # Refresh final_session
        final_session = await runner_post.session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=final_session.id,
        )
        state = final_session.state  # Update local reference

        logger.info(
            f"Injected {len(evidence_store.items)} evidence items into DeepResearchOutput"
        )

    logger.debug("Constructing SharedState from session state")
    shared_state = SharedState(
        drug_name=state.get("drug_name"),
        disease_name=state.get("indication"),
        research_plan=state.get("research_plan"),
        evidence_store=state.get("evidence_store"),
        research_head_plan=state.get("research_head_plan"),
        deep_research_output=state.get("deep_research_output"),
    )
    logger.info(
        f"SharedState populated: research_plan={'present' if shared_state.research_plan else 'missing'}, "
        f"evidence_store={'present' if shared_state.evidence_store else 'missing'}, "
        f"deep_research_output={'present' if shared_state.deep_research_output else 'missing'}"
    )

    return shared_state


def run_pipeline(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    **kwargs,
) -> SharedState:
    """
    Run the sequential agent pipeline and return populated shared state.

    Args:
        indication: The disease indication to research.
        drug_name: The drug name (e.g., "IL-2", "Aspirin").
        drug_form: The specific form of the drug (e.g., "low-dose IL-2").
        drug_generic_name: The generic name of the drug (e.g., "Aldesleukin").
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    logger.debug("Running pipeline synchronously via asyncio.run")
    return asyncio.run(
        run_pipeline_async(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
            **kwargs,
        )
    )


@app.command()
def main(
    indication: str = typer.Option(
        ..., "--indication", "-i", help="Disease indication to research"
    ),
    drug_name: str = typer.Option(
        ..., "--drug-name", "-d", help="Drug name (e.g., 'IL-2', 'Aspirin')"
    ),
    drug_form: str | None = typer.Option(
        None,
        "--drug-form",
        help="Specific form of the drug (e.g., 'low-dose IL-2')",
    ),
    drug_generic_name: str | None = typer.Option(
        None,
        "--drug-generic-name",
        help="Generic name of the drug (e.g., 'Aldesleukin')",
    ),
):
    """
    Run the deep research pipeline for a given disease indication.

    The pipeline executes a map-reduce architecture:
    1. Meta-planner creates structured research outline
    2. Parallel evidence collectors retrieve evidence for each section
    3. Deterministic aggregation function merges and deduplicates evidence
    4. Writer generates final structured output
    """
    logger.info(
        f"Starting deep research pipeline for indication: {indication}, drug: {drug_name}"
    )
    if drug_form:
        logger.info(f"Drug form specified: {drug_form}")
    if drug_generic_name:
        logger.info(f"Drug generic name specified: {drug_generic_name}")

    try:
        shared_state = run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
        )

        typer.echo(shared_state.model_dump_json(indent=2))

        logger.info("Pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
