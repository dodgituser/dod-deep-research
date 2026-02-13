"""Tests for core JSON extraction helpers."""

import re
import shutil

from dod_deep_research.core import extract_json_payload
from dod_deep_research.core import get_output_path


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


def test_get_output_path_uses_group_and_run_id() -> None:
    """Creates run output path as disease-drug/run_id."""
    output_path = get_output_path("Alzheimer Disease", "Low-dose IL-2")
    try:
        assert output_path.exists()
        assert output_path.parent.name == "alzheimer_disease-low-dose_il-2"
        assert re.fullmatch(r"\d{8}_\d{6}_[0-9a-f]{8}", output_path.name)
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
