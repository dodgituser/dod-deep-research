"""Long-form report assembly using section-by-section writing."""

import re
import uuid
from typing import Any

from google.adk import runners
from google.genai import types

from dod_deep_research.agents.planner.schemas import ResearchPlan, ResearchSection
from dod_deep_research.agents.writer.schemas import MarkdownReport, SectionDraft
from dod_deep_research.agents.evidence import EvidenceStore, build_section_evidence
from dod_deep_research.core import run_agent


def build_report_title(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
) -> str:
    """
    Build a report title from drug and indication metadata.

    Args:
        indication (str): Disease or indication name.
        drug_name (str): Drug name.
        drug_form (str | None): Drug form if provided.
        drug_generic_name (str | None): Drug generic name if provided.

    Returns:
        str: Report title.
    """
    drug_label = drug_form or drug_name
    generic_suffix = f" ({drug_generic_name})" if drug_generic_name else ""
    return f"{drug_label}{generic_suffix} for {indication}"


def format_table_of_contents(sections: list[ResearchSection]) -> str:
    """
    Format a markdown table of contents for report sections.

    Args:
        sections (list[ResearchSection]): Ordered report sections.

    Returns:
        str: Markdown table of contents.
    """
    if not sections:
        return "## Table of Contents\n\n"
    items = "\n".join(
        f"{index + 1}. {str(section.name)}" for index, section in enumerate(sections)
    )
    return f"## Table of Contents\n\n{items}\n\n"


def normalize_section_markdown(section_markdown: str, section_title: str) -> str:
    """
    Normalize section headings to ensure a level-2 header with the correct title.

    Args:
        section_markdown (str): Raw markdown from the section writer.
        section_title (str): Section title to enforce.

    Returns:
        str: Normalized section markdown.
    """
    if not section_markdown.strip():
        return f"## {section_title}\n"

    first_heading_match = re.search(r"^(#+)\s+(.+)$", section_markdown, re.MULTILINE)
    if not first_heading_match:
        return f"## {section_title}\n\n{section_markdown.strip()}\n"

    first_heading_level = len(first_heading_match.group(1))
    level_adjustment = 2 - first_heading_level

    def adjust_heading(match: re.Match[str]) -> str:
        hashes = match.group(1)
        content = match.group(2)
        new_level = max(2, len(hashes) + level_adjustment)
        return f"{'#' * new_level} {content}"

    section_markdown = re.sub(
        r"^(#+)\s+(.+)$",
        adjust_heading,
        section_markdown,
        flags=re.MULTILINE,
    )
    section_markdown = re.sub(
        r"^(#+)\s+(.+)$",
        f"## {section_title}",
        section_markdown,
        count=1,
        flags=re.MULTILINE,
    )
    return section_markdown.strip() + "\n"


def extract_citation_ids(report_markdown: str) -> list[str]:
    """
    Extract evidence IDs from report markdown in order of appearance.

    Args:
        report_markdown (str): Markdown report text.

    Returns:
        list[str]: Ordered evidence IDs referenced in the report.
    """
    if not report_markdown:
        return []

    seen: set[str] = set()
    ordered_ids: list[str] = []
    for match in re.finditer(r"\[([A-Za-z0-9_]+_E\d+)\]", report_markdown):
        evidence_id = match.group(1)
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        ordered_ids.append(evidence_id)
    return ordered_ids


def build_references_section(
    cited_ids: list[str],
    evidence_store: EvidenceStore,
) -> str:
    """
    Build the references section from cited evidence IDs.

    Args:
        cited_ids (list[str]): Evidence IDs cited in the report.
        evidence_store (EvidenceStore): Aggregated evidence store.

    Returns:
        str: Markdown references section.
    """
    evidence_by_id = {item.id: item for item in evidence_store.items}
    lines: list[str] = []
    for evidence_id in cited_ids:
        item = evidence_by_id.get(evidence_id)
        if not item:
            continue
        url = item.url or ""
        if url:
            lines.append(f"[{evidence_id}] {item.title} - {url}")
        else:
            lines.append(f"[{evidence_id}] {item.title}")
    references_body = "\n".join(lines)
    if references_body:
        return f"## References\n\n{references_body}\n"
    return "## References\n\n"


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
        section_state = base_state.copy()
        section_state.update(
            {
                "current_report_draft": report_draft,
                "current_section": section.model_dump(),
                "current_section_name": str(section.name),
                "section_evidence": build_section_evidence(
                    evidence_store, str(section.name)
                ),
                "allowed_evidence_ids": allowed_evidence_ids,
            }
        )
        session = await runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            state=section_state,
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
