"""Evidence store models and aggregation utilities."""

import hashlib
import logging
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from dod_deep_research.agents.collector.schemas import CollectorResponse, EvidenceItem
from dod_deep_research.agents.schemas import KeyValuePair
from dod_deep_research.agents.writer.schemas import MarkdownReport

logger = logging.getLogger(__name__)


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


def extract_section_stores(state: dict[str, Any]) -> dict[str, CollectorResponse]:
    """
    Extract all evidence_store_section_* keys from state and convert to CollectorResponse.

    Args:
        state: Dictionary containing state keys.

    Returns:
        dict[str, CollectorResponse]: Mapping of section names to CollectorResponse objects.
    """
    section_stores: dict[str, CollectorResponse] = {}
    for key, value in state.items():
        if key.startswith("evidence_store_section_"):
            section_name = key.replace("evidence_store_section_", "")
            try:
                if isinstance(value, dict):
                    section_stores[section_name] = CollectorResponse(**value)
                else:
                    section_stores[section_name] = value
            except Exception as e:
                logger.warning(
                    f"Failed to parse CollectorResponse for section '{section_name}': {e}"
                )
    return section_stores


def aggregate_evidence(section_stores: dict[str, CollectorResponse]) -> EvidenceStore:
    """
    Deterministically merge evidence from parallel collectors into a single evidence store.

    This function performs the following operations:
    1. Filters out low-quality evidence (missing required URLs or quotes)
    2. Merges all evidence items from all section stores into a single list
    3. Deduplicates evidence using content hashing (title + url + quote)
    4. Builds indexes for efficient lookup:
       - by_section: Groups evidence IDs by section name
       - by_source: Groups evidence IDs by source URL
       - hash_index: Maps content hash to evidence ID for deduplication

    Args:
        section_stores: Dictionary mapping section names to CollectorResponse objects.
            Each CollectorResponse contains evidence items for that section.

    Returns:
        EvidenceStore: Aggregated evidence store with deduplicated items and indexes.

    Deduplication Logic:
        Content hash is computed as SHA256 of "{title}|{url or ''}|{quote}".
        If multiple items have the same hash, only the first occurrence is kept
        (preserving order from collectors). Evidence IDs are preserved as-is since
        they're already prefixed with section names.
    """
    if not section_stores:
        logger.warning("No section stores provided for aggregation")
        return EvidenceStore(items=[], by_section=[], by_source=[], hash_index=[])

    logger.info(f"Aggregating evidence from {len(section_stores)} sections")

    all_items: list[EvidenceItem] = []
    seen_hashes: dict[str, str] = {}  # hash -> evidence_id
    item_hashes: dict[str, str] = {}  # evidence_id -> hash
    filtered_count = 0
    duplicate_count = 0
    total_items = 0

    def is_valid_evidence(item: EvidenceItem) -> bool:
        """Check if an evidence item meets minimum quality requirements."""
        if not item.url or not item.url.strip():
            return False
        if not item.quote or not item.quote.strip():
            return False
        return True

    # Merge all evidence items and deduplicate
    for _, collector_response in section_stores.items():
        for item in collector_response.evidence_items:
            total_items += 1
            if not is_valid_evidence(item):
                filtered_count += 1
                continue
            # Compute content hash for deduplication
            content_str = f"{item.title}|{item.url or ''}|{item.quote}"
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()

            # Keep first occurrence if duplicate
            if content_hash not in seen_hashes:
                seen_hashes[content_hash] = item.id
                item_hashes[item.id] = content_hash
                all_items.append(item)
            else:
                duplicate_count += 1

    # Build indexes
    by_section: dict[str, list[str]] = {}
    by_source: dict[str | None, list[str]] = {}
    hash_index: dict[str, str] = {}

    for item in all_items:
        # by_section index
        if item.section not in by_section:
            by_section[item.section] = []
        by_section[item.section].append(item.id)

        # by_source index
        if item.url not in by_source:
            by_source[item.url] = []
        by_source[item.url].append(item.id)

        # hash_index (use precomputed hash)
        hash_index[item_hashes[item.id]] = item.id

    # Convert dictionaries to KeyValuePair lists
    by_section_kvp = [KeyValuePair(key=k, value=v) for k, v in by_section.items()]
    by_source_kvp = [KeyValuePair(key=k or "", value=v) for k, v in by_source.items()]
    hash_index_kvp = [KeyValuePair(key=k, value=v) for k, v in hash_index.items()]

    logger.info(
        f"Evidence aggregation complete: {len(all_items)} items retained "
        f"(filtered {filtered_count}, duplicates removed {duplicate_count} out of {total_items} total)"
    )

    return EvidenceStore(
        items=all_items,
        by_section=by_section_kvp,
        by_source=by_source_kvp,
        hash_index=hash_index_kvp,
    )


class DeepResearchOutput(MarkdownReport):
    """Root model for deep research markdown output with evidence."""

    evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description=(
            "All evidence items referenced in the output. This field is automatically "
            "populated from evidence_store.items after generation."
        ),
    )

    def to_evidence_table(self) -> list[dict[str, Any]]:
        """
        Generate evidence table specification.

        Returns:
            list[dict]: List of evidence entries formatted for table display.
        """
        return [
            {
                "id": ev.id,
                "source": ev.source,
                "title": ev.title,
                "url": ev.url,
                "year": ev.year,
                "quote": ev.quote,
                "tags": ev.tags,
                "section": ev.section,
            }
            for ev in self.evidence
        ]
