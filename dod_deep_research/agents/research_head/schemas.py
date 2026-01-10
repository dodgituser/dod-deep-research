"""Schemas for research head agent."""

from pydantic import BaseModel, Field

from dod_deep_research.agents.planner.schemas import CommonSection
from dod_deep_research.agents.schemas import EvidenceSource, PreferredTool, TaskPriority


class ResearchGap(BaseModel):
    """Identified gap in evidence coverage for a section."""

    section: CommonSection = Field(
        ...,
        description="Section name with identified gaps.",
    )
    missing_evidence_types: list[EvidenceSource] = Field(
        default_factory=list,
        description="Required evidence types not yet collected (e.g., ['pubmed', 'clinicaltrials']).",
    )
    missing_questions: list[str] = Field(
        default_factory=list,
        description="Key questions from the research plan that are not yet answered.",
    )
    notes: str = Field(
        default="",
        description="Additional context about the gap and why it matters.",
    )


class RetrievalTask(BaseModel):
    """Targeted retrieval task to fill evidence gaps."""

    section: CommonSection = Field(
        ...,
        description="Target section for this retrieval task.",
    )
    evidence_type: EvidenceSource = Field(
        ...,
        description="Preferred evidence type (pubmed, clinicaltrials, google, guideline, press_release, other).",
    )
    query: str = Field(
        ...,
        description="Search query string for this task.",
    )
    preferred_tool: PreferredTool = Field(
        ...,
        description="Tool to use (pubmed_search_articles, clinicaltrials_search_studies, google_search).",
    )
    priority: TaskPriority = Field(
        ...,
        description="Priority level: high, medium, or low.",
    )


class ResearchHeadPlan(BaseModel):
    """Research Head output plan with gaps and retrieval tasks."""

    continue_research: bool = Field(
        ...,
        description="Whether to continue with targeted collection. Set to False when gaps are resolved.",
    )
    gaps: list[ResearchGap] = Field(
        default_factory=list,
        description="List of identified gaps in evidence coverage.",
    )
    tasks: list[RetrievalTask] = Field(
        default_factory=list,
        description="Prioritized retrieval tasks to fill identified gaps.",
    )
