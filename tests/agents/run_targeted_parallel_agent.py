"""Run the targeted ParallelAgent via core runner utilities."""

import asyncio
import json
from pathlib import Path

from google.adk.agents import ParallelAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from dotenv import load_dotenv

from dod_deep_research.agents.callbacks.update_evidence import update_evidence
from dod_deep_research.agents.collector.agent import (
    create_targeted_collector_agent,
)
from dod_deep_research.agents.schemas import CommonSection
from dod_deep_research.core import build_runner, run_agent
from dod_deep_research.utils.evidence import GapTask
from dod_deep_research.loggy import setup_logging

setup_logging()


_STATE_PATH = Path(__file__).with_name("targeted_parallel_state.json")
load_dotenv()


def _before_agent_callback(callback_context: CallbackContext) -> None:
    state = json.loads(_STATE_PATH.read_text())
    if hasattr(callback_context, "state"):
        callback_context.state.update(state)
        return None
    if hasattr(callback_context, "session") and hasattr(
        callback_context.session, "state"
    ):
        callback_context.session.state.update(state)
    return None


_GAP_TASKS = [
    GapTask(
        section=CommonSection.DISEASE_OVERVIEW,
        missing_questions=[
            "How is Alzheimer's disease diagnosed, and what are the commonly used screening procedures and tests?",
        ],
        min_evidence=1,
    ),
    GapTask(
        section=CommonSection.CLINICAL_TRIALS_ANALYSIS,
        missing_questions=[
            "What completed clinical trials have evaluated IL-2 in Alzheimer's disease?",
        ],
        min_evidence=1,
    ),
]


_GUIDANCE_MAP = {
    "disease_overview": {
        "notes": "Focus on diagnostic criteria and screening procedures.",
        "suggested_queries": [
            "Alzheimer's disease diagnostic criteria",
            "Alzheimer's disease screening tests",
        ],
    },
    "clinical_trials_analysis": {
        "notes": "Focus on IL-2 or Aldesleukin trials in Alzheimer's disease.",
        "suggested_queries": [
            "IL-2 Alzheimer's disease clinical trials",
            "Aldesleukin Alzheimer's disease trial",
        ],
    },
}

_TARGETED_AGENTS = [
    create_targeted_collector_agent(
        gap,
        guidance=_GUIDANCE_MAP.get(str(gap.section)),
        test_local=False,
    )
    for gap in _GAP_TASKS
]

agent = ParallelAgent(
    name="targeted_collectors",
    sub_agents=_TARGETED_AGENTS,
    after_agent_callback=update_evidence,
)

agent.before_agent_callback = _before_agent_callback


def main() -> None:
    """
    Run the targeted parallel collector agent using the core runner.

    Args:
        None

    Returns:
        None
    """
    runner = build_runner(agent=agent, app_name="tests_targeted_parallel")
    session = asyncio.run(
        runner.session_service.create_session(
            app_name="tests_targeted_parallel",
            user_id="test_user",
            state={},
        )
    )
    message = types.Content(
        parts=[types.Part.from_text(text="Collect evidence for tasks.")],
        role="user",
    )
    asyncio.run(run_agent(runner, session.user_id, session.id, message))


if __name__ == "__main__":
    main()
