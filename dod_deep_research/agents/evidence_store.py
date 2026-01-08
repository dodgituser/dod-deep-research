"""Evidence store utilities for managing and merging evidence."""

import hashlib

from dod_deep_research.schemas import EvidenceItem, EvidenceStore


def compute_content_hash(item: EvidenceItem) -> str:
    """
    Compute content hash for deduplication.

    Args:
        item: Evidence item to hash.

    Returns:
        str: SHA256 hash of title + url + quote.
    """
    content = f"{item.title}|{item.url or ''}|{item.quote or ''}"
    return hashlib.sha256(content.encode()).hexdigest()


def add_evidence(store: EvidenceStore, item: EvidenceItem, section: str) -> bool:
    """
    Add evidence to store with deduplication.

    Args:
        store: Evidence store to add to.
        item: Evidence item to add.
        section: Section name this evidence belongs to.

    Returns:
        bool: True if evidence was added, False if duplicate.
    """
    content_hash = compute_content_hash(item)

    if content_hash in store.hash_index:
        return False

    store.items.append(item)
    store.hash_index[content_hash] = item.id

    if section not in store.by_section:
        store.by_section[section] = []
    store.by_section[section].append(item.id)

    if item.url:
        if item.url not in store.by_source:
            store.by_source[item.url] = []
        store.by_source[item.url].append(item.id)

    return True


def get_evidence_by_section(store: EvidenceStore, section: str) -> list[EvidenceItem]:
    """
    Get evidence items for a specific section.

    Args:
        store: Evidence store to query.
        section: Section name.

    Returns:
        list[EvidenceItem]: List of evidence items for the section.
    """
    evidence_ids = store.by_section.get(section, [])
    return [item for item in store.items if item.id in evidence_ids]


def merge_evidence_stores(stores: list[EvidenceStore]) -> EvidenceStore:
    """
    Merge multiple evidence stores into one with deduplication.

    Args:
        stores: List of evidence stores to merge.

    Returns:
        EvidenceStore: Merged evidence store.
    """
    merged = EvidenceStore()

    for store in stores:
        for item in store.items:
            section = item.section
            add_evidence(merged, item, section)

        merged.gaps.extend(store.gaps)

    return merged
