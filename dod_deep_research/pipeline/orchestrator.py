"""Deep research pipeline orchestration."""

import asyncio
import json
import logging
from typing import Any

from dod_deep_research.utils.evidence import EvidenceStore
from dod_deep_research.agents.research_head.agent import research_head_agent
from dod_deep_research.agents.planner.agent import create_planner_agent
from dod_deep_research.agents.schemas import get_common_sections
from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.callbacks.update_evidence_and_gaps import (
    update_evidence_and_gaps,
)
from dod_deep_research.agents.shared_state import SharedState
from dod_deep_research.agents.writer.agent import section_writer_agent
from dod_deep_research.utils.writer import build_validation_report
from dod_deep_research.agents.writer.schemas import MarkdownReport
from dod_deep_research.core import (
    build_runner,
    get_output_events_path,
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

logger = logging.getLogger(__name__)


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
            after_agent_callback=update_evidence_and_gaps,
        ),
        app_name=app_name,
    )  # create target collector agents based on common sections that update the evidence store after running

    events_file = get_output_events_path(indication)
    logger.info("Events will be saved to: %s", events_file)

    session, pre_responses = await run_plan_draft(
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
    research_head_runner = build_runner(
        agent=research_head_agent, app_name=app_name
    )  # target collectors are created dynamically based on plan
    session_loop, loop_responses = await run_iterative_research(
        app_name=app_name,
        runner_research_head=research_head_runner,
        session=session,
    )  # pass the session downstream to the next phase

    ######################
    # Section Writer
    ######################
    section_writer_runner = build_runner(
        agent=section_writer_agent,
        app_name=app_name,
    )
    final_session, post_responses = await run_section_writer(
        app_name=app_name,
        section_writer_runner=section_writer_runner,
        session_loop=session_loop,
    )

    all_responses = pre_responses + loop_responses + post_responses
    events_file.write_text(json.dumps(all_responses, indent=2))
    logger.info("Pipeline events saved to: %s", events_file)

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
            rewrite_report, _ = await write_long_report(
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

    return SharedState(
        drug_name=state.get("drug_name"),
        disease_name=state.get("indication"),
        research_plan=state.get("research_plan"),
        evidence_store=state.get("evidence_store"),
        research_head_plan=state.get("research_head_plan"),
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
