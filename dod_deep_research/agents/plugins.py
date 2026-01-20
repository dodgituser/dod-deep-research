"""Shared plugins for ADK runners."""

from typing import Any

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.plugins import BasePlugin, ReflectAndRetryToolPlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from dod_deep_research.agents.callbacks.after_agent_log_callback import (
    after_agent_log_callback,
)
from dod_deep_research.agents.callbacks.after_model_log_callback import (
    after_model_log_callback,
)
from dod_deep_research.agents.callbacks.after_tool_log_callback import (
    after_tool_log_callback,
)
from dod_deep_research.agents.callbacks.clinical_trials_tool_callback import (
    after_clinical_trials_tool_callback,
    before_clinical_trials_tool_callback,
)
from dod_deep_research.agents.callbacks.before_agent_log_callback import (
    before_agent_log_callback,
)
from dod_deep_research.agents.callbacks.before_model_log_callback import (
    before_model_log_callback,
)
from dod_deep_research.agents.callbacks.before_tool_log_callback import (
    before_tool_log_callback,
)


class AgentLoggingPlugin(BasePlugin):
    """
    Logs agent, model, and tool lifecycle events using the shared callbacks.

    Args:
        name (str): Unique identifier for the plugin instance.
    """

    def __init__(self, name: str = "agent_logging_plugin"):
        """
        Initialize the logging plugin.

        Args:
            name (str): Unique identifier for the plugin instance.

        Returns:
            None
        """
        super().__init__(name=name)

    async def before_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> types.Content | None:
        """
        Delegate to the before-agent logging callback.

        Args:
            agent (BaseAgent): Agent about to execute.
            callback_context (CallbackContext): Callback context containing state.

        Returns:
            types.Content | None: Returning content skips the agent run.
        """
        return before_agent_log_callback(callback_context)

    async def after_agent_callback(
        self, *, agent: BaseAgent, callback_context: CallbackContext
    ) -> types.Content | None:
        """
        Delegate to the after-agent logging callback.

        Args:
            agent (BaseAgent): Agent that finished executing.
            callback_context (CallbackContext): Callback context containing state.

        Returns:
            types.Content | None: Returning content replaces the agent response.
        """
        return after_agent_log_callback(callback_context)

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        """
        Delegate to the before-model logging callback.

        Args:
            callback_context (CallbackContext): Callback context containing session data.
            llm_request (LlmRequest): Model request payload.

        Returns:
            LlmResponse | None: Returning a response skips the model call.
        """
        return before_model_log_callback(callback_context, llm_request)

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        """
        Delegate to the after-model logging callback.

        Args:
            callback_context (CallbackContext): Callback context containing session data.
            llm_response (LlmResponse): Model response payload.

        Returns:
            LlmResponse | None: Returning a response replaces the model response.
        """
        return after_model_log_callback(callback_context, llm_response)

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> dict[str, Any] | None:
        """
        Delegate to the before-tool logging callback.

        Args:
            tool (BaseTool): Tool instance being invoked.
            tool_args (dict[str, Any]): Arguments passed to the tool.
            tool_context (ToolContext): Tool execution context.

        Returns:
            dict[str, Any] | None: Returning a dict skips tool execution.
        """
        modifier_response = before_clinical_trials_tool_callback(
            tool, tool_args, tool_context
        )
        if modifier_response is not None:
            return modifier_response
        return before_tool_log_callback(tool, tool_args, tool_context)

    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict,
    ) -> dict | None:
        """
        Delegate to the after-tool logging callback.

        Args:
            tool (BaseTool): Tool instance that ran.
            tool_args (dict[str, Any]): Arguments passed to the tool.
            tool_context (ToolContext): Tool execution context.
            result (dict): Tool response payload.

        Returns:
            dict | None: Returning a dict replaces the tool response.
        """
        modified_response = after_clinical_trials_tool_callback(
            tool, result, tool_context
        )
        if modified_response is not None:
            result = modified_response
        return after_tool_log_callback(
            tool=tool,
            tool_response=result,
            tool_context=tool_context,
            args=tool_args,
        )


def get_default_plugins() -> list[BasePlugin]:
    """
    Return the default plugins used by the runner.

    Returns:
        list[BasePlugin]: Instantiated plugin list.
    """
    return [
        AgentLoggingPlugin(),
        ReflectAndRetryToolPlugin(max_retries=3),
    ]
