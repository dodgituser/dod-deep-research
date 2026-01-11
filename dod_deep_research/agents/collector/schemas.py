"""Schemas for collector agent."""

import logging

from typing import Any, Annotated, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import WithJsonSchema

from dod_deep_research.agents.planner.schemas import get_common_sections
from dod_deep_research.agents.schemas import EvidenceSource
from dod_deep_research.core import inline_json_schema


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
    section: str = Field(
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


EVIDENCE_ITEM_SCHEMA = inline_json_schema(EvidenceItem)


class CollectorResponse(BaseModel):
    """Response containing evidence items for a specific section."""

    section: str = Field(
        ...,
        description="Section name that this collector was assigned.",
    )
    evidence: list[Annotated[EvidenceItem, WithJsonSchema(EVIDENCE_ITEM_SCHEMA)]] = (
        Field(
            ...,
            description="Evidence items collected for the assigned section.",
        )
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_evidence(cls, data: Any) -> Any:
        """Normalize evidence input before Pydantic validation."""
        if not isinstance(data, dict):
            return data

        section = data.get("section")
        evidence = data.get("evidence")
        if not section or not isinstance(evidence, list):
            return data

        normalized = []
        for index, item in enumerate(evidence, start=1):
            if isinstance(item, EvidenceItem):
                normalized.append(item)
                continue
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            normalized_item = dict(item)
            normalized_item.setdefault("section", section)
            normalized_item.setdefault("id", f"E{index}")
            if not normalized_item.get("url") and normalized_item.get("source_url"):
                normalized_item["url"] = normalized_item["source_url"]
            normalized.append(normalized_item)

        data["evidence"] = normalized
        return data

    @model_validator(mode="after")
    def validate_and_convert_evidence(self) -> Self:
        """Convert evidence dicts to EvidenceItem objects for validation."""
        common_sections = [s.value for s in get_common_sections()]
        logger = logging.getLogger(__name__)

        # Convert dicts to EvidenceItem objects for validation
        evidence_items = []
        for ev_dict in self.evidence:
            if isinstance(ev_dict, EvidenceItem):
                evidence_items.append(ev_dict)
            else:
                evidence_items.append(EvidenceItem(**ev_dict))

        # Validate non-empty evidence
        if self.section in common_sections and not evidence_items:
            logger.warning(
                f"CollectorResponse has no evidence items for section '{self.section}'."
            )
            raise ValueError(
                f"Evidence list cannot be empty for required section '{self.section}'"
            )
        if self.section in common_sections and len(evidence_items) < 3:
            logger.warning(
                f"CollectorResponse has {len(evidence_items)} evidence items for section '{self.section}'."
            )
            raise ValueError(
                f"Evidence list must include at least 3 items for required section '{self.section}'"
            )

        return self

    @property
    def evidence_items(self) -> list[EvidenceItem]:
        """Get evidence as EvidenceItem objects."""
        return [
            item if isinstance(item, EvidenceItem) else EvidenceItem(**item)
            for item in self.evidence
        ]
