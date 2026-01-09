"""Schemas for aggregator agent."""

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from dod_deep_research.agents.collector.schemas import EvidenceItem


class KeyValuePair(BaseModel):
    """Key-value pair for dictionary-like structures."""

    key: str = Field(
        ...,
        description="Lookup key (e.g., section name, source URL, or hash string).",
    )
    value: Any = Field(
        ...,
        description=("Lookup value (usually a list of evidence IDs for that key)."),
    )


class EvidenceStore(BaseModel):
    """Centralized evidence store with indexing and deduplication."""

    items: list[EvidenceItem] = Field(
        default_factory=list,
        description="All unique evidence items after merging and deduplication.",
    )
    by_section: list[KeyValuePair] = Field(
        default_factory=list,
        description=(
            "Section name → list of evidence IDs (encoded as KeyValuePair list)."
        ),
    )
    by_source: list[KeyValuePair] = Field(
        default_factory=list,
        description=(
            "Source URL → list of evidence IDs (encoded as KeyValuePair list)."
        ),
    )
    hash_index: list[KeyValuePair] = Field(
        default_factory=list,
        description=(
            "Content hash → evidence ID (for deduplication, encoded as KeyValuePair list)."
        ),
    )

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        """Validate that all evidence IDs are unique across the store."""
        ids = [item.id for item in self.items]
        duplicates = [id for id in ids if ids.count(id) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate evidence IDs found: {set(duplicates)}. "
                "All evidence IDs must be unique across the EvidenceStore."
            )
        return self
