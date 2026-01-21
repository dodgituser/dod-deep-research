"""Evidence collector agent factory for section-specific evidence retrieval."""

import os

from typing import Any, Callable

from google.adk import Agent
from google.adk.agents import ParallelAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

from dod_deep_research.agents.callbacks.after_agent_log_callback import (
    after_agent_log_callback,
)
from dod_deep_research.agents.collector.prompt import (
    COLLECTOR_AGENT_PROMPT_TEMPLATE,
    TARGETED_COLLECTOR_AGENT_PROMPT_TEMPLATE,
)
from dod_deep_research.agents.collector.schemas import CollectorResponse
from dod_deep_research.utils.evidence import GapTask
from dod_deep_research.core import get_http_options
from dod_deep_research.models import GeminiModels
from dod_deep_research.agents.tooling import reflect_step
from dod_deep_research.utils.evidence import get_min_evidence
import logging
from google.genai.types import GenerateContentConfig

logger = logging.getLogger(__name__)

EXA_DEFAULT_TOOLS = "web_search_exa,crawling_exa,company_research_exa"


def _get_tools():
    """Get standard tools for collector agents."""
    pubmed_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp"),
            timeout=180,
            sse_read_timeout=180,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["pubmed_search_articles", "pubmed_fetch_contents"],
    )
    clinical_trials_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp"),
            timeout=180,
            sse_read_timeout=180,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["clinicaltrials_search_studies", "clinicaltrials_get_study"],
    )
    exa_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("EXA_MCP_URL", "http://127.0.0.1:3019/mcp"),
            timeout=10,
            sse_read_timeout=10,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["web_search_exa", "crawling_exa", "company_research_exa"],
    )
    return [
        pubmed_toolset,
        reflect_step,
        clinical_trials_toolset,
        exa_toolset,
    ]


def get_collector_tools():
    """Return the collector toolset including PubMed and ClinicalTrials."""
    return _get_tools()


def create_collector_agent(
    section_name: str,
    before_agent_callback: Callable[[CallbackContext], types.Content | None]
    | None = None,
) -> Agent:
    """
    Create a collector agent for a specific section.

    Args:
        section_name: Name of the section to collect evidence for.
        before_agent_callback: Callback to run before the agent executes.

    Returns:
        Agent: Configured collector agent for the section.
    """
    min_evidence = get_min_evidence(section_name)
    prompt = COLLECTOR_AGENT_PROMPT_TEMPLATE.format(
        section_name=section_name,
        min_evidence=min_evidence,
    )
    agent_name = f"collector_{section_name}"

    agent = Agent(
        name=agent_name,
        instruction=prompt,
        tools=_get_tools(),
        model=GeminiModels.GEMINI_FLASH_LATEST.value.replace("models/", ""),
        include_contents="none",
        output_key=f"evidence_store_section_{section_name}",
        output_schema=CollectorResponse,
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            http_options=get_http_options(),
        ),
    )

    if before_agent_callback:
        agent.before_agent_callback = before_agent_callback
    return agent


def create_collector_agents(
    sections: list[str],
    after_agent_callback: Callable[[CallbackContext], types.Content | None]
    | None = None,
) -> ParallelAgent:
    """
    Create a list of collector agents for the given sections.
    """
    parallel_agent = ParallelAgent(
        name="evidence_collectors",
        sub_agents=[create_collector_agent(section) for section in sections],
        after_agent_callback=after_agent_callback,
    )
    return parallel_agent


def create_targeted_collector_agent(
    gap: GapTask,
    guidance: dict[str, Any] | None = None,
) -> Agent:
    """
    Create a targeted collector agent for a specific gap task.

    Args:
        gap: GapTask specifying the targeted collection parameters.
        guidance: Suggestions for the section. notes + suggested queries

    Returns:
        Agent: Configured targeted collector agent.
    """
    min_evidence = get_min_evidence(str(gap.section))
    guidance_notes = ""
    suggested_queries = ""
    if guidance:
        guidance_notes = str(guidance["notes"]).strip()
        suggested_queries = ", ".join(guidance["suggested_queries"])
    prompt = TARGETED_COLLECTOR_AGENT_PROMPT_TEMPLATE.format(
        section_name=gap.section,
        missing_questions=", ".join(gap.missing_questions) or "None",
        guidance_notes=guidance_notes or "None",
        suggested_queries=suggested_queries or "None",
        min_evidence=min_evidence,
    )
    agent_name = f"targeted_collector_{gap.section}"

    agent = Agent(
        name=agent_name,
        instruction=prompt,
        tools=[t for t in _get_tools() if t != reflect_step],
        model=GeminiModels.GEMINI_25_PRO.value.replace("models/", ""),
        after_agent_callback=after_agent_log_callback,
        include_contents="none",
        output_key=f"evidence_store_section_{gap.section}",
        output_schema=CollectorResponse,
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            http_options=get_http_options(),
        ),
    )
    return agent


def create_targeted_collector_agents(
    gap_tasks: list[GapTask],
    guidance_map: dict[str, dict[str, Any]] | None = None,
    after_agent_callback: Callable[[CallbackContext], types.Content | None]
    | None = None,
) -> ParallelAgent:
    """
    Create a parallel agent with targeted collectors for the given tasks.

    Args:
        gap_tasks: List of GapTask objects.
        guidance_map: Suggestions for each section. section -> notes + suggested queries
        after_agent_callback: Optional callback to run after collectors complete.

    Returns:
        ParallelAgent with targeted collector agents.
    """
    if not gap_tasks:
        return ParallelAgent(
            name="targeted_collectors_empty",
            sub_agents=[],
        )

    collector_agents = [
        create_targeted_collector_agent(
            gap,
            guidance=guidance_map.get(str(gap.section)) if guidance_map else None,
        )
        for gap in gap_tasks
    ]

    parallel_agent = ParallelAgent(
        name="targeted_collectors",
        sub_agents=collector_agents,
        after_agent_callback=after_agent_callback,
    )

    return parallel_agent
