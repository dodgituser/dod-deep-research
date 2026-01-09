"""Schemas for validator agent."""

from pydantic import BaseModel, Field


class ValidationReport(BaseModel):
    """Schema validation report."""

    is_valid: bool = Field(
        ...,
        description="Whether the evidence store is sufficient to build the output schema.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Hard failures that should block downstream writing.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Required fields or sections that are missing.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Quality warnings that do not block output generation.",
    )
