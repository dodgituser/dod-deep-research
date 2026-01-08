"""Factory for creating the research pipeline with dynamic collectors."""

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


def create_pipeline_with_collectors(section_names: list[str]) -> SequentialAgent:
    """
    Create research pipeline with collectors for specified sections.

    Args:
        section_names: List of section names to create collectors for.

    Returns:
        SequentialAgent: Configured research pipeline.
    """
    collector_agents = [create_collector_agent(section) for section in section_names]

    parallel_collectors = ParallelAgent(
        name="evidence_collectors",
        sub_agents=collector_agents,
    )

    return SequentialAgent(
        name="research_pipeline",
        sub_agents=[
            planner_agent,
            parallel_collectors,
            aggregator_agent,
            validator_agent,
            writer_agent,
        ],
    )


def create_default_pipeline() -> SequentialAgent:
    """
    Create research pipeline with collectors for common sections.

    Returns:
        SequentialAgent: Default research pipeline.
    """
    common_sections = [
        "epidemiology",
        "biomarkers",
        "mechanisms",
        "trials",
        "competitive_landscape",
    ]
    return create_pipeline_with_collectors(common_sections)
