"""Evaluation utilities for the deep research pipeline."""

import json
from pathlib import Path
from typing import Any


def _compute_tool_call_success_rates(
    agent_logs_dir: Path,
) -> dict[str, dict[str, float | int]]:
    """
    Compute per-agent tool call success rates from after_tool logs.

    Args:
        agent_logs_dir (Path): Path to outputs/agent_logs.

    Returns:
        dict[str, dict[str, float | int]]: Per-agent metrics.
    """
    results: dict[str, dict[str, float | int]] = {}
    if not agent_logs_dir.exists():
        return results

    for agent_dir in sorted(path for path in agent_logs_dir.iterdir() if path.is_dir()):
        total = 0
        success = 0
        for log_path in agent_dir.glob("*_callback_after_tool.jsonl"):
            for line in log_path.read_text().splitlines():
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = entry.get("payload") if isinstance(entry, dict) else None
                if not isinstance(payload, dict):
                    continue
                tool_response = payload.get("tool_response")
                if not isinstance(tool_response, dict):
                    continue
                total += 1
                if tool_response.get("isError") is True:
                    continue
                success += 1
        if total:
            results[agent_dir.name] = {
                "total": total,
                "success": success,
                "success_rate": round(success / total, 4),
            }
    return results


def _compute_agent_iterations(agent_logs_dir: Path) -> dict[str, int]:
    """
    Count per-targeted-collector iteration entries from after_agent logs.

    Args:
        agent_logs_dir (Path): Path to outputs/agent_logs.

    Returns:
        dict[str, int]: Per-targeted-collector iteration counts.
    """
    results: dict[str, int] = {}
    if not agent_logs_dir.exists():
        return results

    for agent_dir in sorted(path for path in agent_logs_dir.iterdir() if path.is_dir()):
        if not agent_dir.name.startswith("targeted_collector_"):
            continue
        count = 0
        after_agent_logs = list(agent_dir.glob("*_callback_after_agent.jsonl"))
        if after_agent_logs:
            for log_path in after_agent_logs:
                count += sum(1 for _ in log_path.read_text().splitlines())
        else:
            for log_path in agent_dir.glob("*_callback_before_agent.jsonl"):
                count += sum(1 for _ in log_path.read_text().splitlines())
        if count:
            results[agent_dir.name] = count
    return results


def _compute_source_diversity(
    evidence_store: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Compute source diversity metrics from evidence store.

    Args:
        evidence_store (dict[str, Any] | None): Evidence store payload.

    Returns:
        dict[str, Any]: Source diversity metrics.
    """
    if not evidence_store:
        return {"overall_unique_sources": 0, "per_section": {}}

    items = evidence_store.get("items", [])
    per_section: dict[str, set[str]] = {}
    overall_sources: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        section = item.get("section")
        if not source or not section:
            continue
        overall_sources.add(source)
        per_section.setdefault(section, set()).add(source)

    per_section_counts = {
        section: len(sources) for section, sources in per_section.items()
    }
    return {
        "overall_unique_sources": len(overall_sources),
        "per_section": per_section_counts,
    }


def pipeline_eval(
    agent_logs_dir: Path,
    evidence_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build pipeline eval metrics from agent logs.

    Args:
        agent_logs_dir (Path): Path to outputs/agent_logs.
        evidence_store (dict[str, Any] | None): Evidence store payload.

    Returns:
        dict[str, Any]: Evaluation metrics.
    """
    return {
        "tool_call_success_rate": _compute_tool_call_success_rates(agent_logs_dir),
        "agent_iterations": _compute_agent_iterations(agent_logs_dir),
        "source_diversity": _compute_source_diversity(evidence_store),
    }
