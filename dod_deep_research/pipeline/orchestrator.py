"""Deep research pipeline orchestration."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from dod_deep_research.utils.evidence import EvidenceStore

from dod_deep_research.agents.research_head.agent import (
    RESEARCH_HEAD_PARALLEL_AGENT,
    RESEARCH_HEAD_QUAL_AGENT,
)
from dod_deep_research.agents.planner.agent import create_planner_agent
from dod_deep_research.agents.schemas import get_common_sections
from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.callbacks.update_evidence import update_evidence
from dod_deep_research.agents.shared_state import SharedState
from dod_deep_research.agents.writer.agent import section_writer_agent
from dod_deep_research.utils.writer import build_validation_report
from dod_deep_research.agents.writer.schemas import MarkdownReport
from dod_deep_research.core import (
    build_runner,
    get_output_path,
    persist_state_delta,
)
from dod_deep_research.evals import pipeline_eval
from dod_deep_research.pipeline.phases import (
    run_iterative_research,
    run_section_writer,
    run_plan_draft,
    write_long_report,
)
from dod_deep_research.prompts.indication_prompt import generate_indication_prompt
from dod_deep_research.utils.persistence import persist_output_artifacts

logger = logging.getLogger(__name__)


def _run_pipeline_in_new_loop(coro: Any) -> SharedState:
    """
    Runs a coroutine in a dedicated event loop from a worker thread.

    Args:
        coro (Any): Coroutine to execute.

    Returns:
        SharedState: Pipeline shared state returned by the coroutine.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


async def run_pipeline_async(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
    **kwargs: Any,
) -> SharedState:
    """
    Run the deep research pipeline asynchronously and return populated shared state.

    Args:
        indication: The disease indication to research.
        drug_name: The drug name (e.g., "IL-2", "Aspirin").
        drug_form: The specific form of the drug (e.g., "low-dose IL-2").
        drug_generic_name: The generic name of the drug (e.g., "Aldesleukin").
        indication_aliases: Optional aliases for indication search.
        drug_aliases: Optional aliases for drug search.
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    logger.info(
        "Initializing pipeline: indication=%s, drug_name=%s, drug_form=%s, drug_generic_name=%s",
        indication,
        drug_name,
        drug_form,
        drug_generic_name,
    )

    app_name = "deep_research"
    user_id = "user"

    indication_prompt = generate_indication_prompt(
        disease=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
    )  # generate prompt for the planner agent based on cli arguments

    ######################
    # Plan Draft
    ######################
    planner_agent = create_planner_agent(
        indication_prompt=indication_prompt
    )  # dynamically create planner agent
    common_sections = [section.value for section in get_common_sections()]
    plan_runner = build_runner(
        agent=planner_agent,
        app_name=app_name,
    )
    draft_runner = build_runner(
        agent=create_collector_agents(
            common_sections,
            after_agent_callback=update_evidence,
        ),
        app_name=app_name,
    )  # create target collector agents based on common sections that update the evidence store after running

    session = await run_plan_draft(
        app_name=app_name,
        plan_runner=plan_runner,
        draft_runner=draft_runner,
        user_id=user_id,
        indication=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
        indication_aliases=indication_aliases,
        drug_aliases=drug_aliases,
        common_sections=common_sections,
        **kwargs,
    )  # pass the session downstream to the next phases

    ######################
    # Iterative Research
    ######################
    research_head_parallel_runner = build_runner(
        agent=RESEARCH_HEAD_PARALLEL_AGENT, app_name=app_name
    )
    research_head_qual_runner = build_runner(
        agent=RESEARCH_HEAD_QUAL_AGENT, app_name=app_name
    )
    research_head_session = await run_iterative_research(
        app_name=app_name,
        research_head_parallel_runner=research_head_parallel_runner,
        research_head_qual_runner=research_head_qual_runner,
        session=session,
    )  # pass the session downstream to the next phase

    ######################
    # Section Writer
    ######################
    section_writer_runner = build_runner(
        agent=section_writer_agent,
        app_name=app_name,
    )
    final_session = await run_section_writer(
        app_name=app_name,
        section_writer_runner=section_writer_runner,
        session_loop=research_head_session,
    )

    state = final_session.state

    writer_output_dict = state.get("deep_research_output")
    evidence_store_dict = state.get("evidence_store")

    if writer_output_dict and evidence_store_dict:
        evidence_store = EvidenceStore(**evidence_store_dict)
        report_markdown = writer_output_dict.get("report_markdown", "")
        validation_report = build_validation_report(
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
                section_writer_runner.session_service,
                final_session,
                {"validation_report": validation_report},
            )
            rewrite_report = await write_long_report(
                runner=section_writer_runner,
                app_name=app_name,
                user_id=final_session.user_id,
                base_state=final_session.state,
            )
            final_session = await persist_state_delta(
                section_writer_runner.session_service,
                final_session,
                {"deep_research_output": rewrite_report.model_dump()},
            )
            state = final_session.state

    writer_output_dict = state.get("deep_research_output")
    output_dir = get_output_path(indication)
    report_path = None
    if writer_output_dict:
        writer_output = MarkdownReport(**writer_output_dict)
        report_path = output_dir / "report.md"
        report_path.write_text(writer_output.report_markdown)
        logger.info("Markdown report saved to: %s", report_path)

    state_file = output_dir / "session_state.json"
    state_file.write_text(json.dumps(state, indent=2, default=str))
    logger.info("Session state saved to: %s", state_file)

    agent_logs_dir = output_dir.parent / "agent_logs"
    evals = pipeline_eval(agent_logs_dir, evidence_store_dict)
    evals_file = output_dir / "pipeline_evals.json"
    evals_file.write_text(json.dumps(evals, indent=2, default=str))
    logger.info("Pipeline evals saved to: %s", evals_file)
    persisted_artifacts = persist_output_artifacts(
        output_dir=output_dir,
        report_path=report_path,
        state_file=state_file,
        evals_file=evals_file,
    )
    logger.info(
        "Uploaded %d artifacts to %s",
        len(persisted_artifacts.artifacts),
        persisted_artifacts.bucket_name,
    )

    return SharedState(
        drug_name=state.get("drug_name"),
        disease_name=state.get("indication"),
        research_plan=state.get("research_plan"),
        evidence_store=state.get("evidence_store"),
        research_head_quant_plan=state.get("research_head_quant_plan"),
        research_head_qual_plan=state.get("research_head_qual_plan"),
        deep_research_output=state.get("deep_research_output"),
    )


def run_pipeline(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
    **kwargs: Any,
) -> SharedState:
    """
    Run the deep research pipeline synchronously and return populated shared state.

    Args:
        indication: The disease indication to research.
        drug_name: The drug name.
        drug_form: The specific form of the drug.
        drug_generic_name: The generic name of the drug.
        indication_aliases: Optional aliases for indication search.
        drug_aliases: Optional aliases for drug search.
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    pipeline_coro = run_pipeline_async(
        indication=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
        indication_aliases=indication_aliases,
        drug_aliases=drug_aliases,
        **kwargs,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(pipeline_coro)
    return _run_pipeline_in_new_loop(pipeline_coro)
