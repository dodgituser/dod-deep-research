"""After-model callback that logs the model response."""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse

from dod_deep_research.agents.callbacks.utils import (
    log_agent_event,
)


def after_model_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    """
    Logs the model response after the model call.

    Args:
        callback_context (CallbackContext): Callback context with session data.
        llm_response (LlmResponse): Model response payload.

    Returns:
        LlmResponse | None: Returning a response replaces the model response.
    """
    agent_name = callback_context.agent_name or "unknown"
    payload = {"payload": {"response": llm_response}}
    log_agent_event(agent_name, "after_model", payload)
    return None
