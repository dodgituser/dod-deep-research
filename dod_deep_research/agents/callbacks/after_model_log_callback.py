"""After-model callback that logs the model response."""

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse

from dod_deep_research.agents.callbacks.utils import (
    log_agent_event,
)


def after_model_log_callback(
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
    run_output_dir = callback_context.state.get("run_output_dir")
    output = llm_response.content.parts if llm_response.content else None
    final_text = output[0].text if output else ""
    log_agent_event(
        agent_name=agent_name,
        callback_type="response",
        payload={"payload": {"final_text": final_text}},
        run_output_dir=run_output_dir,
    )

    payload = {"payload": {"response": llm_response}}
    log_agent_event(
        agent_name,
        "after_model",
        payload,
        run_output_dir=run_output_dir,
    )
    return None
