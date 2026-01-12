"""Deep research sequential agent pipeline with map-reduce architecture."""

from google.adk import Agent

from google.adk.agents import SequentialAgent

from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.planner.agent import planner_agent
from dod_deep_research.agents.writer.agent import writer_agent
from dod_deep_research.agents.planner.schemas import get_common_sections
from dod_deep_research.agents.evidence import aggregate_evidence_after_collectors


def get_pre_aggregation_agent(planner: Agent | None = None) -> SequentialAgent:
    """
    Build the pre-aggregation pipeline (planner + collectors).

    Returns:
        SequentialAgent: Configured pre-aggregation agent.
    """
    planner_agent_to_use = planner or planner_agent
    return SequentialAgent(
        name="pre_aggregation_pipeline",
        sub_agents=[
            planner_agent_to_use,
            create_collector_agents(
                [section.value for section in get_common_sections()],
                after_agent_callback=aggregate_evidence_after_collectors,
            ),
        ],
    )


# Iterative research loop is done in the deep_research.py file manually not leveraging ADK workflow agents.


# TODO: Currently we only have one writer agent, but in the future we may have multiple agents as apart of the post-aggregation pipeline.
def get_post_aggregation_agent() -> SequentialAgent:
    """
    Build the post-aggregation pipeline (writer).

    Returns:
        SequentialAgent: Configured post-aggregation agent.
    """
    return SequentialAgent(
        name="post_aggregation_pipeline",
        sub_agents=[
            writer_agent,
        ],
    )
