"""Evidence store models and aggregation utilities."""

import hashlib
import json
import logging
from collections import defaultdict
from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from dod_deep_research.agents.collector.schemas import CollectorResponse, EvidenceItem
from dod_deep_research.agents.schemas import CommonSection, EvidenceSource, KeyValuePair
from dod_deep_research.agents.research_head.schemas import GapTask
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.core import extract_json_payload

# Section-specific minimum evidence targets. Tuned to push deeper
SECTION_MIN_EVIDENCE: dict[CommonSection, int] = {
    CommonSection.RATIONALE_EXECUTIVE_SUMMARY: 5,
    CommonSection.DISEASE_OVERVIEW: 5,
    CommonSection.THERAPEUTIC_LANDSCAPE: 6,
    CommonSection.CURRENT_TREATMENT_GUIDELINES: 4,
    CommonSection.COMPETITOR_ANALYSIS: 6,
    CommonSection.CLINICAL_TRIALS_ANALYSIS: 7,
    CommonSection.MARKET_OPPORTUNITY_ANALYSIS: 6,
}

DEFAULT_MIN_EVIDENCE = 2


def get_min_evidence(section_name: str) -> int:
    """
    Look up the minimum evidence target for a section.

    Args:
        section_name (str): Section name (CommonSection value as string).

    Returns:
        int: Minimum evidence items required.
    """
    try:
        section_enum = CommonSection(section_name)
    except ValueError:
        return DEFAULT_MIN_EVIDENCE
    return SECTION_MIN_EVIDENCE.get(section_enum, DEFAULT_MIN_EVIDENCE)


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
                payload = value
                if isinstance(payload, str):
                    payload = json.loads(extract_json_payload(payload))
                if isinstance(payload, dict) and section_name in payload:
                    payload = payload[section_name]
                if isinstance(payload, dict) and key in payload:
                    payload = payload[key]
                if isinstance(payload, list):
                    payload = {"section": section_name, "evidence": payload}
                if isinstance(payload, dict) and "evidence" in payload:
                    payload.setdefault("section", section_name)
                if isinstance(payload, dict):
                    section_stores[section_name] = CollectorResponse(**payload)
                elif isinstance(payload, CollectorResponse):
                    section_stores[section_name] = payload
            except Exception as e:
                logger.warning(
                    f"Failed to parse CollectorResponse for section '{section_name}': {e} with payload: {payload}"
                )
    return section_stores


def construct_missing_url(item: EvidenceItem) -> str | None:
    """
    Attempt to construct a missing URL based on the source and ID.

    Args:
        item: The evidence item with missing URL.

    Returns:
        str | None: Constructed URL or None if not possible.
    """
    if not item.id:
        return None

    # Handle PubMed
    # IDs usually look like "E1", "E2" or direct PMIDs.
    # If the ID is numeric (PMID), we can build it.
    if item.source == EvidenceSource.PUBMED and item.id.isdigit():
        return f"https://pubmed.ncbi.nlm.nih.gov/{item.id}/"

    # Handle ClinicalTrials.gov
    # IDs should be NCT numbers (e.g. NCT01234567)
    if item.source == EvidenceSource.CLINICALTRIALS and item.id.upper().startswith(
        "NCT"
    ):
        return f"https://clinicaltrials.gov/study/{item.id}"

    return None


def aggregate_evidence(
    section_stores: dict[str, CollectorResponse],
    existing_store: EvidenceStore | None = None,
) -> EvidenceStore:
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
    if not section_stores and not existing_store:
        logger.warning("No section stores provided for aggregation")
        return EvidenceStore(items=[], by_section=[], by_source=[], hash_index=[])

    all_items: list[EvidenceItem] = []
    seen_hashes: dict[str, str] = {}  # hash -> evidence_id
    item_hashes: dict[str, str] = {}  # evidence_id -> hash
    filtered_count = 0
    duplicate_count = 0
    total_items = 0

    def is_valid_evidence(item: EvidenceItem) -> tuple[bool, str]:
        """Check if an evidence item meets minimum quality requirements."""
        if not item.url or not item.url.strip():
            return False, "Missing URL (could not be reconstructed)"

        if not item.quote or not item.quote.strip():
            if not item.title:
                return False, "Missing both quote and title"
            return False, "Missing quote"

        return True, ""

    # Merge all evidence items (existing store + current section stores) and deduplicate
    merged_items: list[EvidenceItem] = []
    if existing_store:
        merged_items.extend(existing_store.items)
    for _section_name, collector_response in section_stores.items():
        merged_items.extend(collector_response.evidence_items)

    for item in merged_items:
        total_items += 1

        # 1. Attempt to fix missing URL before validation
        if not item.url:
            fixed_url = construct_missing_url(item)
            if fixed_url:
                item.url = fixed_url

        # 2. Validate
        is_valid, reason = is_valid_evidence(item)
        if not is_valid:
            logger.warning(f"Dropping evidence {item.id} from {item.section}: {reason}")
            filtered_count += 1
            continue

        # Compute content hash for deduplication
        content_str = f"{item.section}|{item.title}|{item.url or ''}|{item.quote}"
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


def build_section_evidence(
    evidence_store: EvidenceStore,
    section_name: str,
) -> list[dict[str, Any]]:
    """
    Build a list of evidence items for a specific section.

    Args:
        evidence_store (EvidenceStore): Aggregated evidence store.
        section_name (str): Section name to filter evidence.

    Returns:
        list[dict[str, Any]]: Serialized evidence items for the section.
    """
    return [
        item.model_dump()
        for item in evidence_store.items
        if item.section == section_name
    ]


def build_question_coverage(
    research_plan: ResearchPlan,
    evidence_store: EvidenceStore,
) -> dict[str, dict[str, list[str]]]:
    """
    Build a per-question evidence coverage map.
    Section -> question -> list of evidence IDs that support the question.

    Args:
        research_plan (ResearchPlan): Structured research plan with key questions.
        evidence_store (EvidenceStore): Aggregated evidence store.

    Returns:
        dict[str, dict[str, list[str]]]: Section -> question -> evidence IDs coverage map.
    """
    coverage: dict[str, dict[str, list[str]]] = {}
    for section in research_plan.sections:
        section_name = str(section.name)
        coverage[section_name] = defaultdict(list)
        for question in section.key_questions:
            coverage[section_name][question]  # create question key empty list

    # go through each evidence item and questions it supports then tie to the section name and question
    for item in evidence_store.items:
        section_coverage = coverage.get(item.section)
        if not section_coverage:
            continue
        for question in item.supported_questions:
            if question not in section_coverage:
                continue
            if item.id not in section_coverage[question]:
                section_coverage[question].append(item.id)

    return {section: dict(questions) for section, questions in coverage.items()}


def is_question_covered(evidence_ids: list[str], min_evidence: int) -> bool:
    """
    Check whether a question meets the minimum evidence threshold.

    Args:
        evidence_ids (list[str]): Evidence IDs supporting the question.
        min_evidence (int): Minimum evidence required.

    Returns:
        bool: True if the question meets the threshold.
    """
    return len(evidence_ids) >= min_evidence


def is_section_covered(
    section_name: str,
    section_coverage: dict[str, list[str]],
    min_evidence: int,
) -> bool:
    """
    Check whether all questions in a section meet the minimum evidence threshold.

    Args:
        section_name (str): Section name (CommonSection value as string).
        section_coverage (dict[str, list[str]]): Question -> evidence IDs map.
        min_evidence (int): Minimum evidence required per question.

    Returns:
        bool: True if all questions meet the threshold and section target is met.
    """
    question_covered = all(
        is_question_covered(evidence_ids, min_evidence)
        for evidence_ids in section_coverage.values()
    )
    if not question_covered:
        return False

    section_min = get_min_evidence(section_name)
    unique_evidence_ids = {
        evidence_id
        for evidence_ids in section_coverage.values()
        for evidence_id in evidence_ids
    }
    return len(unique_evidence_ids) >= section_min


def build_gap_tasks(
    question_coverage: dict[str, dict[str, list[str]]],
    min_evidence: int,
    guidance_map: dict[str, Any] | None = None,
) -> list[GapTask]:
    """
    Build question-level gap tasks from coverage. If the question does not meet the minimum evidence,
    it is added to the gap tasks for targeted collectors.

    Args:
        question_coverage (dict[str, dict[str, list[str]]]): Coverage map.
        min_evidence (int): Minimum evidence required per question.
        guidance_map (dict[str, Any] | None): Guidance from Research Head.

    Returns:
        list[dict[str, Any]]: Gap tasks for targeted collection.
    """
    tasks: list[GapTask] = []

    for section, questions in question_coverage.items():
        # Factor 1: Question Coverage (Quantitative)
        # Check if individual questions meet the minimum evidence count
        missing_questions = [
            question
            for question, evidence_ids in questions.items()
            if not is_question_covered(evidence_ids, min_evidence)
        ]

        # Factor 2: Qualitative Guidance (needs_more_research)
        # Check if Research Head explicitly flagged the section
        needs_more = False
        if guidance_map:
            section_guidance = guidance_map.get(section)
            if section_guidance and isinstance(section_guidance, dict):
                needs_more = section_guidance.get("needs_more_research", False)

        if not missing_questions and needs_more:
            # Force task for this section, include all questions to drive broad search
            missing_questions = list(questions.keys())

        # Factor 3: Section Coverage (Total Count)
        # Check if the section as a whole meets the SECTION_MIN_EVIDENCE target
        if not missing_questions:
            if not is_section_covered(section, questions, min_evidence):
                # Section total too low, force all questions to collect more volume
                missing_questions = list(questions.keys())

        if not missing_questions:
            continue

        tasks.append(
            GapTask(
                section=CommonSection(section),
                missing_questions=missing_questions,
                min_evidence=min_evidence,
            )
        )
    return tasks
