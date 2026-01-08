"""Deep research sequential agent pipeline with map-reduce architecture."""

from google.adk.agents import ParallelAgent, SequentialAgent

from dod_deep_research.agents.aggregator.aggregator_agent import (
    root_agent as aggregator_agent,
)
from dod_deep_research.agents.collector.collector_agent import create_collector_agent
from dod_deep_research.agents.planner.planner_agent import root_agent as planner_agent
from dod_deep_research.agents.validator.validator_agent import (
    root_agent as validator_agent,
)
from dod_deep_research.agents.writer.writer_agent import root_agent as writer_agent

common_sections = [
    "epidemiology",
    "biomarkers",
    "mechanisms",
    "trials",
    "competitive_landscape",
]

collector_agents = [create_collector_agent(section) for section in common_sections]

parallel_collectors = ParallelAgent(
    name="evidence_collectors",
    sub_agents=collector_agents,
)

root_agent = SequentialAgent(
    name="research_pipeline",
    sub_agents=[
        planner_agent,
        parallel_collectors,
        aggregator_agent,
        validator_agent,
        writer_agent,
    ],
)
