"""Core utilities for deep research agent pipeline."""

import json
import logging
from typing import Any

from google.adk import runners
from google.adk.apps.app import App
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.genai import types
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def inline_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """
    Builds an ADK-compatible JSON schema by inlining $ref/$defs.

    Args:
        model (type[BaseModel]): Pydantic model to inline.

    Returns:
        dict[str, Any]: JSON schema with inline definitions.
    """
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref and ref.startswith("#/$defs/"):
                key = ref.split("/")[-1]
                resolved = defs.get(key, {})
                merged = {**resolved, **{k: v for k, v in node.items() if k != "$ref"}}
                return _resolve(merged)
            return {k: _resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    inlined = _resolve(schema)
    inlined.pop("$defs", None)
    return inlined


def _format_tool_payload(payload: dict, max_chars: int = 800) -> str:
    """Format tool payloads for logging with truncation."""
    try:
        text = json.dumps(payload, default=str)
    except TypeError:
        text = str(payload)
    if len(text) > max_chars:
        return f"{text[:max_chars]}...[truncated]"
    return text


def build_runner(
    agent: object,
    app_name: str,
) -> runners.InMemoryRunner:
    """
    Build an in-memory runner with the Reflect-and-Retry plugin.

    Args:
        agent: Root agent for the runner.
        app_name: Application name for the runner context.

    Returns:
        InMemoryRunner: Configured runner instance.
    """
    retry_plugin = ReflectAndRetryToolPlugin(max_retries=3)
    app_instance = App(
        name=app_name,
        root_agent=agent,
        plugins=[retry_plugin],
    )
    return runners.InMemoryRunner(app=app_instance)


async def run_agent(
    runner: runners.InMemoryRunner,
    user_id: str,
    session_id: str,
    new_message: types.Content,
) -> list[dict]:
    """
    Run an agent and collect JSON responses from events.

    Args:
        runner: The InMemoryRunner instance to use.
        user_id: User ID for the session.
        session_id: Session ID to run the agent in.
        new_message: The message to send to the agent.

    Returns:
        List of parsed JSON objects from final responses.
    """
    json_responses = []
    final_response_count: dict[str, int] = {}
    final_response_empty: dict[str, int] = {}

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        func_calls = event.get_function_calls()
        if func_calls:
            for call in func_calls:
                logger.info(
                    "Tool call: author=%s name=%s args=%s",
                    event.author,
                    call.name,
                    _format_tool_payload(call.args or {}),
                )

        func_responses = event.get_function_responses()
        if func_responses:
            for response in func_responses:
                response_payload = response.response or {}
                if isinstance(response_payload, dict) and response_payload.get("error"):
                    logger.warning(
                        "Tool error: author=%s name=%s error=%s",
                        event.author,
                        response.name,
                        _format_tool_payload(response_payload),
                    )
                else:
                    logger.info(
                        "Tool response: author=%s name=%s result=%s",
                        event.author,
                        response.name,
                        _format_tool_payload(response_payload),
                    )

        if not event.is_final_response():
            logger.debug(f"Received intermediate event from {event.author}")
            continue

        if event.content and event.content.parts:
            final_response_count[event.author] = (
                final_response_count.get(event.author, 0) + 1
            )
            saw_text = False
            for part in event.content.parts:
                if part.text:
                    saw_text = True
                    try:
                        parsed_json = json.loads(part.text)
                        logger.info(f"Parsed JSON response from agent '{event.author}'")
                        logger.debug(f"Parsed JSON: {parsed_json}")
                        json_responses.append(parsed_json)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse JSON from agent '{event.author}': {e}. "
                            f"Text preview: {part.text[:100]}..."
                        )
            if not saw_text:
                final_response_empty[event.author] = (
                    final_response_empty.get(event.author, 0) + 1
                )
                logger.warning(
                    f"Final response from agent '{event.author}' had no text parts."
                )
        else:
            final_response_empty[event.author] = (
                final_response_empty.get(event.author, 0) + 1
            )
            logger.warning(
                f"Final response from agent '{event.author}' had no text content."
            )

    if final_response_count:
        logger.info(f"Final responses by agent: {final_response_count}")
    if final_response_empty:
        logger.warning(f"Final responses without text by agent: {final_response_empty}")

    return json_responses


def get_output_file(indication: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    research_dir = Path(__file__).parent / "research"
    research_dir.mkdir(exist_ok=True)
    output_dir = research_dir / f"{indication}-{timestamp}"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"pipeline_events_{timestamp}.json"
    return output_file
