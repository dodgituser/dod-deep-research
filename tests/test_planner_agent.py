"""Functional tests for planner agent."""

import uuid

import pytest
from google.genai import types

from dod_deep_research.agents.planner.agent import planner_agent
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.deep_research import build_runner, run_agent


@pytest.mark.asyncio
async def test_planner_agent():
    """
    Test planner agent by running it with a sample indication prompt.

    Verifies:
    - Agent runs without errors
    - Returns valid JSON response
    - Response matches ResearchPlan schema
    - Contains required fields (disease, research_areas, sections)
    - Sections are properly structured
    """
    runner = build_runner(agent=planner_agent, app_name="test_planner")
    user_id = "test_user"
    session_id = str(uuid.uuid4())

    # Create test message with indication prompt
    test_message = types.Content(
        parts=[
            types.Part.from_text(
                text="My specific disease indication for this report is: ALS. "
                "Please generate a comprehensive report on IL-2 for ALS ONLY."
            )
        ],
        role="user",
    )

    # Create session with initial state
    session = await runner.session_service.create_session(
        app_name="test_planner",
        user_id=user_id,
        session_id=session_id,
        state={"indication": "ALS", "drug_name": "IL-2"},
    )

    # Run agent
    json_responses = await run_agent(runner, session.user_id, session.id, test_message)

    # Analyze results
    assert len(json_responses) > 0, "Agent should return at least one JSON response"

    # Get final response (last one)
    final_response = json_responses[-1]

    # Validate against ResearchPlan schema
    research_plan = ResearchPlan(**final_response)

    # Check required fields
    assert research_plan.disease is not None, "Research plan should have disease field"
    assert research_plan.disease.lower() == "als", "Disease should match input"
    assert len(research_plan.research_areas) > 0, (
        "Research plan should have research areas"
    )
    assert len(research_plan.sections) > 0, "Research plan should have sections"

    # Validate section structure
    for section in research_plan.sections:
        assert section.name is not None, "Section should have a name"
        assert section.description is not None, "Section should have a description"
        assert len(section.key_questions) > 0, "Section should have key questions"
        assert section.scope is not None, "Section should have scope"

    # Check session state was updated
    updated_session = await runner.session_service.get_session(
        app_name="test_planner",
        user_id=user_id,
        session_id=session.id,
    )
    assert "research_plan" in updated_session.state, (
        "Session state should contain research_plan"
    )
