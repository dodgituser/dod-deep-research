"""Schemas for writer agent."""

from pydantic import BaseModel, Field


class MarkdownReport(BaseModel):
    """Writer agent output schema (without evidence field)."""

    report_markdown: str = Field(
        ...,
        description="Full deep research report in markdown format.",
    )


class SectionDraft(BaseModel):
    """Section writer output schema for long-form reports."""

    section_markdown: str = Field(
        ...,
        description="Markdown for a single report section.",
    )
