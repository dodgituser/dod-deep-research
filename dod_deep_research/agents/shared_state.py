"""Shared state contract for map-reduce agent pipeline."""

from pydantic import BaseModel, Field

from dod_deep_research.utils.evidence import EvidenceStore
from dod_deep_research.agents.writer.schemas import MarkdownReport
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan


class SharedState(BaseModel):
    """
    Shared state contract for map-reduce agent pipeline.

    Documents the state keys used for passing data between agents:
    - drug_name (str): Drug name being researched (available to all agents)
    - disease_name (str): Disease/indication name being researched (available to all agents)
    - research_plan (ResearchPlan): Meta-planner → Collectors
    - evidence_store_section_* (CollectorResponse): Collectors → Deterministic aggregation function
    - evidence_store (EvidenceStore): Aggregation function → ResearchHead/Writer
    - research_head_plan (ResearchHeadPlan): ResearchHead → Targeted Collectors
    - deep_research_output (MarkdownReport): Writer → Final
    """

    drug_name: str | None = Field(
        default=None,
        description="Drug name being researched (e.g., 'IL-2', 'Aspirin'). Available to all agents.",
    )
    disease_name: str | None = Field(
        default=None,
        description="Disease/indication name being researched (e.g., 'ALS', 'SLE', 'cancer'). Available to all agents.",
    )
    research_plan: ResearchPlan | None = Field(
        default=None,
        description="ResearchPlan model: Structured plan with disease, research_areas and sections (each section has name, description, key_questions, scope) (Meta-planner output)",
    )
    evidence_store: EvidenceStore | None = Field(
        default=None,
        description="EvidenceStore model: Centralized evidence store with indexing and deduplication (Aggregation function output)",
    )
    research_head_plan: ResearchHeadPlan | None = Field(
        default=None,
        description="ResearchHeadPlan model: Gap analysis and targeted retrieval tasks (ResearchHead output)",
    )
    deep_research_output: MarkdownReport | None = Field(
        default=None,
        description="MarkdownReport model: Complete markdown research output (Writer output)",
    )
