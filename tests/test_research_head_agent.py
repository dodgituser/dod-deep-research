"""Functional tests for research head agent."""

import uuid

import pytest
from google.genai import types

from dod_deep_research.agents.collector.schemas import EvidenceItem
from dod_deep_research.agents.research_head.agent import research_head_agent
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.deep_research import build_runner, run_agent
from dod_deep_research.agents.shared_state import EvidenceStore


@pytest.mark.asyncio
async def test_research_head_agent():
    """
    Test research head agent by running it with evidence store and research plan.

    Verifies:
    - Agent runs without errors
    - Returns valid JSON response
    - Response matches ResearchHeadPlan schema
    - Contains required fields (continue_research, gaps, tasks)
    - Gaps are properly identified when evidence is missing
    - Tasks are properly structured when gaps exist
    """
    runner = build_runner(agent=research_head_agent, app_name="test_research_head")
    user_id = "test_user"
    session_id = str(uuid.uuid4())

    # Create sample evidence store with limited evidence
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
                text="Analyze the evidence gaps and create retrieval tasks if needed."
            )
        ],
        role="user",
    )

    # Create session with initial state including evidence store and research plan
    session = await runner.session_service.create_session(
        app_name="test_research_head",
        user_id=user_id,
        session_id=session_id,
        state={
            "indication": "ALS",
            "drug_name": "IL-2",
            "evidence_store": evidence_store.model_dump(),
            "research_plan": {
                "disease": "ALS",
                "research_areas": [
                    "disease_overview",
                    "clinical_trials_analysis",
                    "therapeutic_landscape",
                ],
                "sections": [
                    {
                        "name": "disease_overview",
                        "description": "Overview of ALS",
                        "key_questions": ["What is ALS?", "How is ALS diagnosed?"],
                        "scope": "ALS disease characteristics",
                    },
                    {
                        "name": "clinical_trials_analysis",
                        "description": "Clinical trials for IL-2 in ALS",
                        "key_questions": ["What trials exist for IL-2 in ALS?"],
                        "scope": "IL-2 trials in ALS",
                    },
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

    # Validate against ResearchHeadPlan schema
    research_head_plan = ResearchHeadPlan(**final_response)

    # Check required fields
    assert research_head_plan.continue_research is not None, (
        "Research head plan should have continue_research flag"
    )
    assert research_head_plan.gaps is not None, "Research head plan should have gaps"
    assert research_head_plan.tasks is not None, "Research head plan should have tasks"

    # If gaps are identified, tasks should be created
    if research_head_plan.continue_research:
        assert len(research_head_plan.tasks) > 0, (
            "If continuing research, tasks should be provided"
        )

    # Validate gap structure if gaps exist
    for gap in research_head_plan.gaps:
        assert gap.section is not None, "Gap should have a section"
        assert gap.missing_evidence_types is not None, (
            "Gap should have missing_evidence_types"
        )
        assert gap.missing_questions is not None, "Gap should have missing_questions"
        assert gap.notes is not None, "Gap should have notes"

    # Validate task structure if tasks exist
    for task in research_head_plan.tasks:
        assert task.section is not None, "Task should have a section"
        assert task.evidence_type is not None, "Task should have evidence_type"
        assert task.query is not None, "Task should have query"
        assert task.preferred_tool is not None, "Task should have preferred_tool"
        assert task.priority is not None, "Task should have priority"
        assert task.priority in [
            "high",
            "medium",
            "low",
        ], "Task priority should be high, medium, or low"

    # Check session state was updated
    updated_session = await runner.session_service.get_session(
        app_name="test_research_head",
        user_id=user_id,
        session_id=session.id,
    )
    assert "research_head_plan" in updated_session.state, (
        "Session state should contain research_head_plan"
    )
