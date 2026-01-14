"""Deep research pipeline CLI entrypoint and stable re-exports."""

import logging

import typer

from dod_deep_research.core import (
    normalize_aliases,
    prepare_outputs_dir,
)
from dod_deep_research.loggy import setup_logging
from dod_deep_research.pipeline.orchestrator import run_pipeline

setup_logging(level=logging.INFO)
logger = logging.getLogger(__name__)
app = typer.Typer()


@app.command()
def main(
    indication: str = typer.Option(
        ..., "--indication", "-i", help="Disease indication to research"
    ),
    drug_name: str = typer.Option(
        ..., "--drug-name", "-d", help="Drug name (e.g., 'IL-2', 'Aspirin')"
    ),
    drug_form: str | None = typer.Option(
        None,
        "--drug-form",
        help="Specific form of the drug (e.g., 'low-dose IL-2')",
    ),
    drug_generic_name: str | None = typer.Option(
        None,
        "--drug-generic-name",
        help="Generic name of the drug (e.g., 'Aldesleukin')",
    ),
    indication_alias: list[str] = typer.Option(
        [],
        "--indication-alias",
        help='Indication alias (repeatable), e.g. --indication-alias "Alzheimer disease"',
    ),
    drug_alias: list[str] = typer.Option(
        [],
        "--drug-alias",
        help="Drug/asset alias (repeatable), e.g. --drug-alias Aldesleukin",
    ),
):
    """
    Run the deep research pipeline for a given disease indication.

    The pipeline executes a map-reduce architecture:
    1. Meta-planner creates structured research outline
    2. Parallel evidence collectors retrieve evidence for each section
    3. Deterministic aggregation function merges and deduplicates evidence
    4. Writer generates final structured output
    """
    logger.info(
        "Starting deep research pipeline for indication: %s, drug: %s",
        indication,
        drug_name,
    )

    try:
        prepare_outputs_dir()
        normalized_indication_aliases = normalize_aliases(indication_alias)
        normalized_drug_aliases = normalize_aliases(drug_alias)
        run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
            indication_aliases=normalized_indication_aliases,
            drug_aliases=normalized_drug_aliases,
        )
        logger.info("Pipeline completed successfully")
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
