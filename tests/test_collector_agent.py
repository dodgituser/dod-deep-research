"""Functional tests for collector agent."""

import json
import uuid

import pytest
from google.genai import types
from google.adk.models.llm_response import LlmResponse

from dod_deep_research.agents.collector.agent import create_collector_agent
from dod_deep_research.agents.collector.schemas import CollectorResponse
from dod_deep_research.agents.schemas import CommonSection
from dod_deep_research.deep_research import build_runner, run_agent


def _mock_evidence_payload(section_name: str) -> dict:
    """
    Build a deterministic CollectorResponse payload for tests.

    Args:
        section_name: Section name for evidence.

    Returns:
        dict: Mock collector response payload.
    """
    return {
        "section": section_name,
        "evidence": [
            {
                "id": "E1",
                "source": "pubmed",
                "title": "Amyotrophic lateral sclerosis overview",
                "url": "https://pubmed.ncbi.nlm.nih.gov/00000001/",
                "quote": "ALS is a progressive neurodegenerative disease.",
                "year": 2020,
                "tags": ["als", "overview"],
                "section": section_name,
            },
            {
                "id": "E2",
                "source": "pubmed",
                "title": "ALS diagnostics and biomarkers",
                "url": "https://pubmed.ncbi.nlm.nih.gov/00000002/",
                "quote": "Diagnosis is supported by clinical and electrodiagnostic criteria.",
                "year": 2021,
                "tags": ["als", "diagnosis"],
                "section": section_name,
            },
            {
                "id": "E3",
                "source": "pubmed",
                "title": "Epidemiology of ALS",
                "url": "https://pubmed.ncbi.nlm.nih.gov/00000003/",
                "quote": "ALS incidence is estimated at 1-2 per 100,000 person-years.",
                "year": 2019,
                "tags": ["als", "epidemiology"],
                "section": section_name,
            },
        ],
    }


@pytest.mark.asyncio
async def test_collector_agent():
    """
    Test collector agent by running it with a sample section.

    Verifies:
    - Agent runs without errors
    - Returns valid JSON response
    - Response matches CollectorResponse schema
    - Contains evidence items
    - Evidence items have required fields (id, source, title, quote, section)
    - Evidence items are properly prefixed with section name
    """
    # Create a collector agent for disease_overview section
    section_name = CommonSection.DISEASE_OVERVIEW.value
    collector = create_collector_agent(section_name)
    collector.tools = []

    def _mock_before_model_callback(callback_context=None, llm_request=None):
        payload = _mock_evidence_payload(section_name)
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=json.dumps(payload))],
            )
        )

    collector.before_model_callback = _mock_before_model_callback

    runner = build_runner(agent=collector, app_name="test_collector")
    user_id = "test_user"
    session_id = str(uuid.uuid4())

    # Create test message with indication prompt
    test_message = types.Content(
        parts=[
            types.Part.from_text(
                text=(
                    "My specific disease indication for this report is: ALS. "
                    "Please collect evidence for the disease_overview section about ALS. "
                    "Use PubMed tools only and include at least 3 citations."
                )
            )
        ],
        role="user",
    )

    # Create session with initial state and research plan
    session = await runner.session_service.create_session(
        app_name="test_collector",
        user_id=user_id,
        session_id=session_id,
        state={
            "indication": "ALS",
            "drug_name": "IL-2",
            "research_plan": {
                "disease": "ALS",
                "research_areas": ["disease_overview"],
                "sections": [
                    {
                        "name": section_name,
                        "description": "Overview of ALS disease",
                        "key_questions": ["What is ALS?", "How is ALS diagnosed?"],
                        "scope": "Focus on ALS disease characteristics",
                    }
                ],
            },
            f"research_section_{section_name}": {
                "name": section_name,
                "description": "Overview of ALS disease",
                "key_questions": ["What is ALS?", "How is ALS diagnosed?"],
                "scope": "Focus on ALS disease characteristics",
            },
        },
    )

    # Run agent
    json_responses = await run_agent(runner, session.user_id, session.id, test_message)

    # Analyze results
    assert len(json_responses) > 0, "Agent should return at least one JSON response"

    # Get final response (last one)
    final_response = json_responses[-1]

    # Validate against CollectorResponse schema
    collector_response = CollectorResponse(**final_response)

    # Check required fields
    assert collector_response.section == section_name, (
        f"Section should match {section_name}"
    )
    assert len(collector_response.evidence_items) >= 3, (
        "Collector should return at least 3 evidence items for required section"
    )

    # Validate evidence items
    for item in collector_response.evidence_items:
        assert item.id is not None, "Evidence item should have an id"
        assert item.id.startswith(f"{section_name}_"), (
            f"Evidence ID should be prefixed with {section_name}_"
        )
        assert item.source is not None, "Evidence item should have a source"
        assert item.title is not None, "Evidence item should have a title"
        assert item.quote is not None, "Evidence item should have a quote"
        assert item.section == section_name, "Evidence item section should match"
        assert item.url is not None, "Evidence item should have a URL"

    # Check session state was updated
    updated_session = await runner.session_service.get_session(
        app_name="test_collector",
        user_id=user_id,
        session_id=session.id,
    )
    state_key = f"evidence_store_section_{section_name}"
    assert state_key in updated_session.state, (
        f"Session state should contain {state_key}"
    )
