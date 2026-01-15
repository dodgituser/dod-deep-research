"""Schemas for research head agent."""

from pydantic import BaseModel, Field

from dod_deep_research.agents.schemas import CommonSection


class ResearchHeadGuidance(BaseModel):
    """Guidance for targeted collection in a section."""

    section: CommonSection = Field(
        ...,
        description="Section name to guide targeted collection.",
    )
    notes: str = Field(
        default="",
        description="Short guidance on what to look for in this section.",
    )
    suggested_queries: list[str] = Field(
        default_factory=list,
        description="Suggested search queries for targeted collection.",
    )  # TODO how will the research head know how to suggest queries?


class ResearchHeadPlan(BaseModel):
    """Research Head output plan with guidance only."""

    guidance: list[ResearchHeadGuidance] = Field(
        default_factory=list,
        description="Guidance for targeted collection by section.",
    )
