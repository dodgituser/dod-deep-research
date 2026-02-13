"""ADK Web root agent wrapper for running the deep research pipeline."""

from pathlib import Path

from google.adk import Agent
from pydantic import BaseModel, Field

from dod_deep_research.deep_research import run_pipeline
from dod_deep_research.models import GeminiModels

ROOT_AGENT_PROMPT = """
You orchestrate the deep research pipeline.
Before calling any tool, collect required inputs: indication and drug_name.
Optional inputs: drug_form, drug_generic_name, indication_aliases, drug_aliases.
When required inputs are present, call run_deep_research_pipeline exactly once.
Return only the tool result with report_path.
"""


class PipelineRunResult(BaseModel):
    """Structured payload returned by the ADK Web tool."""

    status: str = Field(..., description="Run status: success or error.")
    report_path: str | None = Field(
        default=None, description="Path to generated markdown report."
    )
    error: str | None = Field(default=None, description="Error message when failed.")


def _find_latest_run_output(outputs_root: Path) -> Path | None:
    """Find the most recently modified output directory."""
    if not outputs_root.exists():
        return None

    run_dirs = [path for path in outputs_root.iterdir() if path.is_dir()]
    if not run_dirs:
        return None

    return max(run_dirs, key=lambda path: path.stat().st_mtime)


def run_deep_research_pipeline(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    indication_aliases: list[str] | None = None,
    drug_aliases: list[str] | None = None,
) -> dict[str, str | None]:
    """
    Runs the deep research pipeline synchronously and returns output artifact paths.

    Args:
        indication (str): Disease indication to research.
        drug_name (str): Drug or asset name.
        drug_form (str | None, optional): Specific form of the drug.
            Defaults to None.
        drug_generic_name (str | None, optional): Generic drug name.
            Defaults to None.
        indication_aliases (list[str] | None, optional): Additional indication aliases.
            Defaults to None.
        drug_aliases (list[str] | None, optional): Additional drug aliases.
            Defaults to None.

    Returns:
        dict[str, str | None]: Status and generated artifact paths.

    Raises:
        ValueError: If required inputs are empty.
    """
    if not indication.strip():
        raise ValueError("indication is required")
    if not drug_name.strip():
        raise ValueError("drug_name is required")

    outputs_root = Path(__file__).resolve().parent / "outputs"

    try:
        run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
            indication_aliases=indication_aliases,
            drug_aliases=drug_aliases,
        )
    except Exception as exc:
        return PipelineRunResult(status="error", error=str(exc)).model_dump()

    latest_dir = _find_latest_run_output(outputs_root)
    if latest_dir is None:
        return PipelineRunResult(
            status="error",
            error="Pipeline completed but no output directory was found.",
        ).model_dump()

    return PipelineRunResult(
        status="success",
        report_path=str(latest_dir / "report.md"),
    ).model_dump()


root_agent = Agent(
    name="dod_deep_research_runner",
    model=GeminiModels.GEMINI_FLASH_LATEST.value.replace("models/", ""),
    description="Runs the DOD deep research pipeline from ADK Web.",
    instruction=ROOT_AGENT_PROMPT,
    tools=[
        run_deep_research_pipeline,
    ],
)
