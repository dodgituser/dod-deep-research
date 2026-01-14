"""Post-aggregation (writing) phase helpers."""

from typing import Any

from google.adk import runners
from google.genai import types

from dod_deep_research.utils.evidence import EvidenceStore, build_section_evidence
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.writer.schemas import MarkdownReport, SectionDraft
from dod_deep_research.utils.writer import (
    build_references_section,
    build_report_title,
    extract_citation_ids,
    format_table_of_contents,
    normalize_section_markdown,
)
from dod_deep_research.core import persist_state_delta, run_agent


async def write_long_report(
    runner: runners.InMemoryRunner,
    app_name: str,
    user_id: str,
    base_state: dict[str, Any],
) -> tuple[MarkdownReport, list[dict]]:
    """
    Write a report by iteratively generating each section.

    Args:
        runner (runners.InMemoryRunner): Runner for the section writer agent.
        app_name (str): Application name for session creation.
        user_id (str): User ID for the session.
        base_state (dict[str, Any]): Shared state containing plan and evidence.

    Returns:
        tuple[MarkdownReport, list[dict]]: Final report and JSON responses.
    """
    research_plan_dict = base_state.get("research_plan")
    evidence_store_dict = base_state.get("evidence_store")
    if not research_plan_dict:
        raise ValueError("Missing research_plan in state for long writer.")
    if not evidence_store_dict:
        raise ValueError("Missing evidence_store in state for long writer.")

    research_plan = ResearchPlan(**research_plan_dict)
    evidence_store = EvidenceStore(**evidence_store_dict)
    allowed_evidence_ids = base_state.get("allowed_evidence_ids")
    if not allowed_evidence_ids:
        allowed_evidence_ids = [item.id for item in evidence_store.items]

    report_title = build_report_title(
        indication=base_state.get("indication", ""),
        drug_name=base_state.get("drug_name", ""),
        drug_form=base_state.get("drug_form"),
        drug_generic_name=base_state.get("drug_generic_name"),
    )
    report_draft = f"# {report_title}\n\n"
    report_draft += format_table_of_contents(research_plan.sections)

    json_responses: list[dict] = []

    for section in research_plan.sections:
        session = await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            state=base_state.copy(),
        )
        session = await persist_state_delta(
            runner.session_service,
            session,
            {
                "current_report_draft": report_draft,
                "current_section": section.model_dump(),
                "current_section_name": str(section.name),
                "section_evidence": build_section_evidence(
                    evidence_store, str(section.name)
                ),
                "allowed_evidence_ids": allowed_evidence_ids,
            },
        )
        responses = await run_agent(
            runner,
            session.user_id,
            session.id,
            types.Content(
                parts=[types.Part.from_text(text="Write the section.")],
                role="user",
            ),
        )
        json_responses.extend(responses)
        if not responses:
            raise ValueError(f"No response for section '{section.name}'.")
        section_draft = SectionDraft(**responses[-1])
        section_markdown = normalize_section_markdown(
            section_draft.section_markdown,
            str(section.name),
        )
        report_draft += f"{section_markdown}\n"

    cited_ids = extract_citation_ids(report_draft)
    references_section = build_references_section(cited_ids, evidence_store)
    report_markdown = f"{report_draft}\n{references_section}".strip() + "\n"

    return MarkdownReport(report_markdown=report_markdown), json_responses


async def run_post_aggregation(
    app_name: str,
    runner_post: runners.Runner,
    session_loop: runners.Session,
) -> tuple[runners.Session, list[dict]]:
    """
    Run the post-aggregation phase (writer).

    Args:
        app_name (str): App name for session creation.
        runner_post (runners.Runner): Runner for the section writer agent.
        session_loop (runners.Session): The loop session containing evidence and plan.

    Returns:
        tuple[runners.Session, list[dict]]: Updated session and JSON responses.
    """
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
    return session_post, json_responses
