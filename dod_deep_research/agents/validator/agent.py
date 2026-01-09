"""Validator agent for output validation against schema."""

from google.adk import Agent

from dod_deep_research.agents.validator.prompt import VALIDATOR_AGENT_PROMPT
from dod_deep_research.agents.validator.schemas import ValidationReport
from dod_deep_research.models import GeminiModels

validator_agent = Agent(
    name="validator_agent",
    instruction=VALIDATOR_AGENT_PROMPT,
    tools=[],
    model=GeminiModels.GEMINI_25_FLASH_LITE.value.replace("models/", ""),
    output_key="validation_report",
    output_schema=ValidationReport,
)
