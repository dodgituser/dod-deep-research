"""Planner agent for research strategy."""

from google.adk import Agent
from google.genai import types

from dod_deep_research.agents.planner.prompt import PLANNER_AGENT_PROMPT
from dod_deep_research.agents.planner.structured_response import ResearchPlan
from dod_deep_research.models import GeminiModels

root_agent = Agent(
    name="planner_agent",
    instruction=PLANNER_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_20_FLASH_LITE.value.replace("models/", ""),
    output_key="research_plan",
    generate_content_config=types.GenerateContentConfig(response_schema=ResearchPlan),
)
