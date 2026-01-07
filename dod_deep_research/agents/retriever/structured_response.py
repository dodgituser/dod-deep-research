"""Structured response schema for retriever agent."""

from pydantic import BaseModel, Field

from dod_deep_research.schemas import Evidence


class EvidenceListResponse(BaseModel):
    """Response containing a list of evidence."""

    evidence: list[Evidence] = Field(..., description="List of evidence citations")
