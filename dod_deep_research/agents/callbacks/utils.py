"""Shared utilities for agent callbacks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from google.adk.models import LlmRequest


def sanitize_agent_name(agent_name: str) -> str:
    """Sanitize agent name for filesystem paths."""
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in agent_name)


def get_session_id(callback_context: Any) -> str:
    """
    Best-effort extraction of session id from callback context.

    Args:
        callback_context (Any): Callback context with session data.

    Returns:
        str: Session id if available, otherwise "unknown".
    """
    session_id = getattr(callback_context, "session_id", None)
    if session_id:
        return str(session_id)
    session = getattr(callback_context, "session", None)
    if session:
        for attr in ("id", "session_id"):
            value = getattr(session, attr, None)
            if value:
                return str(value)
    state = getattr(callback_context, "state", None)
    if state:
        for key in ("session_id", "id"):
            try:
                value = state.get(key) if isinstance(state, dict) else state[key]
            except Exception:
                value = None
            if value:
                return str(value)
    return "unknown"


def format_state(state: Any) -> str:
    """
    Format state into JSON with truncation.

    Args:
        state (Any): State payload to serialize.

    Returns:
        str: Serialized state string.
    """
    payload = state
    if hasattr(state, "to_dict"):
        payload = state.to_dict()
    try:
        text = json.dumps(payload, default=str)
    except TypeError:
        text = str(payload)
    return text


def log_agent_event(session_id: str, agent_name: str, message: str) -> None:
    """
    Append a message to the per-agent log file.

    Args:
        session_id (str): Session identifier.
        agent_name (str): Agent name for log file naming.
        message (str): Message to append.
    """
    logs_dir = Path(__file__).resolve().parents[2] / "research" / "agent_logs"
    logs_dir.mkdir(exist_ok=True)
    safe_name = sanitize_agent_name(agent_name or "unknown")
    log_path = logs_dir / f"{session_id}_{safe_name}.log"
    timestamp = datetime.now().isoformat()
    with log_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def format_llm_request(llm_request: LlmRequest) -> str:
    """
    Format LLM request contents into role/parts text.

    Args:
        llm_request (LlmRequest): LLM request containing prompt contents.

    Returns:
        str: Rendered prompt text.
    """
    contents = getattr(llm_request, "contents", None)
    if not contents:
        return str(llm_request)

    chunks = []
    for content in contents:
        role = getattr(content, "role", "unknown")
        parts = getattr(content, "parts", []) or []
        part_texts = []
        for part in parts:
            text = getattr(part, "text", None)
            part_texts.append(text if text is not None else str(part))
        body = "\n".join(part_texts).strip()
        chunks.append(f"{role}:\n{body}" if body else f"{role}:")

    return "\n\n".join(chunks)


def format_payload(payload: Any) -> str:
    """
    Format payloads as JSON when possible.

    Args:
        payload (Any): Payload to serialize.

    Returns:
        str: Serialized payload string.
    """
    try:
        return json.dumps(payload, default=str)
    except TypeError:
        return str(payload)


def get_callbacks() -> dict[str, Any]:
    """
    Return callbacks keyed by their agent attribute name.

    Returns:
        dict[str, Any]: Callback name to function mapping.
    """
    from dod_deep_research.agents.callbacks.after_agent import after_agent_callback
    from dod_deep_research.agents.callbacks.after_model import after_model_callback
    from dod_deep_research.agents.callbacks.after_tool import after_tool_callback
    from dod_deep_research.agents.callbacks.before_agent import before_agent_callback
    from dod_deep_research.agents.callbacks.before_model import before_model_callback
    from dod_deep_research.agents.callbacks.before_tool import before_tool_callback

    return {
        "before_agent_callback": before_agent_callback,
        "after_agent_callback": after_agent_callback,
        "before_model_callback": before_model_callback,
        "after_model_callback": after_model_callback,
        "before_tool_callback": before_tool_callback,
        "after_tool_callback": after_tool_callback,
    }
