"""Tests for mandatory local + GCS output persistence."""

from pathlib import Path

import pytest

from dod_deep_research.utils import persistence


class _FakeBlob:
    """Test blob object that records upload calls."""

    def __init__(self, name: str, fail_object: str | None, calls: list[str]) -> None:
        self._name = name
        self._fail_object = fail_object
        self._calls = calls

    def upload_from_filename(self, filename: str) -> None:
        self._calls.append(f"{self._name}::{filename}")
        if self._fail_object and self._name == self._fail_object:
            raise RuntimeError("forced upload failure")


class _FakeBucket:
    """Test bucket object that returns fake blobs."""

    def __init__(self, fail_object: str | None, calls: list[str]) -> None:
        self._fail_object = fail_object
        self._calls = calls

    def blob(self, object_name: str) -> _FakeBlob:
        return _FakeBlob(
            name=object_name,
            fail_object=self._fail_object,
            calls=self._calls,
        )


class _FakeClient:
    """Test storage client that serves a fake bucket."""

    def __init__(self, fail_object: str | None, calls: list[str]) -> None:
        self._fail_object = fail_object
        self._calls = calls

    def bucket(self, _bucket_name: str) -> _FakeBucket:
        return _FakeBucket(fail_object=self._fail_object, calls=self._calls)


def _create_outputs_tree(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    outputs_root = tmp_path / "outputs"
    output_dir = outputs_root / "alz-drug" / "20260213_120000_ab12cd34"
    output_dir.mkdir(parents=True)
    report_path = output_dir / "report.md"
    state_file = output_dir / "session_state.json"
    evals_file = output_dir / "pipeline_evals.json"
    report_path.write_text("# Report\n")
    state_file.write_text("{}\n")
    evals_file.write_text("{}\n")

    log_dir = output_dir / "agent_logs" / "planner_agent"
    log_dir.mkdir(parents=True)
    (log_dir / "planner_agent_callback_after_agent.jsonl").write_text("{}\n")

    return output_dir, report_path, state_file, evals_file


def test_persist_output_artifacts_uploads_with_mirrored_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir, report_path, state_file, evals_file = _create_outputs_tree(tmp_path)
    upload_calls: list[str] = []

    monkeypatch.setattr(
        persistence.storage,
        "Client",
        lambda: _FakeClient(fail_object=None, calls=upload_calls),
    )

    persisted = persistence.persist_output_artifacts(
        output_dir=output_dir,
        report_path=report_path,
        state_file=state_file,
        evals_file=evals_file,
    )

    uploaded_object_names = [call.split("::", maxsplit=1)[0] for call in upload_calls]
    assert "alz-drug/20260213_120000_ab12cd34/report.md" in uploaded_object_names
    assert (
        "alz-drug/20260213_120000_ab12cd34/session_state.json"
        in uploaded_object_names
    )
    assert (
        "alz-drug/20260213_120000_ab12cd34/pipeline_evals.json"
        in uploaded_object_names
    )
    assert (
        "alz-drug/20260213_120000_ab12cd34/agent_logs/planner_agent/planner_agent_callback_after_agent.jsonl"
        in uploaded_object_names
    )
    assert len(persisted.artifacts) == len(upload_calls)


def test_persist_output_artifacts_fails_run_on_any_upload_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir, report_path, state_file, evals_file = _create_outputs_tree(tmp_path)
    upload_calls: list[str] = []

    monkeypatch.setattr(
        persistence.storage,
        "Client",
        lambda: _FakeClient(
            fail_object="alz-drug/20260213_120000_ab12cd34/session_state.json",
            calls=upload_calls,
        ),
    )

    with pytest.raises(RuntimeError, match="GCS upload failed"):
        persistence.persist_output_artifacts(
            output_dir=output_dir,
            report_path=report_path,
            state_file=state_file,
            evals_file=evals_file,
        )
