"""Parallel evidence collectors for map-reduce pipeline."""

from google.adk.agents import ParallelAgent

from dod_deep_research.agents.collector.agent import create_collector_agent
from dod_deep_research.agents.planner.schemas import get_common_sections

collector_agents = [
    create_collector_agent(section) for section in get_common_sections()
]

parallel_collectors = ParallelAgent(
    name="evidence_collectors",
    sub_agents=collector_agents,
)
