"""Shared schema enums for agent outputs."""

from enum import StrEnum
from typing import Any

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


class EvidenceSource(StrEnum):
    """Allowed evidence source types for collection and planning."""

    PUBMED = "pubmed"
    CLINICALTRIALS = "clinicaltrials"
    WEB = "web"  # this uses Exa


class PreferredTool(StrEnum):
    """Allowed tool names for targeted retrieval."""

    PUBMED_SEARCH_ARTICLES = "pubmed_search_articles"
    CLINICALTRIALS_SEARCH_STUDIES = "clinicaltrials_search_studies"


class TaskPriority(StrEnum):
    """Allowed priority levels for retrieval tasks."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class KeyValuePair(BaseModel):
    """Key-value pair for dictionary-like structures."""

    key: str = Field(
        ...,
        description="Lookup key (e.g., section name, source URL, or hash string).",
    )
    value: Any = Field(
        ...,
        description=("Lookup value (usually a list of evidence IDs for that key)."),
    )
