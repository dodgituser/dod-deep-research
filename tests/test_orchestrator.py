"""Tests for orchestrator event-loop bridging behavior."""

from typing import Any

from dod_deep_research.pipeline import orchestrator


def test_run_pipeline_without_running_loop(monkeypatch: Any) -> None:
    """Runs pipeline with asyncio.run when no event loop is active."""

    async def fake_run_pipeline_async(**_: Any) -> str:
        return "ok-sync"

    monkeypatch.setattr(orchestrator, "run_pipeline_async", fake_run_pipeline_async)

    result = orchestrator.run_pipeline(indication="alz", drug_name="drug")

    assert result == "ok-sync"


async def test_run_pipeline_inside_running_loop(monkeypatch: Any) -> None:
    """Runs pipeline in a worker thread when already in an event loop."""

    async def fake_run_pipeline_async(**_: Any) -> str:
        return "ok-async"

    monkeypatch.setattr(orchestrator, "run_pipeline_async", fake_run_pipeline_async)

    result = orchestrator.run_pipeline(indication="alz", drug_name="drug")

    assert result == "ok-async"
