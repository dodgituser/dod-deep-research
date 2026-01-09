"""Schemas for writer agent."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from dod_deep_research.agents.aggregator.schemas import KeyValuePair


class Metadata(BaseModel):
    """Metadata for the research output."""

    generated_at: datetime = Field(
        ...,
        description="ISO timestamp for when the output was generated.",
    )
    model: str = Field(
        ...,
        description="Model or agent name that generated the output.",
    )

    @field_serializer("generated_at")
    def serialize_datetime(self, value: datetime, _info) -> str:
        """Serialize datetime to ISO format string."""
        return value.isoformat()


class Biomarker(BaseModel):
    """Biomarker information."""

    name: str = Field(..., description="Biomarker name.")
    role: Literal["diagnostic", "prognostic", "predictive", "monitoring", "other"] = (
        Field(
            ...,
            description="Clinical role of the biomarker.",
        )
    )
    ontology_ids: list[str] = Field(
        default_factory=list,
        description="Ontology identifiers for the biomarker, if known.",
    )


class IndicationProfile(BaseModel):
    """Disease indication profile."""

    disease_name: str = Field(..., description="Disease/indication name.")
    ontology_ids: list[str] = Field(
        default_factory=list,
        description="Ontology identifiers for the disease, if known.",
    )
    icd_10_codes: list[str] = Field(
        default_factory=list,
        description="Relevant ICD-10 codes for the indication.",
    )
    patient_population_us: int | None = Field(
        None,
        description="Estimated US patient population size, if known.",
    )
    key_biomarkers: list[Biomarker] = Field(
        default_factory=list,
        description="Key biomarkers relevant to the indication.",
    )


class MechanisticRationale(BaseModel):
    """Mechanistic rationale for the drug therapy."""

    mechanism_name: str = Field(
        ...,
        description="Short name for the mechanism (e.g., 'Treg modulation').",
    )
    relevance_score: Literal["high", "medium", "low"] = Field(
        ...,
        description="How relevant the mechanism is to the drug in this indication.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs that support this mechanism.",
    )
    status: Literal["established", "hypothetical", "contested"] = Field(
        ...,
        description="Maturity of the mechanism based on evidence.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for the mechanism (0-1).",
    )


class CompetitiveLandscape(BaseModel):
    """Competitive landscape entry."""

    company_name: str = Field(..., description="Company developing the competitor.")
    drug_name: str = Field(..., description="Competitor drug name.")
    mechanism: str = Field(..., description="Mechanism of action.")
    stage: Literal[
        "preclinical",
        "phase_1",
        "phase_2",
        "phase_3",
        "approved",
        "discontinued",
    ] = Field(..., description="Development stage of the competitor.")
    nct_ids: list[str] = Field(
        default_factory=list,
        description="Related clinical trial identifiers.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting this entry.",
    )


class DrugSpecificTrial(BaseModel):
    """Drug-specific clinical trial."""

    nct_id: str = Field(..., description="ClinicalTrials.gov identifier.")
    trial_status: Literal[
        "recruiting",
        "active_not_recruiting",
        "completed",
        "terminated",
        "suspended",
        "withdrawn",
        "unknown",
    ] = Field(..., description="Recruitment/overall status of the trial.")
    phase: Literal["phase_1", "phase_2", "phase_3", "phase_4", "not_applicable"] = (
        Field(
            ...,
            description="Trial phase.",
        )
    )
    intervention_name: str = Field(
        ...,
        description="Primary drug intervention name.",
    )
    dose: str | None = Field(
        None,
        description="Dose information if available.",
    )
    route: Literal["iv", "sc", "im", "oral", "topical", "other"] = Field(
        ...,
        description="Route of administration.",
    )
    design: str | None = Field(
        None,
        description="Brief study design details.",
    )
    enrollment: int | None = Field(
        None,
        description="Planned or actual enrollment count.",
    )
    sponsor: str | None = Field(
        None,
        description="Trial sponsor.",
    )
    primary_outcome_met: Literal["yes", "no", "pending", "unknown"] = Field(
        ...,
        description="Whether primary outcome was met, if known.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting this trial entry.",
    )


class WriterOutput(BaseModel):
    """Writer agent output schema (without evidence field)."""

    metadata: Metadata = Field(
        ...,
        description="Run metadata for the generated output.",
    )
    indication_profile: IndicationProfile = Field(
        ...,
        description="High-level disease overview and biomarkers.",
    )
    mechanistic_rationales: list[MechanisticRationale] = Field(
        default_factory=list,
        description="Mechanistic rationales grounded in evidence.",
    )
    competitive_landscape: list[CompetitiveLandscape] = Field(
        default_factory=list,
        description="Competitor entries relevant to the drug in this indication.",
    )
    drug_specific_trials: list[DrugSpecificTrial] = Field(
        default_factory=list,
        description="Drug-specific trials relevant to this indication.",
    )
    provenance: list[KeyValuePair] = Field(
        default_factory=list,
        description="Audit trail or provenance notes as key-value pairs.",
    )
