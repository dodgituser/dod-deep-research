"""Shared state contract for map-reduce agent pipeline."""

import hashlib

from pydantic import BaseModel, Field

from dod_deep_research.agents.aggregator.schemas import EvidenceStore, KeyValuePair
from dod_deep_research.agents.collector.schemas import CollectorResponse
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.validator.schemas import ValidationReport
from dod_deep_research.agents.writer.schemas import DeepResearchOutput


def aggregate_evidence(section_stores: dict[str, CollectorResponse]) -> EvidenceStore:
    """
    Deterministically merge evidence from parallel collectors into a single evidence store.

    This function performs the following operations:
    1. Merges all evidence items from all section stores into a single list
    2. Deduplicates evidence using content hashing (title + url + quote)
    3. Builds indexes for efficient lookup:
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
    all_items = []
    seen_hashes: dict[str, str] = {}  # hash -> evidence_id
    item_hashes: dict[str, str] = {}  # evidence_id -> hash

    # Merge all evidence items and deduplicate
    for section_name, collector_response in section_stores.items():
        for item in collector_response.evidence:
            # Compute content hash for deduplication
            content_str = f"{item.title}|{item.url or ''}|{item.quote}"
            content_hash = hashlib.sha256(content_str.encode()).hexdigest()

            # Keep first occurrence if duplicate
            if content_hash not in seen_hashes:
                seen_hashes[content_hash] = item.id
                item_hashes[item.id] = content_hash
                all_items.append(item)

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

    return EvidenceStore(
        items=all_items,
        by_section=by_section_kvp,
        by_source=by_source_kvp,
        hash_index=hash_index_kvp,
    )


class SharedState(BaseModel):
    """
    Shared state contract for map-reduce agent pipeline.

    Documents the state keys used for passing data between agents:
    - research_plan (ResearchPlan): Meta-planner → Collectors
    - evidence_store_section_* (CollectorResponse): Collectors → Deterministic aggregation function
    - evidence_store (EvidenceStore): Aggregation function → Validator → Writer
    - validation_report (ValidationReport): Validator → Writer
    - deep_research_output (DeepResearchOutput): Writer → Final
    """

    research_plan: ResearchPlan | None = Field(
        default=None,
        description="ResearchPlan model: Structured plan with disease, research_areas and sections (each section has name, description, required_evidence_types, key_questions, scope) (Meta-planner output)",
    )
    evidence_store: EvidenceStore | None = Field(
        default=None,
        description="EvidenceStore model: Centralized evidence store with indexing and deduplication (Aggregation function output)",
    )
    validation_report: ValidationReport | None = Field(
        default=None,
        description="ValidationReport model: Schema validation results, missing fields, errors (Validator output)",
    )
    deep_research_output: DeepResearchOutput | None = Field(
        default=None,
        description="DeepResearchOutput model: Complete structured research output (Writer output)",
    )
