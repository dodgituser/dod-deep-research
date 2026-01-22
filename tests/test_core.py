"""Tests for core JSON extraction helpers."""

from dod_deep_research.core import extract_json_payload


def test_extract_json_payload_prefers_fenced_block_with_prose() -> None:
    """Extracts JSON from a fenced block even with leading prose."""
    raw = 'Summary first.\n```json\n{"a": 1}\n```\nMore text.'
    assert extract_json_payload(raw) == '{"a": 1}'


def test_extract_json_payload_handles_fence_without_language() -> None:
    """Extracts JSON from a fenced block without a language tag."""
    raw = "``` \n[1, 2, 3]\n```"
    assert extract_json_payload(raw) == "[1, 2, 3]"


def test_extract_json_payload_returns_raw_when_no_fence() -> None:
    """Returns the raw text when no fenced block exists."""
    raw = '{"ok": true}'
    assert extract_json_payload(raw) == raw


def test_extract_json_payload_empty_string() -> None:
    """Returns empty string when input is empty."""
    assert extract_json_payload("") == ""


def test_extract_json_payload_prose_only() -> None:
    """Returns trimmed prose when no JSON is present."""
    raw = "No JSON here."
    assert extract_json_payload(raw) == raw
