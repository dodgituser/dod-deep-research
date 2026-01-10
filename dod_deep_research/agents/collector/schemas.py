"""Schemas for collector agent."""

from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from dod_deep_research.agents.planner.schemas import CommonSection, get_common_sections
from dod_deep_research.agents.schemas import EvidenceSource


class EvidenceItem(BaseModel):
    """Evidence citation item."""

    id: str = Field(
        ...,
        description=(
            "Short evidence ID (e.g., 'E1'); will be prefixed with the section name."
        ),
    )
    source: EvidenceSource = Field(
        ...,
        description="Source type of the evidence.",
    )
    title: str = Field(..., description="Exact title of the source.")
    url: str | None = Field(
        None,
        description=(
            "Canonical URL for the source (required for pubmed/clinicaltrials)."
        ),
    )
    quote: str = Field(
        ...,
        description="Direct supporting quote or excerpt from the source.",
    )
    year: int | None = Field(None, description="Publication year, if known.")
    tags: list[str] = Field(
        default_factory=list,
        description="Short topical tags to help retrieval and grouping.",
    )
    section: CommonSection = Field(
        ...,
        description="Section name this evidence supports (must match plan sections).",
    )

    @field_validator("section")
    @classmethod
    def validate_section(cls, v: str) -> str:
        """Validate that section is one of the common sections."""
        common_sections = [s.value for s in get_common_sections()]
        if v not in common_sections:
            raise ValueError(f"Section must be one of {common_sections}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_and_prefix_id(self) -> Self:
        """Normalize evidence IDs by prefixing with the section name."""
        if not self.id.startswith(f"{self.section}_"):
            self.id = f"{self.section}_{self.id}"
        return self


class CollectorResponse(BaseModel):
    """Response containing evidence items for a specific section."""

    section: CommonSection = Field(
        ...,
        description="Section name that this collector was assigned.",
    )
    evidence: list[dict[str, str | int | list[str] | None]] = Field(
        ...,
        description=(
            "Evidence items collected for the assigned section. Each item is a dict with keys: "
            "id (str), source (str: 'google'|'pubmed'|'clinicaltrials'|'guideline'|'press_release'|'other'), "
            "title (str), url (str|None), quote (str), year (int|None), tags (list[str]), section (str)."
        ),
    )

    @model_validator(mode="after")
    def validate_and_convert_evidence(self) -> Self:
        """Convert evidence dicts to EvidenceItem objects for validation."""
        common_sections = [s.value for s in get_common_sections()]

        # Convert dicts to EvidenceItem objects for validation
        evidence_items = []
        for ev_dict in self.evidence:
            item = EvidenceItem(**ev_dict)
            evidence_items.append(item)

        # Validate non-empty evidence
        if self.section in common_sections and not evidence_items:
            raise ValueError(
                f"Evidence list cannot be empty for required section '{self.section}'"
            )
        if self.section in common_sections and len(evidence_items) < 3:
            raise ValueError(
                f"Evidence list must include at least 3 items for required section '{self.section}'"
            )

        return self

    @property
    def evidence_items(self) -> list[EvidenceItem]:
        """Get evidence as EvidenceItem objects."""
        return [EvidenceItem(**item) for item in self.evidence]
