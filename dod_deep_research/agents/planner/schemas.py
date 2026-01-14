"""Schemas for planner agent."""

from pydantic import BaseModel, Field

from dod_deep_research.agents.schemas import CommonSection


class ResearchSection(BaseModel):
    """Research section definition."""

    name: CommonSection = Field(
        ...,
        description=("Exact section name from the predefined section list."),
    )
    description: str = Field(
        ...,
        description="What this section should cover for the specific indication.",
    )
    key_questions: list[str] = Field(
        ...,
        description="Section-specific research questions to answer.",
    )
    scope: str = Field(
        ...,
        description="What to include and exclude in this section.",
    )


class ResearchPlan(BaseModel):
    """Research plan output from planner agent."""

    disease: str = Field(
        ...,
        description="Disease/indication name extracted from the input prompt.",
    )
    research_areas: list[CommonSection] = Field(
        ...,
        description="List of research areas to investigate (e.g., ['rationale_executive_summary', 'disease_overview', 'therapeutic_landscape', 'clinical_trials_analysis'])",
    )
    sections: list[ResearchSection] = Field(
        ...,
        description="One ResearchSection per predefined section name.",
    )
