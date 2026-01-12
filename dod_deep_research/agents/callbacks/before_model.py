"""Before-model callback that logs the outbound prompt."""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse

from dod_deep_research.agents.callbacks.utils import (
    format_llm_request,
    format_payload,
    get_session_id,
    log_agent_event,
)


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    """
    Logs the outbound prompt before the model call.

    Args:
        callback_context (CallbackContext): Callback context with session data.
        llm_request (LlmRequest): LLM request containing prompt contents.

    Returns:
        types.LlmResponse | None: Returning a response skips the model call.
    """
    agent_name = callback_context.agent_name or "unknown"
    session_id = get_session_id(callback_context)
    payload = {
        "type": "before_model",
        "agent_name": agent_name,
        "payload": {"prompt": format_llm_request(llm_request)},
    }
    log_agent_event(session_id, agent_name, format_payload(payload))
    return None
