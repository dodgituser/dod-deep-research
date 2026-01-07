import logging
from pathlib import Path

from google.adk.agents import SequentialAgent
from dod_deep_research.agents.planner.agent import root_agent as planner_agent
from dod_deep_research.agents.retriever.agent import root_agent as retriever_agent
from dod_deep_research.agents.validator.agent import root_agent as validator_agent
from dod_deep_research.agents.writer.agent import root_agent as writer_agent
from dod_deep_research.prompts import list_all, resolve
from dod_deep_research.schemas import DeepResearchOutput

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(prompt_arg: str, **kwargs) -> str:
    """Load prompt from registry, file, or return as-is."""
    return resolve(prompt_arg, **kwargs)


def list_prompts() -> list[str]:
    """List all registered prompts."""
    return list_all()


sequential_agent = SequentialAgent(
    name="research_pipeline",
    sub_agents=[
        planner_agent,
        retriever_agent,
        validator_agent,
        writer_agent,
    ],
)


def run_pipeline(indication: str, **kwargs) -> DeepResearchOutput:
    """
    Run the sequential agent pipeline for deep research.

    Args:
        indication: The disease indication to research.
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        DeepResearchOutput: The structured research output.
    """
    response = sequential_agent.run(indication, **kwargs)

    deep_research_output_dict = response.state.get("deep_research_output")
    if deep_research_output_dict is None:
        raise ValueError("Pipeline did not produce deep_research_output in state")

    return DeepResearchOutput.model_validate(deep_research_output_dict)
