"""Shared schema enums for agent outputs."""

from enum import StrEnum


class EvidenceSource(StrEnum):
    """Allowed evidence source types for collection and planning."""

    GOOGLE = "google"
    PUBMED = "pubmed"
    CLINICALTRIALS = "clinicaltrials"
    GUIDELINE = "guideline"
    PRESS_RELEASE = "press_release"
    OTHER = "other"


class PreferredTool(StrEnum):
    """Allowed tool names for targeted retrieval."""

    PUBMED_SEARCH_ARTICLES = "pubmed_search_articles"
    CLINICALTRIALS_SEARCH_STUDIES = "clinicaltrials_search_studies"
    GOOGLE_SEARCH = "google_search"


class TaskPriority(StrEnum):
    """Allowed priority levels for retrieval tasks."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
