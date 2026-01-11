"""Test agents for functional testing, can plug and play for different agents to run adk web ui locally."""

import json
from pathlib import Path

from google.adk.agents.callback_context import CallbackContext

from dod_deep_research.agents.collector.agent import create_collector_agent

_STATE_PATH = Path(__file__).with_name("collector_state.json")


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


root_agent = create_collector_agent(
    "market_opportunity_analysis",
    before_agent_callback=_before_agent_callback,
)
