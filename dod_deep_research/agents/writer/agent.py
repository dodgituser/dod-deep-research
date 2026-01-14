"""Section writer agent for long-form report assembly."""

from google.adk import Agent
from google.genai import types

from dod_deep_research.core import get_http_options
from dod_deep_research.agents.writer.prompt import LONG_WRITER_SECTION_PROMPT
from dod_deep_research.agents.writer.schemas import SectionDraft
from dod_deep_research.models import GeminiModels

section_writer_agent = Agent(
    name="section_writer_agent",
    instruction=LONG_WRITER_SECTION_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    generate_content_config=types.GenerateContentConfig(
        http_options=get_http_options(),
    ),
    output_key="section_draft",
    output_schema=SectionDraft,
)
