"""Shared utilities for agent callbacks."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def sanitize_agent_name(agent_name: str) -> str:
    """Sanitize agent name for filesystem paths."""
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in agent_name)


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


def log_agent_event(agent_name: str, callback_type: str, payload: Any) -> None:
    """
    Append a message to the per-agent log file.

    Args:
        agent_name (str): Agent name for log file naming.
        callback_type (str): Callback type used for the log file name.
        payload (Any): Payload to append as JSONL.
    """
    safe_name = sanitize_agent_name(agent_name or "unknown")
    safe_callback = sanitize_agent_name(callback_type or "unknown")
    logs_dir = (
        Path(__file__).resolve().parents[2] / "outputs" / "agent_logs" / safe_name
    )
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{safe_name}_callback_{safe_callback}.jsonl"
    timestamp = datetime.now().isoformat()
    if isinstance(payload, dict):
        entry = {"timestamp": timestamp, **payload}
    else:
        entry = {"timestamp": timestamp, "payload": payload}
    with log_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")
