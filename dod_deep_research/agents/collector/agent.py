"""Evidence collector agent factory for section-specific evidence retrieval."""

import os

from google.adk import Agent
from google.adk.tools import FunctionTool, google_search
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from dod_deep_research.agents.collector.prompt import COLLECTOR_AGENT_PROMPT_TEMPLATE
from dod_deep_research.agents.collector.schemas import CollectorResponse
from dod_deep_research.models import GeminiModels
from dod_deep_research.tools import reflect_step


def create_collector_agent(section_name: str) -> Agent:
    """
    Create a collector agent for a specific section.

    Args:
        section_name: Name of the section to collect evidence for.

    Returns:
        Agent: Configured collector agent for the section.
    """
    prompt = COLLECTOR_AGENT_PROMPT_TEMPLATE.format(section_name=section_name)
    pubmed_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp"),
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["pubmed_search_articles", "pubmed_fetch_contents"],
    )
    clinical_trials_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp"),
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["clinicaltrials_search_studies", "clinicaltrials_get_study"],
    )

    return Agent(
        name=f"collector_{section_name}",
        instruction=prompt,
        tools=[
            google_search,
            pubmed_toolset,
            clinical_trials_toolset,
            FunctionTool(reflect_step),
        ],
        model=GeminiModels.GEMINI_25_FLASH_LITE.value.replace("models/", ""),
        output_key=f"evidence_store_section_{section_name}",
        output_schema=CollectorResponse,
    )
