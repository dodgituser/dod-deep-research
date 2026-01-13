"""Deep research pipeline entry point."""

import asyncio
import json
import re
import uuid

import typer
from google.genai import types

from google.adk import runners

from dod_deep_research.core import (
    build_runner,
    run_agent,
    get_output_file,
    persist_state_delta,
    prepare_outputs_dir,
    normalize_aliases,
)

from dod_deep_research.agents.collector.agent import (
    create_collector_agents,
    create_targeted_collector_agents,
)
from dod_deep_research.agents.planner.agent import create_planner_agent
from dod_deep_research.agents.research_head.agent import research_head_agent
from dod_deep_research.agents.planner.schemas import get_common_sections
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.research_head.schemas import (
    ResearchHeadPlan,
)
from dod_deep_research.agents.writer.agent import section_writer_agent
from dod_deep_research.agents.writer.long_writer import write_long_report
from dod_deep_research.agents.evidence import (
    EvidenceStore,
    aggregate_evidence_after_collectors,
)
from dod_deep_research.agents.shared_state import SharedState
from dod_deep_research.agents.writer.schemas import MarkdownReport
from dod_deep_research.evals import pipeline_eval
from dod_deep_research.prompts.indication_prompt import generate_indication_prompt
from dod_deep_research.loggy import setup_logging
import logging

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)
app = typer.Typer()


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
    **kwargs,
) -> tuple[runners.Session, list[dict]]:
    """Run the pre-aggregation phase (planner + collectors)."""
    logger.info("Starting pre-aggregation phase (planner + collectors)")
    common_sections = [section.value for section in get_common_sections()]
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
            "common_sections": common_sections,
            **kwargs,
        },
    )
    logger.debug(f"Created session in pre-aggregation: {session.id}")

    # run research planner
    json_responses = await run_agent(
        runner_planner,
        session.user_id,
        session.id,
        types.Content(
            parts=[types.Part.from_text(text="Plan the research.")], role="user"
        ),
    )

    logger.info("Planner phase completed")

    updated_session = await runner_planner.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )

    state = updated_session.state
    logger.info(f"Session state keys: {list(state.keys())}")

    research_plan = state.get("research_plan")
    # If research_plan is present, extract sections and update state
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
        except Exception as exc:
            logger.warning("Failed to persist research section state: %s", exc)
        else:
            state = updated_session.state
    # Run inital draft collectors
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
    state = updated_session.state

    logger.info("Pre-aggregation phase completed")
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
    logger.debug(f"Created session in gap-driven loop runner: {session_loop.id}")

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

        session_loop = await persist_state_delta(
            runner_loop.session_service,
            session_loop,
            updated_targeted_session.state,
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
    evidence_store_dict = session_post.state.get("evidence_store")
    if evidence_store_dict:
        evidence_store = EvidenceStore(**evidence_store_dict)
        session_post = await persist_state_delta(
            runner_post.session_service,
            session_post,
            {"allowed_evidence_ids": [item.id for item in evidence_store.items]},
        )
    report, json_responses = await write_long_report(
        runner=runner_post,
        app_name=app_name,
        user_id=session_post.user_id,
        base_state=session_post.state,
    )
    session_post = await persist_state_delta(
        runner_post.session_service,
        session_post,
        {"deep_research_output": report.model_dump()},
    )
    logger.debug(f"Created session in post-aggregation runner: {session_post.id}")
    return session_post, json_responses


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
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
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
    runner_planner = build_runner(agent=planner_agent, app_name=app_name)
    runner_collectors = build_runner(
        agent=create_collector_agents(
            [section.value for section in get_common_sections()],
            after_agent_callback=aggregate_evidence_after_collectors,
        ),
        app_name=app_name,
    )
    runner_loop = build_runner(agent=research_head_agent, app_name=app_name)
    runner_post = build_runner(agent=section_writer_agent, app_name=app_name)

    events_file = get_output_file(indication)
    logger.info(f"Events will be saved to: {events_file}")

    # Phase 1: Pre-aggregation
    session, pre_responses = await run_pre_aggregation(
        app_name=app_name,
        runner_planner=runner_planner,
        runner_collectors=runner_collectors,
        user_id=user_id,
        session_id=session_id,
        indication=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
        indication_aliases=indication_aliases,
        drug_aliases=drug_aliases,
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
            final_session = await persist_state_delta(
                runner_post.session_service,
                final_session,
                {"validation_report": validation_report},
            )
            rewrite_report, _ = await write_long_report(
                runner=runner_post,
                app_name=app_name,
                user_id=final_session.user_id,
                base_state=final_session.state,
            )
            final_session = await persist_state_delta(
                runner_post.session_service,
                final_session,
                {"deep_research_output": rewrite_report.model_dump()},
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

    agent_logs_dir = events_file.parent.parent / "agent_logs"
    evals = pipeline_eval(agent_logs_dir, evidence_store_dict)
    evals_file = events_file.parent / "pipeline_evals.json"
    evals_file.write_text(json.dumps(evals, indent=2, default=str))
    logger.info(f"Pipeline evals saved to: {evals_file}")

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
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
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
            indication_aliases=indication_aliases,
            drug_aliases=drug_aliases,
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
    indication_alias: list[str] = typer.Option(
        [],
        "--indication-alias",
        help='Indication alias (repeatable), e.g. --indication-alias "Alzheimer disease"',
    ),
    drug_alias: list[str] = typer.Option(
        [],
        "--drug-alias",
        help="Drug/asset alias (repeatable), e.g. --drug-alias Aldesleukin",
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
        prepare_outputs_dir()
        normalized_indication_aliases = normalize_aliases(indication_alias)
        normalized_drug_aliases = normalize_aliases(drug_alias)
        run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
            indication_aliases=normalized_indication_aliases,
            drug_aliases=normalized_drug_aliases,
        )

        logger.info("Pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
