"""Structured response schema for planner agent."""

from pydantic import BaseModel, Field


class ResearchSection(BaseModel):
    """Research section definition."""

    name: str = Field(
        ..., description="Section name (e.g., 'epidemiology', 'biomarkers')"
    )
    description: str = Field(..., description="Section description")
    required_evidence_types: list[str] = Field(
        ...,
        description="List of required evidence types (e.g., ['pubmed', 'clinicaltrials'])",
    )
    key_questions: list[str] = Field(
        ..., description="Section-specific research questions"
    )


class ResearchPlan(BaseModel):
    """Research plan output from planner agent."""

    disease: str = Field(..., description="The disease/indication name")
    research_areas: list[str] = Field(
        ...,
        description="List of research areas to investigate (e.g., ['epidemiology', 'biomarkers', 'mechanisms', 'trials'])",
    )
    sections: list[ResearchSection] = Field(
        ...,
        description="Structured research sections with evidence requirements",
    )
    key_questions: list[str] = Field(
        ..., description="List of specific research questions to answer"
    )
    scope: str = Field(
        ..., description="Description of the research scope and boundaries"
    )
