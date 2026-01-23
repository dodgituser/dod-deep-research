"""Planner agent for research strategy."""

# NOTE: We avoid ADK output_schema here because the ResearchPlan schema is too large/complex
# and can hit the "too many states" limitation in Gemini/ADK. See
# https://github.com/cline/cline/issues/7897. We handle structured output parsing ourselves.

import json

from google.adk import Agent
from google.genai import types

from dod_deep_research.core import get_http_options, inline_json_schema
from dod_deep_research.agents.planner.prompt import PLANNER_AGENT_PROMPT
from dod_deep_research.models import GeminiModels
from dod_deep_research.agents.planner.schemas import ResearchPlan


def create_planner_agent(indication_prompt: str | None = None) -> Agent:
    """
    Create a planner agent with optional indication prompt context.

    Args:
        indication_prompt (str | None): Optional indication prompt to append.

    Returns:
        Agent: Configured planner agent.
    """
    research_plan_schema = json.dumps(
        inline_json_schema(ResearchPlan),
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    )
    instruction = PLANNER_AGENT_PROMPT.replace(
        "{research_plan_schema}", research_plan_schema
    )  # replace the research_plan_schema in the prompt with the actual schema
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
        model=GeminiModels.GEMINI_FLASH_LATEST.value.replace("models/", ""),
        generate_content_config=types.GenerateContentConfig(
            http_options=get_http_options(),
        ),
        output_key="research_plan_raw",
    )  # return the research_plan_raw from the agent (we will parse this later)
