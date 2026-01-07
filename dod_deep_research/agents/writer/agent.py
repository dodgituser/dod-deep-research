"""Writer agent for generating final structured output."""

from google.adk import Agent

from dod_deep_research.agents.writer.prompt import WRITER_AGENT_PROMPT
from dod_deep_research.agents.writer.structured_response import WriterResponse
from dod_deep_research.models import GeminiModels

root_agent = Agent(
    name="writer_agent",
    instruction=WRITER_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_20_FLASH_LITE.value.replace("models/", ""),
    output_key="deep_research_output",
    output_schema=WriterResponse,
)
