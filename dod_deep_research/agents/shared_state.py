"""Shared state contract for sequential agent pipeline."""

from pydantic import BaseModel, Field

from dod_deep_research.agents.planner.structured_response import ResearchPlan
from dod_deep_research.agents.retriever.structured_response import EvidenceListResponse
from dod_deep_research.agents.validator.structured_response import ValidationReport
from dod_deep_research.schemas import DeepResearchOutput


class SharedState(BaseModel):
    """
    Shared state contract for sequential agent pipeline.

    Documents the state keys used for passing data between agents:
    - research_plan (ResearchPlan): Planner → Retriever
    - evidence_list (EvidenceListResponse): Retriever → Validator
    - validation_report (ValidationReport): Validator → Writer
    - deep_research_output (DeepResearchOutput): Writer → Final
    """

    research_plan: ResearchPlan | None = Field(
        default=None,
        description="ResearchPlan model: Structured plan with disease, research areas, key questions (Planner output)",
    )
    evidence_list: EvidenceListResponse | None = Field(
        default=None,
        description="EvidenceListResponse model: List of Evidence objects (Retriever output)",
    )
    validation_report: ValidationReport | None = Field(
        default=None,
        description="ValidationReport model: Schema validation results, missing fields, errors (Validator output)",
    )
    deep_research_output: DeepResearchOutput | None = Field(
        default=None,
        description="DeepResearchOutput model: Complete structured research output (Writer output)",
    )
