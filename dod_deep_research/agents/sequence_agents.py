"""Deep research sequential agent pipeline with map-reduce architecture."""

from google.adk.agents import SequentialAgent

from dod_deep_research.agents.parellelize_agents import parallel_collectors
from dod_deep_research.agents.planner.agent import planner_agent
from dod_deep_research.agents.writer.agent import writer_agent

pre_aggregation_agent = SequentialAgent(
    name="pre_aggregation_pipeline",
    sub_agents=[
        planner_agent,
        parallel_collectors,
    ],
)

post_aggregation_agent = SequentialAgent(
    name="post_aggregation_pipeline",
    sub_agents=[
        writer_agent,
    ],
)
