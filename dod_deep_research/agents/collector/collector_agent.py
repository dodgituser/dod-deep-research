"""Evidence collector agent factory for section-specific evidence retrieval."""

from google.adk import Agent

from dod_deep_research.agents.collector.collector_prompt import (
    COLLECTOR_AGENT_PROMPT_TEMPLATE,
)
from dod_deep_research.agents.collector.collector_structured_response import (
    CollectorResponse,
)
from dod_deep_research.models import GeminiModels


def create_collector_agent(section_name: str) -> Agent:
    """
    Create a collector agent for a specific section.

    Args:
        section_name: Name of the section to collect evidence for.

    Returns:
        Agent: Configured collector agent for the section.
    """
    prompt = COLLECTOR_AGENT_PROMPT_TEMPLATE.format(section_name=section_name)

    return Agent(
        name=f"collector_{section_name}",
        instruction=prompt,
        tools=[],
        model=GeminiModels.GEMINI_20_FLASH_LITE.value.replace("models/", ""),
        output_key=f"evidence_store_section_{section_name}",
        output_schema=CollectorResponse,
    )
