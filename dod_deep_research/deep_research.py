"""Deep research pipeline entry point."""

import asyncio
import json
import re
import shutil
import uuid
from pathlib import Path

import typer
from google.genai import types

from google.adk import runners
from google.adk.events import Event, EventActions

from dod_deep_research.core import build_runner, run_agent, get_output_file

from dod_deep_research.agents.collector.agent import create_targeted_collector_agents
from dod_deep_research.agents.planner.agent import create_planner_agent
from dod_deep_research.agents.research_head.agent import research_head_agent
from dod_deep_research.agents.planner.schemas import get_common_sections, ResearchPlan
from dod_deep_research.agents.research_head.schemas import (
    ResearchHeadPlan,
)
from dod_deep_research.agents.sequence_agents import (
    get_pre_aggregation_agent,
    get_post_aggregation_agent,
)
from dod_deep_research.agents.evidence import (
    EvidenceStore,
    aggregate_evidence_after_collectors,
)
from dod_deep_research.agents.shared_state import SharedState
from dod_deep_research.agents.writer.schemas import MarkdownReport
from dod_deep_research.prompts.indication_prompt import generate_indication_prompt
from dod_deep_research.loggy import setup_logging
import logging

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)
app = typer.Typer()


def _prepare_outputs_dir() -> Path:
    """
    Create the outputs directory and clear any existing run subdirectories.

    Returns:
        Path: Path to the outputs directory.
    """
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    for entry in outputs_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
    return outputs_dir


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
    user_prompt = "Run the research pipeline"
    new_message = types.Content(
        parts=[types.Part.from_text(text=user_prompt)],
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

    state = updated_session.state
    logger.info(f"Session state keys: {list(state.keys())}")

    research_plan = state.get("research_plan")
    if research_plan:
        try:
            plan = ResearchPlan(**research_plan)
        except Exception as exc:
            logger.warning("Failed to parse research_plan for section state: %s", exc)
        else:
            section_state = {
                f"research_section_{section.name}": section.model_dump()
                for section in plan.sections
            }
            if section_state:
                merge_event = Event(
                    author="user",
                    actions=EventActions(state_delta=section_state),
                )
                await runner_pre.session_service.append_event(
                    updated_session, merge_event
                )
                updated_session = await runner_pre.session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session.id,
                )
                state = updated_session.state

    evidence_store = state.get("evidence_store")
    if evidence_store:
        logger.info("Evidence store already aggregated by collectors callback")
    else:
        logger.warning("Evidence store missing after collectors")

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
        if not research_head_plan_dict:
            logger.info("No research_head_plan found after analysis")
            continue

        try:
            research_head_plan = ResearchHeadPlan(**research_head_plan_dict)
        except Exception as e:
            logger.warning(f"Failed to parse research_head_plan: {e}")
            continue
        logger.info(
            "ResearchHead plan summary: "
            f"continue_research={research_head_plan.continue_research}, "
            f"gaps={len(research_head_plan.gaps)}"
        )

        if not research_head_plan.gaps:
            logger.info("ResearchHead determined gaps are resolved")
            break

        logger.info(
            f"Running targeted collectors for {len(research_head_plan.gaps)} gaps"
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

        merge_event = Event(
            author="user",
            actions=EventActions(state_delta=updated_targeted_session.state),
        )
        await runner_loop.session_service.append_event(session_loop, merge_event)

        session_loop = await runner_loop.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )
    # If max iterations is reached, run final gap analysis else we have already run the final gap analysis
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


async def run_post_aggregation(
    app_name: str,
    runner_post: runners.Runner,
    user_id: str,
    session_loop: runners.Session,
) -> tuple[runners.Session, list[dict]]:
    """Run the post-aggregation phase (writer)."""
    logger.info("Starting post-aggregation phase (writer)")

    state_for_post = session_loop.state.copy()
    evidence_store_dict = state_for_post.get("evidence_store")
    if evidence_store_dict:
        evidence_store = EvidenceStore(**evidence_store_dict)
        state_for_post["allowed_evidence_ids"] = [
            item.id for item in evidence_store.items
        ]

    session_post = await runner_post.session_service.create_session(
        app_name=app_name,
        user_id=session_loop.user_id,
        session_id=session_loop.id,
        state=state_for_post,
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


def _extract_citation_ids(report_markdown: str) -> set[str]:
    """
    Extract bracketed evidence IDs from the markdown report.

    Args:
        report_markdown (str): Markdown report text.

    Returns:
        set[str]: Unique evidence IDs referenced in the report.
    """
    if not report_markdown:
        return set()
    return set(re.findall(r"\[([A-Za-z0-9_]+_E\d+)\]", report_markdown))


def _build_validation_report(
    report_markdown: str,
    evidence_store: EvidenceStore,
    indication: str,
    drug_name: str,
) -> dict[str, list[str]]:
    """
    Build validation errors and warnings for the markdown report.

    Args:
        report_markdown (str): Markdown report text.
        evidence_store (EvidenceStore): Aggregated evidence store.
        indication (str): Disease/indication name.
        drug_name (str): Drug name.

    Returns:
        dict[str, list[str]]: Validation report with errors and warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    report_lower = report_markdown.lower()
    if indication.lower() not in report_lower:
        errors.append(f"Report must mention indication '{indication}'.")
    if drug_name.lower() not in report_lower:
        errors.append(f"Report must mention drug name '{drug_name}'.")

    evidence_ids = {item.id for item in evidence_store.items}
    cited_ids = _extract_citation_ids(report_markdown)
    unknown_citations = sorted(cited_ids - evidence_ids)
    if unknown_citations:
        errors.append(
            "Report cites evidence IDs not present in evidence_store: "
            + ", ".join(unknown_citations)
        )

    if not cited_ids:
        warnings.append("Report includes no evidence citations.")

    return {"errors": errors, "warnings": warnings}


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
    indication_prompt = generate_indication_prompt(
        disease=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
    )
    logger.debug("Generated indication prompt for planner.")
    planner_agent = create_planner_agent(indication_prompt=indication_prompt)
    runner_pre = build_runner(
        agent=get_pre_aggregation_agent(planner=planner_agent),
        app_name=app_name,
    )
    runner_loop = build_runner(agent=research_head_agent, app_name=app_name)
    runner_post = build_runner(agent=get_post_aggregation_agent(), app_name=app_name)

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

    # Validate and optionally re-run writer if output is off-topic or cites unknown evidence.
    writer_output_dict = state.get("deep_research_output")
    evidence_store_dict = state.get("evidence_store")

    if writer_output_dict and evidence_store_dict:
        evidence_store = EvidenceStore(**evidence_store_dict)
        report_markdown = writer_output_dict.get("report_markdown", "")
        validation_report = _build_validation_report(
            report_markdown=report_markdown,
            evidence_store=evidence_store,
            indication=indication,
            drug_name=drug_name,
        )

        if validation_report["errors"]:
            logger.warning(
                "Writer output validation failed, requesting rewrite: %s",
                validation_report["errors"],
            )
            validation_event = Event(
                author="user",
                actions=EventActions(
                    state_delta={"validation_report": validation_report}
                ),
            )
            await runner_post.session_service.append_event(
                final_session, validation_event
            )

            rewrite_message = types.Content(
                parts=[
                    types.Part.from_text(
                        text="Rewrite the report to address validation_report errors. "
                        "Use only evidence_store citations."
                    )
                ],
                role="user",
            )
            await run_agent(
                runner_post,
                final_session.user_id,
                final_session.id,
                rewrite_message,
            )
            final_session = await runner_post.session_service.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=final_session.id,
            )
            state = final_session.state

    writer_output_dict = state.get("deep_research_output")
    if writer_output_dict:
        writer_output = MarkdownReport(**writer_output_dict)
        report_path = events_file.parent / "report.md"
        report_path.write_text(writer_output.report_markdown)
        logger.info(f"Markdown report saved to: {report_path}")

    state_file = events_file.parent / "session_state.json"
    state_file.write_text(json.dumps(state, indent=2, default=str))
    logger.info(f"Session state saved to: {state_file}")

    logger.debug("Constructing SharedState from session state")
    shared_state = SharedState(
        drug_name=state.get("drug_name"),
        disease_name=state.get("indication"),
        research_plan=state.get("research_plan"),
        evidence_store=state.get("evidence_store"),
        research_head_plan=state.get("research_head_plan"),
        deep_research_output=state.get("deep_research_output"),
    )
    logger.debug(
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
        _prepare_outputs_dir()
        shared_state = run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
        )

        if shared_state.deep_research_output:
            typer.echo(shared_state.deep_research_output.report_markdown)
        else:
            typer.echo(shared_state.model_dump_json(indent=2))

        logger.info("Pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
