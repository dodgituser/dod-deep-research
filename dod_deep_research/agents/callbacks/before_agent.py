"""Before-agent callback that logs session state."""

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from dod_deep_research.agents.callbacks.utils import (
    format_state,
    get_session_id,
    log_agent_event,
)


def before_agent_callback(callback_context: CallbackContext) -> types.Content | None:
    """
    Logs session state before an agent run.

    Args:
        callback_context (CallbackContext): Callback context with agent and session data.

    Returns:
        types.Content | None: Returning content skips the agent's run; None proceeds.
    """
    agent_name = callback_context.agent_name or "unknown"
    session_id = get_session_id(callback_context)
    payload = {
        "type": "before_agent",
        "agent_name": agent_name,
        "payload": {"state": callback_context.state},
    }
    log_agent_event(session_id, agent_name, format_state(payload))
    return None
