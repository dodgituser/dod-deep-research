"""Aggregator agent for merging parallel collector outputs."""

from google.adk import Agent

from dod_deep_research.agents.aggregator.aggregator_prompt import (
    AGGREGATOR_AGENT_PROMPT,
)
from dod_deep_research.agents.aggregator.aggregator_structured_response import (
    AggregatorResponse,
)
from dod_deep_research.models import GeminiModels

root_agent = Agent(
    name="aggregator_agent",
    instruction=AGGREGATOR_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_20_FLASH_LITE.value.replace("models/", ""),
    output_key="evidence_store",
    output_schema=AggregatorResponse,
)
