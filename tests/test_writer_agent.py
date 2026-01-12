"""Functional tests for writer agent."""

import uuid

import pytest
from google.genai import types

from dod_deep_research.agents.collector.schemas import EvidenceItem
from dod_deep_research.agents.writer.agent import writer_agent
from dod_deep_research.agents.writer.schemas import WriterOutput
from dod_deep_research.deep_research import build_runner, run_agent
from dod_deep_research.agents.shared_state import EvidenceStore


@pytest.mark.asyncio
async def test_writer_agent():
    """
    Test writer agent by running it with aggregated evidence.

    Verifies:
    - Agent runs without errors
    - Returns valid JSON response
    - Response matches WriterOutput schema
    - Contains required fields (metadata, indication_profile, etc.)
    - Metadata has proper structure
    - Indication profile is populated
    """
    runner = build_runner(agent=writer_agent, app_name="test_writer")
    user_id = "test_user"
    session_id = str(uuid.uuid4())

    # Create sample evidence store
    sample_evidence_items = [
        EvidenceItem(
            id="disease_overview_E1",
            source="pubmed",
            title="ALS Overview",
            url="https://example.com/als",
            quote="ALS is a neurodegenerative disease",
            year=2023,
            tags=["disease"],
            section="disease_overview",
        ),
        EvidenceItem(
            id="clinical_trials_analysis_E1",
            source="clinicaltrials",
            title="IL-2 Trial for ALS",
            url="https://clinicaltrials.gov/ct2/show/NCT12345",
            quote="Phase 2 trial of IL-2 in ALS patients",
            year=2024,
            tags=["trial"],
            section="clinical_trials_analysis",
        ),
    ]

    evidence_store = EvidenceStore(
        items=sample_evidence_items,
        by_section=[],
        by_source=[],
        hash_index=[],
    )

    # Create test message
    test_message = types.Content(
        parts=[
            types.Part.from_text(
                text="Generate the final research report based on the collected evidence."
            )
        ],
        role="user",
    )

    # Create session with initial state including evidence store
    session = await runner.session_service.create_session(
        app_name="test_writer",
        user_id=user_id,
        session_id=session_id,
        state={
            "indication": "ALS",
            "drug_name": "IL-2",
            "evidence_store": evidence_store.model_dump(),
            "research_plan": {
                "disease": "ALS",
                "research_areas": ["disease_overview", "clinical_trials_analysis"],
                "sections": [
                    {
                        "name": "disease_overview",
                        "description": "Overview of ALS",
                        "key_questions": ["What is ALS?"],
                        "scope": "ALS disease characteristics",
                    }
                ],
            },
        },
    )

    # Run agent
    json_responses = await run_agent(runner, session.user_id, session.id, test_message)

    # Analyze results
    assert len(json_responses) > 0, "Agent should return at least one JSON response"

    # Get final response (last one)
    final_response = json_responses[-1]

    # Validate against WriterOutput schema
    writer_output = WriterOutput(**final_response)

    # Check required fields
    assert writer_output.metadata is not None, "Writer output should have metadata"
    assert writer_output.metadata.generated_at is not None, (
        "Metadata should have generated_at timestamp"
    )
    assert writer_output.metadata.model is not None, "Metadata should have model name"

    assert writer_output.indication_profile is not None, (
        "Writer output should have indication_profile"
    )
    assert writer_output.indication_profile.disease_name is not None, (
        "Indication profile should have disease_name"
    )

    # Check optional fields are present (may be empty lists)
    assert writer_output.mechanistic_rationales is not None, (
        "Writer output should have mechanistic_rationales"
    )
    assert writer_output.competitive_landscape is not None, (
        "Writer output should have competitive_landscape"
    )
    assert writer_output.drug_specific_trials is not None, (
        "Writer output should have drug_specific_trials"
    )
    assert writer_output.provenance is not None, "Writer output should have provenance"

    # Check session state was updated
    updated_session = await runner.session_service.get_session(
        app_name="test_writer",
        user_id=user_id,
        session_id=session.id,
    )
    assert "deep_research_output" in updated_session.state, (
        "Session state should contain deep_research_output"
    )
