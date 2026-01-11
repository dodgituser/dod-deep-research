"""Deep research sequential agent pipeline with map-reduce architecture."""

from google.adk.agents import SequentialAgent

from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.planner.agent import planner_agent
from dod_deep_research.agents.writer.agent import writer_agent
from dod_deep_research.agents.planner.schemas import get_common_sections


def get_pre_aggregation_agent() -> SequentialAgent:
    """
    Build the pre-aggregation pipeline (planner + collectors).

    Returns:
        SequentialAgent: Configured pre-aggregation agent.
    """
    return SequentialAgent(
        name="pre_aggregation_pipeline",
        sub_agents=[
            planner_agent,
            create_collector_agents(
                [section.value for section in get_common_sections()]
            ),
        ],
    )

# Iterative research loop is done in the deep_research.py file manually not leveraging ADK workflow agents.

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
