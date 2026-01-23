"""Core utilities for deep research agent pipeline."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from google.adk import runners
from google.adk.apps.app import App
from google.genai import types
from pydantic import BaseModel
from google.adk.events import Event, EventActions

from dod_deep_research.agents.plugins import get_default_plugins
from dod_deep_research.agents.planner.schemas import ResearchPlan
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan


logger = logging.getLogger(__name__)


def get_validated_model(
    state: dict[str, Any], model_class: type[BaseModel], state_key: str
) -> BaseModel:
    """
    Extract and validate a Pydantic model from session state.
    Handles raw JSON strings (with optional markdown fences) or existing dicts/models.

    Args:
        state: The session state dictionary.
        model_class: The Pydantic model class to validate against.
        state_key: The key in the state to retrieve.

    Returns:
        BaseModel: An instance of the model_class.

    Raises:
        ValueError: If the key is missing or the payload is invalid.
    """
    raw_value = state.get(state_key)
    if not raw_value:
        raise ValueError(f"Missing structured output in state key: {state_key}")

    if isinstance(raw_value, model_class):
        return raw_value

    payload = raw_value
    if isinstance(payload, str):
        payload = extract_json_payload(payload)
        payload = json.loads(payload)

    return model_class.model_validate(payload)


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
            initial_delay=10,
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


def get_missing_output_keys(state: dict[str, Any], output_keys: list[str]) -> list[str]:
    """
    Return output keys that are missing or empty in state.

    Args:
        state: Session state dictionary.
        output_keys: Output keys expected to be populated.

    Returns:
        list[str]: Keys that are missing or empty.
    """
    missing: list[str] = []
    for key in output_keys:
        value = state.get(key)
        if value is None:
            missing.append(key)
            continue
        if isinstance(value, str):
            if not value.strip():
                missing.append(key)
        elif isinstance(value, (list, dict)):
            if not value:
                missing.append(key)
        else:
            if not value:
                missing.append(key)
    return missing


async def retry_missing_outputs(
    *,
    app_name: str,
    user_id: str,
    session: runners.Session,
    output_keys: list[str],
    build_agent: Callable[[list[str]], object],
    run_message: str,
    max_attempts: int = 2,
    log_label: str | None = None,
    agent_prefix: str | None = None,
) -> runners.Session:
    """
    Retry only the missing outputs by rebuilding an agent for the remaining keys.

    Args:
        app_name: App name for sessions.
        user_id: User ID for the session.
        session: The session after the initial run.
        output_keys: Expected output keys to check.
        build_agent: Callback that builds an agent for the missing keys.
        run_message: Prompt text for retries.
        max_attempts: Maximum retry attempts.

    Returns:
        runners.Session: Updated session after retries.
    """

    def _format_agent_names(keys: list[str]) -> list[str]:
        sections = [key.removeprefix("evidence_store_section_") for key in keys]
        if agent_prefix:
            return [f"{agent_prefix}{section}" for section in sections]
        return sections

    updated_session = session
    missing_keys = get_missing_output_keys(updated_session.state, output_keys)
    retry_attempts = 0
    if log_label:
        success_count = len(output_keys) - len(missing_keys)
        logger.info(
            "[%s] Attempt 0: %d/%d collectors succeeded",
            log_label,
            success_count,
            len(output_keys),
        )
    if missing_keys and log_label:
        logger.info(
            "[%s] Missing outputs: %s", log_label, _format_agent_names(missing_keys)
        )

    while missing_keys and retry_attempts < max_attempts:
        if log_label:
            logger.info(
                "[%s] Retry %d for: %s",
                log_label,
                retry_attempts + 1,
                _format_agent_names(missing_keys),
            )
        retry_agent = build_agent(missing_keys)
        retry_runner = build_runner(agent=retry_agent, app_name=app_name)
        retry_session = await retry_runner.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            state=updated_session.state.copy(),
        )
        await run_agent(
            retry_runner,
            retry_session.user_id,
            retry_session.id,
            types.Content(
                parts=[types.Part.from_text(text=run_message)],
                role="user",
            ),
            output_keys=missing_keys,
            max_retries=0,  # collector agents are not retried as that is done here
            log_attempts=False,
        )
        updated_session = await retry_runner.session_service.get_session(
            app_name=app_name,
            user_id=retry_session.user_id,
            session_id=retry_session.id,
        )
        previous_missing = set(missing_keys)
        missing_keys = get_missing_output_keys(updated_session.state, output_keys)
        recovered = previous_missing - set(missing_keys)
        if log_label:
            success_count = len(output_keys) - len(missing_keys)
            logger.info(
                "[%s] Attempt %d: %d/%d collectors succeeded",
                log_label,
                retry_attempts + 1,
                success_count,
                len(output_keys),
            )
        if recovered and log_label:
            logger.info(
                "[%s] Recovered outputs: %s",
                log_label,
                _format_agent_names(sorted(recovered)),
            )
        retry_attempts += 1
        if missing_keys and log_label:
            logger.info(
                "[%s] Still missing: %s",
                log_label,
                _format_agent_names(missing_keys),
            )

    if missing_keys and log_label:
        logger.warning(
            "[%s] Missing outputs after %d attempts: %s",
            log_label,
            retry_attempts,
            _format_agent_names(missing_keys),
        )

    return updated_session


async def run_agent(
    runner: runners.InMemoryRunner,
    user_id: str,
    session_id: str,
    new_message: types.Content,
    output_keys: str | list[str] | None = None,
    max_retries: int = 1,
    log_attempts: bool = True,
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
    keys = [output_keys] if isinstance(output_keys, str) else (output_keys or [])

    # NOTE: ADK does not provide a supported way to force an agent to continue
    # after a tool call; see https://github.com/google/adk-python/discussions/2508.
    # We use a lightweight retry with a generic "finalize" nudge when required
    # outputs are missing.
    attempt = 0
    while True:
        step_count = 0
        agent_step_counts: dict[str, int] = {}
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
            ):
                step_count += 1
                agent_step_counts[event.author] = (
                    agent_step_counts.get(event.author, 0) + 1
                )

                calls = event.get_function_calls()
                responses = event.get_function_responses()

                agent_step = agent_step_counts[event.author]
                if log_attempts:
                    log_msg = f"[Attempt {attempt + 1}][Step {agent_step}] Agent: {event.author}"
                else:
                    log_msg = f"[Step {agent_step}] Agent: {event.author}"
                if calls:
                    log_msg += f" | Calls: {[c.name for c in calls]}"
                if responses:
                    log_msg += f" | Responses: {[r.name for r in responses]}"
                if event.error_code:
                    log_msg += f" | Error: {event.error_code}: {event.error_message}"

                logger.info(log_msg)

        except Exception as e:
            attempt_label = attempt + 1 if log_attempts else attempt + 1
            logger.error(
                f"Agent execution failed in session {session_id} on attempt {attempt_label} at step {step_count}: {str(e)}",
                exc_info=True,
            )
            raise e

        if not keys:
            break

        session = await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if session and not get_missing_output_keys(session.state, list(keys)):
            if log_attempts:
                logger.info(
                    "Agent run complete for session %s (attempt %d) after %d steps",
                    session_id,
                    attempt + 1,
                    step_count,
                )
            break

        attempt += 1
        if attempt > max_retries and max_retries > 0:
            logger.error("Agent execution failed after %d attempts", max_retries)
            break

        new_message = types.Content(
            parts=[
                types.Part.from_text(
                    text="Finalize by outputting only the required JSON.",
                )
            ],
            role="user",
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


def extract_json_payload(raw_text: str) -> str:
    """
    Extract a JSON payload from text that may include prose or fenced code.

    Args:
        raw_text (str): Raw text possibly containing a JSON block.

    Returns:
        str: Extracted JSON payload as a string.
    """
    text = raw_text.strip()
    if not text:
        return text

    fence_start = text.find("```")
    if fence_start != -1:
        fence_end = text.find("```", fence_start + 3)
        if fence_end != -1:
            fenced = text[fence_start + 3 : fence_end]
            return fenced.strip().removeprefix("json").strip()

    first_brace = -1
    brace_candidates = [text.find("{"), text.find("[")]
    brace_candidates = [pos for pos in brace_candidates if pos != -1]
    if brace_candidates:
        first_brace = min(brace_candidates)

    if first_brace != -1:
        last_brace = max(text.rfind("}"), text.rfind("]"))
        if last_brace != -1 and last_brace >= first_brace:
            return text[first_brace : last_brace + 1].strip()
        return text[first_brace:].strip()

    return text


def merge_research_head_plans(state: dict[str, Any]) -> ResearchHeadPlan | None:
    """
    Merge quantitative and qualitative research head plans from state.

    Args:
        state (dict[str, Any]): Pipeline state containing research head plans.

    Returns:
        ResearchHeadPlan | None: Merged plan, or None if no guidance exists.
    """
    quant_raw = state.get("research_head_quant_plan")
    qual_raw = state.get("research_head_qual_plan")

    quant_plan = (
        quant_raw
        if isinstance(quant_raw, ResearchHeadPlan)
        else ResearchHeadPlan(**quant_raw)
        if quant_raw
        else ResearchHeadPlan()
    )
    qual_plan = (
        qual_raw
        if isinstance(qual_raw, ResearchHeadPlan)
        else ResearchHeadPlan(**qual_raw)
        if qual_raw
        else ResearchHeadPlan()
    )

    merged_guidance = [*quant_plan.guidance, *qual_plan.guidance]
    if not merged_guidance:
        return None

    return ResearchHeadPlan(guidance=merged_guidance)


def get_research_head_guidance(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Extract research head guidance per section from state.

    Args:
        state (dict[str, Any]): Pipeline state containing research head plans.

    Returns:
        dict[str, dict[str, Any]]: Section -> guidance payload.
    """
    plan = merge_research_head_plans(state)
    if not plan:
        return {}

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
