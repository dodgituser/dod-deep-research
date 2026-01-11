"""Test agents for functional testing,, can plug and play for different agents to run adk web ui locally."""

from google.adk import Agent
from dod_deep_research.models import GeminiModels
from dod_deep_research.agents.collector.agent import get_collector_tools

root_agent = Agent(
    name="tooling_agent",
    tools=get_collector_tools(),
    model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
    instruction=(
        "You are a tooling agent. Verify PubMed MCP tools by calling them with "
        "simple queries and summarize the results."
    ),
)
