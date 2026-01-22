"""Tests for writer utilities."""

from dod_deep_research.utils.writer import extract_citation_ids


def test_extract_citation_ids_handles_comma_separated_ids() -> None:
    report = (
        "Intro text [alpha_id]. "
        "More text [beta_id, gamma_id]. "
        "Repeat [beta_id]. "
        "Trailing commas [delta_id, , epsilon_id]."
    )

    assert extract_citation_ids(report) == [
        "alpha_id",
        "beta_id",
        "gamma_id",
        "delta_id",
        "epsilon_id",
    ]
