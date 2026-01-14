"""Planner agent for research strategy."""

from google.adk import Agent
from google.genai import types

from dod_deep_research.core import get_http_options
from dod_deep_research.agents.planner.prompt import PLANNER_AGENT_PROMPT
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.models import GeminiModels


def create_planner_agent(indication_prompt: str | None = None) -> Agent:
    """
    Create a planner agent with optional indication prompt context.

    Args:
        indication_prompt (str | None): Optional indication prompt to append.

    Returns:
        Agent: Configured planner agent.
    """
    instruction = PLANNER_AGENT_PROMPT
    if indication_prompt:
        indication_block = (
            "--- BEGIN INDICATION PROMPT ---\n"
            f"{indication_prompt.strip()}\n"
            "--- END INDICATION PROMPT ---"
        )
        instruction = f"""
{instruction}

{indication_block}

Reminder: Your task is to produce a ResearchPlan from the state inputs. 
Use the indication prompt above only as guidance for section descriptions and key questions. 
Do not collect evidence, do not write the report, and do not assign tasks.
"""

    return Agent(
        name="planner_agent",
        instruction=instruction,
        tools=[],
        model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
        generate_content_config=types.GenerateContentConfig(
            http_options=get_http_options(),
        ),
        output_key="research_plan",
        output_schema=ResearchPlan,
    )


planner_agent = create_planner_agent()
