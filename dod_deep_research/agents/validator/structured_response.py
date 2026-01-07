"""Structured response schema for validator agent."""

from pydantic import BaseModel, Field


class ValidationReport(BaseModel):
    """Schema validation report."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
