"""Schemas for research head agent."""

from pydantic import BaseModel, Field, model_validator

from dod_deep_research.agents.planner.schemas import CommonSection
from typing import Self


class ResearchGap(BaseModel):
    """Identified gap in evidence coverage for a section."""

    section: CommonSection = Field(
        ...,
        description="Section name with identified gaps.",
    )
    missing_questions: list[str] = Field(
        default_factory=list,
        description="Key questions from the research plan that are not yet answered.",
    )
    notes: str = Field(
        default="",
        description="Additional context about the gap and why it matters.",
    )


class ResearchHeadPlan(BaseModel):
    """Research Head output plan with gaps only."""

    continue_research: bool = Field(
        ...,
        description="Whether to continue with targeted collection. Set to False when gaps are resolved.",
    )
    gaps: list[ResearchGap] = Field(
        default_factory=list,
        description="List of identified gaps in evidence coverage.",
    )

    @model_validator(mode="after")
    def _ensure_continue_research(self) -> Self:
        """
        Ensures continue_research is true when gaps are present.

        Returns:
            ResearchHeadPlan: Updated model instance.
        """
        if self.gaps:
            self.continue_research = True
        return self
