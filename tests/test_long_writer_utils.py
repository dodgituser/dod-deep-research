"""Unit tests for long-writer utilities."""

from dod_deep_research.agents.collector.schemas import EvidenceItem
from dod_deep_research.utils.evidence import EvidenceStore
from dod_deep_research.agents.writer.long_writer import (
    build_references_section,
    extract_citation_ids,
    normalize_section_markdown,
)


def test_extract_citation_ids_preserves_order():
    text = (
        "Overview [disease_overview_E2] and more text [disease_overview_E1]. "
        "Repeated [disease_overview_E2] should not duplicate."
    )
    assert extract_citation_ids(text) == [
        "disease_overview_E2",
        "disease_overview_E1",
    ]


def test_normalize_section_markdown_overrides_heading():
    raw = "# Old Title\nSome content\n## Subsection"
    normalized = normalize_section_markdown(raw, "disease_overview")
    assert normalized.startswith("## disease_overview\n")
    assert "### Subsection" in normalized


def test_build_references_section_uses_cited_ids():
    evidence_items = [
        EvidenceItem(
            id="E1",
            source="pubmed",
            title="ALS Overview",
            url="https://example.com/als",
            quote="ALS is a neurodegenerative disease",
            year=2023,
            tags=["disease"],
            section="disease_overview",
        ),
        EvidenceItem(
            id="E2",
            source="clinicaltrials",
            title="IL-2 Trial",
            url="https://clinicaltrials.gov/NCT00000000",
            quote="Phase 2 trial of IL-2 in ALS patients",
            year=2024,
            tags=["trial"],
            section="clinical_trials_analysis",
        ),
    ]
    evidence_store = EvidenceStore(
        items=evidence_items,
        by_section=[],
        by_source=[],
        hash_index=[],
    )
    cited_ids = ["disease_overview_E1", "clinical_trials_analysis_E2"]
    references = build_references_section(cited_ids, evidence_store)
    assert "[disease_overview_E1] ALS Overview - https://example.com/als" in references
    assert (
        "[clinical_trials_analysis_E2] IL-2 Trial - "
        "https://clinicaltrials.gov/NCT00000000"
    ) in references
