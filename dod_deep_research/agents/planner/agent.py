"""Planner agent for research strategy."""

from google.adk import Agent
from google.genai import types

from dod_deep_research.core import get_http_options
from dod_deep_research.agents.planner.prompt import PLANNER_AGENT_PROMPT
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.models import GeminiModels

planner_agent = Agent(
    name="planner_agent",
    instruction=PLANNER_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    generate_content_config=types.GenerateContentConfig(
        http_options=get_http_options(),
    ),
    output_key="research_plan",
    output_schema=ResearchPlan,
)
