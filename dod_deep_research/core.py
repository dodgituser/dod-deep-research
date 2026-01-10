"""Core utilities for deep research agent pipeline."""

import json
import logging

from google.adk import runners
from google.adk.apps.app import App
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.genai import types
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


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
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        if not event.is_final_response():
            logger.debug(f"Received intermediate event from {event.author}")
            continue

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
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

    return json_responses


def get_output_file(indication: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    research_dir = Path(__file__).parent / "research"
    research_dir.mkdir(exist_ok=True)
    output_dir = research_dir / f"{indication}-{timestamp}"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"pipeline_events_{timestamp}.json"
    return output_file
