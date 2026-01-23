"""Schemas for research head agent."""

from typing import Literal

from pydantic import BaseModel, Field

from dod_deep_research.agents.schemas import CommonSection


class GapTask(BaseModel):
    """Question-level gap task for targeted collection."""

    section: CommonSection = Field(
        ...,
        description="Section that contains missing questions.",
    )
    missing_questions: list[str] = Field(
        default_factory=list,
        description="Missing research questions to address.",
    )
    min_evidence: int = Field(
        description="Minimum evidence required per question.",
    )


class ResearchHeadGuidance(BaseModel):
    """Guidance for targeted collection in a section."""

    section: CommonSection = Field(
        ...,
        description="Section name to guide targeted collection.",
    )
    gap_type: Literal["quantitative", "qualitative"] = Field(
        default="quantitative",
        description="Whether this guidance targets a quantitative or qualitative gap.",
    )
    missing_questions: list[str] = Field(
        ...,
        min_length=1,
        description="Missing research questions to address for this section.",
    )
    notes: str = Field(
        ...,
        min_length=1,
        description="Short guidance on what to look for in this section.",
    )
    suggested_queries: list[str] = Field(
        ...,
        min_length=1,
        description="Suggested search queries for targeted collection.",
    )


class ResearchHeadPlan(BaseModel):
    """Research Head output plan with guidance only."""

    guidance: list[ResearchHeadGuidance] = Field(
        default_factory=list,
        description="Guidance for targeted collection by section.",
    )
