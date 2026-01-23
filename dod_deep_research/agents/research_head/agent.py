"""Research Head agents for gap analysis and targeted retrieval."""

from google.adk import Agent
from google.adk.agents import ParallelAgent
from google.genai import types

from dod_deep_research.core import get_http_options
from dod_deep_research.agents.research_head.prompt import (
    RESEARCH_HEAD_QUAL_PROMPT,
    RESEARCH_HEAD_QUANT_PROMPT,
)
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.models import GeminiModels


def _get_research_head_quant_agent() -> Agent:
    """
    Build the quantitative research head agent.

    Returns:
        Agent: Configured quantitative research head agent.
    """
    return Agent(
        name="research_head_quant_agent",
        instruction=RESEARCH_HEAD_QUANT_PROMPT,
        model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            http_options=get_http_options(),
        ),
        output_key="research_head_quant_plan",
        output_schema=ResearchHeadPlan,
    )


def _get_research_head_qual_agent() -> Agent:
    """
    Build the qualitative research head agent.

    Returns:
        Agent: Configured qualitative research head agent.
    """
    return Agent(
        name="research_head_qual_agent",
        instruction=RESEARCH_HEAD_QUAL_PROMPT,
        model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
        include_contents="none",
        generate_content_config=types.GenerateContentConfig(
            http_options=get_http_options(),
        ),
        output_key="research_head_qual_plan",
        output_schema=ResearchHeadPlan,
    )


def _get_research_head_parallel_agent() -> ParallelAgent:
    """
    Build the parallel research head agent.

    Returns:
        ParallelAgent: Parallel agent running quant + qual research heads.
    """
    return ParallelAgent(
        name="research_head_parallel",
        sub_agents=[_get_research_head_quant_agent(), _get_research_head_qual_agent()],
    )


RESEARCH_HEAD_PARALLEL_AGENT = _get_research_head_parallel_agent()
RESEARCH_HEAD_QUAL_AGENT = _get_research_head_qual_agent()
