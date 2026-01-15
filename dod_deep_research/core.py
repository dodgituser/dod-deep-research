"""Core utilities for deep research agent pipeline."""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from google.adk import runners
from google.adk.apps.app import App
from google.genai import types
from pydantic import BaseModel
from google.adk.events import Event, EventActions

from dod_deep_research.agents.plugins import get_default_plugins
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan


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
    Build an in-memory runner with default plugins.

    Args:
        agent: Root agent for the runner.
        app_name: Application name for the runner context.

    Returns:
        InMemoryRunner: Configured runner instance.
    """
    plugins = get_default_plugins()
    app_instance = App(
        name=app_name,
        root_agent=agent,
        plugins=plugins,
    )
    return runners.InMemoryRunner(app=app_instance)


async def run_agent(
    runner: runners.InMemoryRunner,
    user_id: str,
    session_id: str,
    new_message: types.Content,
) -> None:
    """
    Run an agent for a new message.

    Args:
        runner: The InMemoryRunner instance to use.
        user_id: User ID for the session.
        session_id: Session ID to run the agent in.
        new_message: The message to send to the agent.
    """
    logger.debug("Running agent for session %s", session_id)
    step_count = 0
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            step_count += 1

            # Log turn information
            calls = event.get_function_calls()
            responses = event.get_function_responses()

            log_msg = f"[Step {step_count}] Agent: {event.author}"
            if calls:
                log_msg += f" | Calls: {[c.name for c in calls]}"
            if responses:
                log_msg += f" | Responses: {[r.name for r in responses]}"
            if event.error_code:
                log_msg += f" | Error: {event.error_code}: {event.error_message}"

            logger.debug(log_msg)

    except Exception as e:
        logger.error(
            f"Agent execution failed in session {session_id} at step {step_count}: {str(e)}",
            exc_info=True,
        )
        raise e

    logger.debug(
        "Agent run complete for session %s after %d steps", session_id, step_count
    )


def get_output_path(indication: str) -> Path:
    """
    Create and return the output directory for a pipeline run.

    Args:
        indication (str): Indication name used to namespace outputs.

    Returns:
        Path: Path to the output directory for this run.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    outputs_dir = Path(__file__).parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    output_dir = outputs_dir / f"{indication}-{timestamp}"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def get_research_head_guidance(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Extract research head guidance per section from state.

    Args:
        state (dict[str, Any]): Pipeline state containing research_head_plan.

    Returns:
        dict[str, dict[str, Any]]: Section -> guidance payload.
    """
    plan_raw = state.get("research_head_plan")
    if not plan_raw:
        return {}

    plan = (
        plan_raw
        if isinstance(plan_raw, ResearchHeadPlan)
        else ResearchHeadPlan(**plan_raw)
    )
    logger.info("Sections with guidance: %s", [g.section for g in plan.guidance])

    guidance_map: dict[str, dict[str, Any]] = {}
    for guidance in plan.guidance:
        guidance_map[str(guidance.section)] = guidance.model_dump(exclude={"section"})
    return guidance_map


async def persist_section_plan_to_state(
    session_service: runners.InMemorySessionService,
    session: runners.Session,
) -> runners.Session:
    """
    Persist per-section research plan state to the session.

    Args:
        session_service (runners.InMemorySessionService): Session service for persistence.
        session (runners.Session): Session containing research plan state.

    Returns:
        runners.Session: Updated session after persisting section state.
    """
    research_plan = session.state.get("research_plan")
    if not research_plan:
        return session

    plan = ResearchPlan(**research_plan)
    section_state = {
        f"research_section_{section.name}": section.model_dump()
        for section in plan.sections
    }
    return await persist_state_delta(session_service, session, section_state)


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


async def persist_state_delta(
    session_service: runners.InMemorySessionService,
    session: runners.Session,
    state_delta: dict[str, Any],
) -> runners.Session:
    """
    Persist a state update by appending a system event. For a given session service we
    have a session in which we want to merge in a state delta.

    Args:
        session_service: Session service used to append events.
        session: Session to update.
        state_delta: State keys to merge into session state.

    Returns:
        runners.Session: Updated session with merged state.
    """
    if not state_delta:
        return session

    merge_event = Event(
        author="system",
        actions=EventActions(state_delta=state_delta),
    )
    await session_service.append_event(session, merge_event)
    return await session_service.get_session(
        app_name=session.app_name,
        user_id=session.user_id,
        session_id=session.id,
    )  # gets updated state
