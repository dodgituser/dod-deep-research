"""Writer agent for generating final structured output."""

from google.adk import Agent
from google.genai import types

from dod_deep_research.core import get_http_options
from dod_deep_research.agents.writer.prompt import WRITER_AGENT_PROMPT
from dod_deep_research.agents.writer.schemas import MarkdownReport
from dod_deep_research.agents.callbacks.utils import get_callbacks
from dod_deep_research.models import GeminiModels

writer_agent = Agent(
    name="writer_agent",
    instruction=WRITER_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    generate_content_config=types.GenerateContentConfig(
        http_options=get_http_options(),
    ),
    output_key="deep_research_output",
    output_schema=MarkdownReport,
    **get_callbacks(),
)
