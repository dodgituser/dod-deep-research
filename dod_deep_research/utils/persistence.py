"""Persistence helpers for local artifact validation and GCS uploads."""

from pathlib import Path

from google.cloud import storage
from pydantic import BaseModel, Field


OUTPUTS_BUCKET_NAME = "dod-deep-research-outputs"


class PersistedArtifact(BaseModel):
    """Represents an uploaded artifact and its storage locations."""

    local_path: str = Field(..., description="Absolute local file path.")
    gcs_uri: str = Field(..., description="GCS URI for the uploaded file.")


class PersistedArtifacts(BaseModel):
    """Container for persisted artifacts."""

    bucket_name: str = Field(..., description="Target GCS bucket.")
    artifacts: list[PersistedArtifact] = Field(
        default_factory=list,
        description="Uploaded artifact records.",
    )


def _collect_artifact_paths(
    output_dir: Path,
    report_path: Path | None,
    state_file: Path,
    evals_file: Path,
) -> list[Path]:
    """Collects files to upload to GCS."""
    required_files = [state_file, evals_file]
    missing_required = [path for path in required_files if not path.exists()]
    if missing_required:
        missing = ", ".join(str(path) for path in missing_required)
        raise FileNotFoundError(f"Missing required local output files: {missing}")

    artifact_paths: list[Path] = []
    if report_path is not None:
        if not report_path.exists():
            raise FileNotFoundError(f"Missing report output file: {report_path}")
        artifact_paths.append(report_path)
    artifact_paths.extend(required_files)

    agent_logs_dir = output_dir / "agent_logs"
    if agent_logs_dir.exists():
        artifact_paths.extend(
            path for path in sorted(agent_logs_dir.rglob("*")) if path.is_file()
        )
    return artifact_paths


def persist_output_artifacts(
    output_dir: Path,
    report_path: Path | None,
    state_file: Path,
    evals_file: Path,
) -> PersistedArtifacts:
    """
    Uploads run artifacts to GCS while preserving existing local paths.

    Args:
        output_dir (Path): Local run output directory.
        report_path (Path | None): Local report markdown path if generated.
        state_file (Path): Local session state JSON path.
        evals_file (Path): Local eval JSON path.

    Returns:
        PersistedArtifacts: Uploaded artifact metadata.

    Raises:
        FileNotFoundError: If required local artifacts are missing.
        RuntimeError: If any artifact fails to upload to GCS.
    """
    outputs_root = output_dir.parent.parent
    artifact_paths = _collect_artifact_paths(
        output_dir=output_dir,
        report_path=report_path,
        state_file=state_file,
        evals_file=evals_file,
    )

    storage_client = storage.Client()
    bucket = storage_client.bucket(OUTPUTS_BUCKET_NAME)

    uploaded: list[PersistedArtifact] = []
    upload_errors: list[str] = []

    for local_path in artifact_paths:
        object_name = local_path.relative_to(outputs_root).as_posix()
        gcs_uri = f"gs://{OUTPUTS_BUCKET_NAME}/{object_name}"
        try:
            blob = bucket.blob(object_name)
            blob.upload_from_filename(str(local_path))
            uploaded.append(
                PersistedArtifact(local_path=str(local_path), gcs_uri=gcs_uri)
            )
        except Exception as exc:
            upload_errors.append(f"{local_path}: {exc}")

    if upload_errors:
        errors = "; ".join(upload_errors)
        raise RuntimeError(f"GCS upload failed for one or more artifacts: {errors}")

    return PersistedArtifacts(bucket_name=OUTPUTS_BUCKET_NAME, artifacts=uploaded)
