"""Schemas for writer agent."""

from datetime import datetime

from pydantic import BaseModel, Field, field_serializer


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
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return value.isoformat()


class MarkdownReport(BaseModel):
    """Writer agent output schema (without evidence field)."""

    metadata: Metadata = Field(
        ...,
        description="Run metadata for the generated output.",
    )
    report_markdown: str = Field(
        ...,
        description="Full deep research report in markdown format.",
    )
