"""Before-agent callback that logs session state."""

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from dod_deep_research.agents.callbacks.utils import format_state, log_agent_event


def before_agent_log_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """
    Logs session state before an agent run.

    Args:
        callback_context (CallbackContext): Callback context with agent and session data.

    Returns:
        types.Content | None: Returning content skips the agent's run; None proceeds.
    """
    agent_name = callback_context.agent_name or "unknown"
    payload = {"payload": {"state": format_state(callback_context.state)}}
    run_output_dir = callback_context.state.get("run_output_dir")
    log_agent_event(agent_name, "before_agent", payload, run_output_dir=run_output_dir)
    return None
