"""Shared state contract for map-reduce agent pipeline."""

from pydantic import BaseModel, Field

from dod_deep_research.agents.planner.structured_response import ResearchPlan
from dod_deep_research.agents.validator.structured_response import ValidationReport
from dod_deep_research.schemas import DeepResearchOutput, EvidenceStore


class SharedState(BaseModel):
    """
    Shared state contract for map-reduce agent pipeline.

    Documents the state keys used for passing data between agents:
    - research_plan (ResearchPlan): Meta-planner → Collectors
    - evidence_store_section_* (CollectorResponse): Collectors → Aggregator
    - evidence_store (EvidenceStore): Aggregator → Validator → Writer
    - validation_report (ValidationReport): Validator → Writer
    - deep_research_output (DeepResearchOutput): Writer → Final
    """

    research_plan: ResearchPlan | None = Field(
        default=None,
        description="ResearchPlan model: Structured plan with disease, sections, key questions (Meta-planner output)",
    )
    evidence_store: EvidenceStore | None = Field(
        default=None,
        description="EvidenceStore model: Centralized evidence store with indexing and deduplication (Aggregator output)",
    )
    validation_report: ValidationReport | None = Field(
        default=None,
        description="ValidationReport model: Schema validation results, missing fields, errors, gaps (Validator output)",
    )
    deep_research_output: DeepResearchOutput | None = Field(
        default=None,
        description="DeepResearchOutput model: Complete structured research output (Writer output)",
    )
