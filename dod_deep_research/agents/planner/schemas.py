"""Schemas for planner agent."""

from enum import StrEnum

from pydantic import BaseModel, Field


class CommonSection(StrEnum):
    """Common research sections for evidence collection."""

    RATIONALE_EXECUTIVE_SUMMARY = "rationale_executive_summary"
    DISEASE_OVERVIEW = "disease_overview"
    THERAPEUTIC_LANDSCAPE = "therapeutic_landscape"
    CURRENT_TREATMENT_GUIDELINES = "current_treatment_guidelines"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    CLINICAL_TRIALS_ANALYSIS = "clinical_trials_analysis"
    MARKET_OPPORTUNITY_ANALYSIS = "market_opportunity_analysis"


def get_common_sections() -> list[CommonSection]:
    """Get all common sections."""
    return list(CommonSection)


class ResearchSection(BaseModel):
    """Research section definition."""

    name: str = Field(
        ...,
        description=("Exact section name from the predefined section list."),
    )
    description: str = Field(
        ...,
        description="What this section should cover for the specific indication.",
    )
    required_evidence_types: list[str] = Field(
        ...,
        description="List of required evidence types (e.g., ['pubmed', 'clinicaltrials'])",
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
    research_areas: list[str] = Field(
        ...,
        description="List of research areas to investigate (e.g., ['rationale_executive_summary', 'disease_overview', 'therapeutic_landscape', 'clinical_trials_analysis'])",
    )
    sections: list[ResearchSection] = Field(
        ...,
        description="One ResearchSection per predefined section name.",
    )
