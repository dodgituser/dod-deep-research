"""Deep research sequential agent pipeline with map-reduce architecture."""

from google.adk.agents import SequentialAgent

from dod_deep_research.agents.collector.agent import create_collector_agents
from dod_deep_research.agents.planner.agent import planner_agent
from dod_deep_research.agents.writer.agent import writer_agent
from dod_deep_research.agents.planner.schemas import get_common_sections


# Pre-aggregation pipeline - Plan and collect evidence
pre_aggregation_agent = SequentialAgent(
    name="pre_aggregation_pipeline",
    sub_agents=[
        planner_agent,
        create_collector_agents([section.value for section in get_common_sections()]),
    ],
)

# Post-aggregation pipeline - Write evidence
post_aggregation_agent = SequentialAgent(
    name="post_aggregation_pipeline",
    sub_agents=[
        writer_agent,
    ],
)
