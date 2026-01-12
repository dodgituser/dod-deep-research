"""Evidence collector agent factory for section-specific evidence retrieval."""

import os

from typing import Callable

from google.adk import Agent
from google.adk.agents import ParallelAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

from dod_deep_research.agents.collector.prompt import (
    COLLECTOR_AGENT_PROMPT_TEMPLATE,
    TARGETED_COLLECTOR_AGENT_PROMPT_TEMPLATE,
)
from dod_deep_research.agents.collector.schemas import CollectorResponse
from dod_deep_research.agents.research_head.schemas import RetrievalTask
from dod_deep_research.core import get_http_options
from dod_deep_research.models import GeminiModels
from dod_deep_research.tools import reflect_step
import logging
from google.genai.types import GenerateContentConfig

logger = logging.getLogger(__name__)


def _get_tools():
    """Get standard tools for collector agents."""
    pubmed_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("PUBMED_MCP_URL", "http://127.0.0.1:3017/mcp"),
            timeout=60,
            sse_read_timeout=60,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["pubmed_search_articles", "pubmed_fetch_contents"],
    )
    clinical_trials_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.getenv("CLINICAL_TRIALS_MCP_URL", "http://127.0.0.1:3018/mcp"),
            timeout=60,
            sse_read_timeout=60,
            headers={"Accept": "application/json, text/event-stream"},
            terminate_on_close=False,
        ),
        tool_filter=["clinicaltrials_search_studies", "clinicaltrials_get_study"],
    )
    return [
        pubmed_toolset,
        reflect_step,
        clinical_trials_toolset,
    ]


def get_collector_tools():
    """Return the collector toolset including PubMed and ClinicalTrials."""
    return _get_tools()


def create_collector_agent(
    section_name: str,
    task_override: RetrievalTask | None = None,
    before_agent_callback: Callable[[CallbackContext], types.Content | None]
    | None = None,
) -> Agent:
    """
    Create a collector agent for a specific section.

    Args:
        section_name: Name of the section to collect evidence for.
        task_override: Optional RetrievalTask to create a task-focused collector.
        before_agent_callback: Callback to run before the agent executes.

    Returns:
        Agent: Configured collector agent for the section.
    """
    if task_override:
        prompt = TARGETED_COLLECTOR_AGENT_PROMPT_TEMPLATE.format(
            section_name=section_name,
            query=task_override.query,
            preferred_tool=task_override.preferred_tool,
            evidence_type=task_override.evidence_type,
            priority=task_override.priority,
        )
        agent_name = f"targeted_collector_{section_name}_{task_override.priority}"
    else:
        prompt = COLLECTOR_AGENT_PROMPT_TEMPLATE.format(section_name=section_name)
        agent_name = f"collector_{section_name}"

    agent = Agent(
        name=agent_name,
        instruction=prompt,
        tools=_get_tools(),
        model=GeminiModels.GEMINI_FLASH_LATEST.value.replace("models/", ""),
        output_key=f"evidence_store_section_{section_name}",
        output_schema=CollectorResponse,
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            http_options=get_http_options(),
        ),
    )

    if before_agent_callback:
        agent.before_agent_callback = before_agent_callback

    logger.debug(
        f"Collector agent {agent_name} created with tools: {agent.tools} and prompt: {agent.instruction}"
    )
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


def create_targeted_collector_agent(task: RetrievalTask) -> Agent:
    """
    Create a targeted collector agent for a specific retrieval task.

    Args:
        task: RetrievalTask specifying the targeted collection parameters.

    Returns:
        Agent: Configured targeted collector agent.
    """
    return create_collector_agent(section_name=task.section, task_override=task)


def create_targeted_collector_agents(
    tasks: list[RetrievalTask],
    after_agent_callback: Callable[[CallbackContext], types.Content | None]
    | None = None,
) -> ParallelAgent:
    """
    Create a parallel agent with targeted collectors for the given tasks.

    Args:
        tasks: List of RetrievalTask objects.
        after_agent_callback: Optional callback to run after collectors complete.

    Returns:
        ParallelAgent with targeted collector agents.
    """
    if not tasks:
        return ParallelAgent(
            name="targeted_collectors_empty",
            sub_agents=[],
        )

    collector_agents = [create_targeted_collector_agent(task) for task in tasks]

    parallel_agent = ParallelAgent(
        name="targeted_collectors",
        sub_agents=collector_agents,
    )

    # Apply callback if provided
    if after_agent_callback:
        parallel_agent.after_agent_callback = after_agent_callback

    return parallel_agent
