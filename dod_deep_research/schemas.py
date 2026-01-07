"""Pydantic schemas for CLI arguments and deep research output."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CliArgs(BaseModel):
    """CLI arguments."""

    prompt: str
    model: str
    output: Path | None = None
    disease: str | None = None
    drug_name: str | None = None
    drug_form: str | None = None
    drug_generic_name: str | None = None

    def to_prompt_kwargs(self) -> dict:
        """Convert prompt-related kwargs dict, excluding None values."""
        prompt_fields = ["disease", "drug_name", "drug_form", "drug_generic_name"]
        return {
            k: v
            for k, v in self.model_dump().items()
            if k in prompt_fields and v is not None
        }


class Metadata(BaseModel):
    """Metadata for the research output."""

    generated_at: datetime
    model: str


class Evidence(BaseModel):
    """Evidence citation."""

    id: str = Field(..., description="Evidence ID (e.g., 'E1', 'E2')")
    type: Literal["pubmed", "clinicaltrials", "guideline", "press_release", "other"]
    title: str
    url: str | None = None
    year: int | None = None
    quote: str | None = None


class Biomarker(BaseModel):
    """Biomarker information."""

    name: str
    role: Literal["diagnostic", "prognostic", "predictive", "monitoring", "other"]
    ontology_ids: list[str] = Field(default_factory=list)


class IndicationProfile(BaseModel):
    """Disease indication profile."""

    disease_name: str
    ontology_ids: list[str] = Field(default_factory=list)
    icd_10_codes: list[str] = Field(default_factory=list)
    patient_population_us: int | None = None
    key_biomarkers: list[Biomarker] = Field(default_factory=list)


class MechanisticRationale(BaseModel):
    """Mechanistic rationale for IL-2 therapy."""

    mechanism_name: str
    relevance_score: Literal["high", "medium", "low"]
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["established", "hypothetical", "contested"]
    confidence: float = Field(..., ge=0.0, le=1.0)


class CompetitiveLandscape(BaseModel):
    """Competitive landscape entry."""

    company_name: str
    drug_name: str
    mechanism: str
    stage: Literal[
        "preclinical",
        "phase_1",
        "phase_2",
        "phase_3",
        "approved",
        "discontinued",
    ]
    nct_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class IL2SpecificTrial(BaseModel):
    """IL-2 specific clinical trial."""

    nct_id: str
    trial_status: Literal[
        "recruiting",
        "active_not_recruiting",
        "completed",
        "terminated",
        "suspended",
        "withdrawn",
        "unknown",
    ]
    phase: Literal["phase_1", "phase_2", "phase_3", "phase_4", "not_applicable"]
    intervention_name: str
    dose: str | None = None
    route: Literal["iv", "sc", "im", "oral", "topical", "other"]
    design: str | None = None
    enrollment: int | None = None
    sponsor: str | None = None
    primary_outcome_met: Literal["yes", "no", "pending", "unknown"]
    evidence_ids: list[str] = Field(default_factory=list)


class DeepResearchOutput(BaseModel):
    """Root model for deep research structured output."""

    metadata: Metadata
    indication_profile: IndicationProfile
    evidence: list[Evidence] = Field(default_factory=list)
    mechanistic_rationales: list[MechanisticRationale] = Field(default_factory=list)
    competitive_landscape: list[CompetitiveLandscape] = Field(default_factory=list)
    il2_specific_trials: list[IL2SpecificTrial] = Field(default_factory=list)
