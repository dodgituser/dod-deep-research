"""Before-model callback that logs the outbound prompt."""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse

from dod_deep_research.agents.callbacks.utils import log_agent_event


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
    payload = {"type": "before_model", "payload": {"prompt": llm_request}}
    log_agent_event(agent_name, "before_model", payload)
    return None
