"""Tests for EvidenceItem ID generation and integrity."""

import hashlib
import pytest
from dod_deep_research.agents.collector.schemas import EvidenceItem
from dod_deep_research.agents.schemas import EvidenceSource


def test_evidence_item_id_generation_from_scratch() -> None:
    """Verify that ID is correctly generated and prefixed when creating from scratch."""
    section = "rationale_executive_summary"
    quote = "This is a test quote."
    url = "https://example.com/article"

    item = EvidenceItem(
        source=EvidenceSource.PUBMED,
        title="Test Title",
        quote=quote,
        url=url,
        section=section,
    )

    content_sig = f"{url}|{quote}"
    expected_hash = hashlib.sha256(content_sig.encode()).hexdigest()[:8]
    expected_id = f"{section}_{expected_hash}"

    assert item.id == expected_id


def test_evidence_item_id_updates_on_content_change() -> None:
    """Verify that ID changes when content changes, even if an old ID is provided."""
    section = "disease_overview"
    quote_1 = "Initial quote."
    url = "https://example.com"

    item_1 = EvidenceItem(
        source=EvidenceSource.WEB,
        title="Title",
        quote=quote_1,
        url=url,
        section=section,
    )

    old_id = item_1.id

    # Change the quote but pass in the old ID (simulating state reload)
    quote_2 = "Modified quote."
    item_2 = EvidenceItem(
        id=old_id,
        source=EvidenceSource.WEB,
        title="Title",
        quote=quote_2,
        url=url,
        section=section,
    )

    assert item_2.id != old_id
    assert item_2.id.startswith(f"{section}_")

    # Verify the new hash matches the new content
    expected_hash = hashlib.sha256(f"{url}|{quote_2}".encode()).hexdigest()[:8]
    assert item_2.id == f"{section}_{expected_hash}"


def test_evidence_item_id_preserves_valid_prefixed_id() -> None:
    """Verify that a valid prefixed ID is preserved if it matches the content."""
    section = "therapeutic_landscape"
    quote = "Static quote."
    url = "https://example.com"

    content_sig = f"{url}|{quote}"
    valid_hash = hashlib.sha256(content_sig.encode()).hexdigest()[:8]
    valid_id = f"{section}_{valid_hash}"

    item = EvidenceItem(
        id=valid_id,
        source=EvidenceSource.CLINICALTRIALS,
        title="Title",
        quote=quote,
        url=url,
        section=section,
    )

    assert item.id == valid_id


def test_evidence_item_id_fallback_without_section() -> None:
    """Verify fallback behavior when section is missing (though it is required by schema)."""
    quote = "Fallback test."
    url = "https://example.com"

    # We use model_validate with a dict to bypass initial Pydantic type checks for 'section'
    # to test the internal logic of the validator.
    data = {
        "source": EvidenceSource.WEB,
        "title": "Title",
        "quote": quote,
        "url": url,
        # "section" is missing here
    }

    # This should fail validation because 'section' is required, but we want to see if the validator
    # handled the ID generation correctly before the 'required' check fails.
    with pytest.raises(Exception) as excinfo:
        EvidenceItem.model_validate(data)

    # Check that 'section' is indeed the reason it failed, not the ID generation
    assert "section" in str(excinfo.value)
