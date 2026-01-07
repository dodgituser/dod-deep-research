"""Structured response schema for planner agent."""

from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """Research plan output from planner agent."""

    disease: str = Field(..., description="The disease/indication name")
    research_areas: list[str] = Field(
        ...,
        description="List of research areas to investigate (e.g., ['epidemiology', 'biomarkers', 'mechanisms', 'trials'])",
    )
    key_questions: list[str] = Field(
        ..., description="List of specific research questions to answer"
    )
    scope: str = Field(
        ..., description="Description of the research scope and boundaries"
    )
