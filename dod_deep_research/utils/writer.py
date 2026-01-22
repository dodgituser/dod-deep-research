"""Long-writer utilities (markdown + validation)"""

import re

from dod_deep_research.agents.planner.schemas import ResearchSection
from dod_deep_research.utils.evidence import EvidenceStore


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
        f"{index + 1}. {format_section_title(str(section.name))}"
        for index, section in enumerate(sections)
    )
    return f"## Table of Contents\n\n{items}\n\n"


def format_section_title(section_title: str) -> str:
    """
    Format a section name for display in report headers.

    Args:
        section_title (str): Raw section title or name.

    Returns:
        str: Human-readable section title.
    """
    if not section_title:
        return ""
    return section_title.replace("_", " ").strip().title()


def normalize_section_markdown(section_markdown: str, section_title: str) -> str:
    """
    Normalize section headings to ensure a level-2 header with the correct title.

    Args:
        section_markdown (str): Raw markdown from the section writer.
        section_title (str): Section title to enforce.

    Returns:
        str: Normalized section markdown.
    """
    section_title = format_section_title(section_title)
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
    for match in re.finditer(r"\[([A-Za-z0-9_,\s]+)\]", report_markdown):
        for raw_id in match.group(1).split(","):
            evidence_id = raw_id.strip()
            if not evidence_id:
                continue
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


def build_validation_report(
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

    report_lower = (report_markdown or "").lower()
    if indication and indication.lower() not in report_lower:
        errors.append(f"Report must mention indication '{indication}'.")
    if drug_name and drug_name.lower() not in report_lower:
        errors.append(f"Report must mention drug name '{drug_name}'.")

    evidence_ids = {item.id for item in evidence_store.items}
    cited_ids = set(extract_citation_ids(report_markdown))
    unknown_citations = sorted(cited_ids - evidence_ids)
    if unknown_citations:
        errors.append(
            "Report cites evidence IDs not present in evidence_store: "
            + ", ".join(unknown_citations)
        )

    if not cited_ids:
        warnings.append("Report includes no evidence citations.")

    return {"errors": errors, "warnings": warnings}
