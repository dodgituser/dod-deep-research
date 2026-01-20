"""Schemas for collector agent."""

import logging
import hashlib

from typing import Any, Annotated, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import WithJsonSchema

from dod_deep_research.agents.schemas import EvidenceSource, get_common_sections
from dod_deep_research.core import inline_json_schema


class EvidenceItem(BaseModel):
    """Evidence citation item."""

    id: str | None = Field(
        None,
        description=(
            "Short evidence ID; will be auto-generated from content hash if not provided."
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
    supported_questions: list[str] = Field(
        default_factory=list,
        description="Exact key questions this evidence supports.",
    )
    section: str = Field(
        ...,
        description="Section name this evidence supports (must match plan sections).",
    )

    @model_validator(mode="before")
    @classmethod
    def generate_id_and_normalize(cls, data: Any) -> Any:
        """Generate deterministic ID and normalize fields."""
        if not isinstance(data, dict):
            return data

        # Handle source_url alias
        if not data.get("url") and data.get("source_url"):
            data["url"] = data["source_url"]

        # Always generate ID from content hash for consistency
        url = data.get("url") or ""
        quote = data.get("quote") or ""
        content_sig = f"{url}|{quote}"
        data["id"] = hashlib.sha256(content_sig.encode()).hexdigest()[:8]

        return data

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
        if self.id and not self.id.startswith(f"{self.section}_"):
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
        if not isinstance(evidence, list):
            return data

        if not section:
            for item in evidence:
                if isinstance(item, dict) and item.get("section"):
                    section = item["section"]
                    data["section"] = section
                    break

        if not section:
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

        # Validate minimum evidence count
        if self.section in common_sections and len(evidence_items) < 2:
            logger.warning(
                f"CollectorResponse has {len(evidence_items)} evidence items for section '{self.section}'."
            )
            raise ValueError(
                "Evidence list must include at least 2 items for required section "
                f"'{self.section}'"
            )

        return self

    @property
    def evidence_items(self) -> list[EvidenceItem]:
        """Get evidence as EvidenceItem objects."""
        return [
            item if isinstance(item, EvidenceItem) else EvidenceItem(**item)
            for item in self.evidence
        ]
