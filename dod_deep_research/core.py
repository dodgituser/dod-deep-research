"""Core utilities for deep research agent pipeline."""

import json
import logging
import shutil
from typing import Any

from google.adk import runners
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.events import Event, EventActions
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.genai import types
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer

from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.models import GeminiModels


logger = logging.getLogger(__name__)


def normalize_aliases(values: list[str] | None) -> list[str] | None:
    """
    Normalize and deduplicate alias strings.

    Args:
        values: Alias strings (often from repeatable CLI options).

    Returns:
        list[str] | None: Deduplicated list of aliases, or None if empty.
    """
    if not values:
        return None

    seen: set[str] = set()
    aliases: list[str] = []
    for value in values:
        alias = value.strip()
        if not alias:
            continue
        key = alias.casefold()
        if key in seen:
            continue
        seen.add(key)
        aliases.append(alias)

    return aliases or None


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


def get_http_options() -> types.HttpOptions:
    """
    Build shared HTTP options for model retries.

    Returns:
        types.HttpOptions: HTTP options with retry configuration.
    """
    return types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            initial_delay=25,
            attempts=5,
        ),
    )


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
    LLMSummarizer = LlmEventSummarizer(
        llm=GeminiModels.GEMINI_PRO_2_0,
    )
    events_compaction_config = EventsCompactionConfig(
        compaction_interval=8,
        overlap_size=3,
        summarizer=LLMSummarizer,
    )
    context_cache_config = ContextCacheConfig(
        min_tokens=2048,
        ttl_seconds=600,
        cache_intervals=5,
    )
    retry_plugin = ReflectAndRetryToolPlugin(max_retries=3)
    app_instance = App(
        name=app_name,
        root_agent=agent,
        plugins=[retry_plugin],
        events_compaction_config=events_compaction_config,
        context_cache_config=context_cache_config,
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
            continue

        if not (event.content and event.content.parts):
            continue

        for part in event.content.parts:
            if not part.text:
                continue
            try:
                parsed_json = json.loads(part.text)
            except json.JSONDecodeError:
                continue
            json_responses.append(parsed_json)

    return json_responses


def get_output_file(indication: str):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outputs_dir = Path(__file__).parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    output_dir = outputs_dir / f"{indication}-{timestamp}"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"pipeline_events_{timestamp}.json"
    return output_file


def prepare_outputs_dir() -> Path:
    """
    Create the outputs directory and clear any existing run subdirectories.

    Returns:
        Path: Path to the outputs directory.
    """
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    for entry in outputs_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
    return outputs_dir


async def persist_research_sections(
    session_service: runners.InMemorySessionService,
    session: runners.Session,
    research_plan: dict[str, Any],
) -> runners.Session:
    """
    Persist per-section state derived from the research plan.

    Args:
        session_service: Session service used to append events.
        session: Session to update.
        research_plan: Research plan dict from state.

    Returns:
        runners.Session: Updated session with research_section_* keys.
    """
    plan = ResearchPlan(**research_plan)
    section_state = {
        f"research_section_{section.name}": section.model_dump()
        for section in plan.sections
    }
    if not section_state:
        return session

    merge_event = Event(
        author="system",
        actions=EventActions(state_delta=section_state),
    )
    await session_service.append_event(session, merge_event)
    return await session_service.get_session(
        app_name=session.app_name,
        user_id=session.user_id,
        session_id=session.id,
    )
