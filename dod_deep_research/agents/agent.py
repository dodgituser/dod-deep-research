"""Deep research sequential agent pipeline."""

from google.adk.agents import SequentialAgent

from dod_deep_research.agents.planner.agent import root_agent as planner_agent
from dod_deep_research.agents.retriever.agent import root_agent as retriever_agent
from dod_deep_research.agents.validator.agent import root_agent as validator_agent
from dod_deep_research.agents.writer.agent import root_agent as writer_agent

root_agent = SequentialAgent(
    name="research_pipeline",
    sub_agents=[
        planner_agent,
        retriever_agent,
        validator_agent,
        writer_agent,
    ],
)
