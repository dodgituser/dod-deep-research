"""Structured response schema for collector agent."""

from pydantic import BaseModel, Field

from dod_deep_research.schemas import EvidenceItem


class CollectorResponse(BaseModel):
    """Response containing evidence items for a specific section."""

    section: str = Field(..., description="Section name this evidence belongs to")
    evidence: list[EvidenceItem] = Field(
        ..., description="List of evidence items for this section"
    )
