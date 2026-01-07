"""Retriever/Synthesizer agent for evidence retrieval."""

from google.adk import Agent

from dod_deep_research.agents.retriever.prompt import RETRIEVER_AGENT_PROMPT
from dod_deep_research.agents.retriever.structured_response import EvidenceListResponse
from dod_deep_research.models import GeminiModels

root_agent = Agent(
    name="retriever_agent",
    instruction=RETRIEVER_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_20_FLASH_LITE.value.replace("models/", ""),
    output_key="evidence_list",
    output_schema=EvidenceListResponse,
)
