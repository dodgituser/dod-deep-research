"""Deep research pipeline entry point."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import typer
from google.genai import types

from google.adk import runners

from dod_deep_research.agents.sequential_agent import root_agent
from dod_deep_research.agents.shared_state import SharedState
from dod_deep_research.prompts import resolve

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RESEARCH_DIR = Path(__file__).parent / "research"
app = typer.Typer()


async def run_pipeline_async(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    **kwargs,
) -> SharedState:
    """
    Run the sequential agent pipeline asynchronously and return populated shared state.

    Args:
        indication: The disease indication to research.
        drug_name: The drug name (e.g., "IL-2", "Aspirin").
        drug_form: The specific form of the drug (e.g., "low-dose IL-2").
        drug_generic_name: The generic name of the drug (e.g., "Aldesleukin").
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    app_name = "deep_research"
    user_id = "user"
    session_id = str(uuid.uuid4())

    prompt_text = resolve(
        "indication",
        disease=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
    )

    runner = runners.InMemoryRunner(agent=root_agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state={"indication": indication, "drug_name": drug_name, **kwargs},
    )

    new_message = types.Content(
        parts=[types.Part.from_text(text=prompt_text)],
        role="user",
    )

    events = []
    async for event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=new_message,
    ):
        events.append(event)

    RESEARCH_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    events_dir = RESEARCH_DIR / f"{indication}-{timestamp}"
    events_dir.mkdir(exist_ok=True)
    events_file = events_dir / f"pipeline_events_{timestamp}.json"

    json_responses = []
    for event in events:
        event: runners.Event
        if not event.is_final_response():
            continue

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    try:
                        parsed_json = json.loads(part.text)
                        json_responses.append(parsed_json)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse JSON from event text: {part.text[:100]}..."
                        )

    events_file.write_text(json.dumps(json_responses, indent=2))
    logger.info(f"Pipeline events saved to: {events_file}")

    updated_session = await runner.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )
    state = updated_session.state if updated_session else session.state

    shared_state = SharedState(
        research_plan=state.get("research_plan"),
        evidence_store=state.get("evidence_store"),
        validation_report=state.get("validation_report"),
        deep_research_output=state.get("deep_research_output"),
    )

    return shared_state


def run_pipeline(
    indication: str,
    drug_name: str,
    drug_form: str | None = None,
    drug_generic_name: str | None = None,
    **kwargs,
) -> SharedState:
    """
    Run the sequential agent pipeline and return populated shared state.

    Args:
        indication: The disease indication to research.
        drug_name: The drug name (e.g., "IL-2", "Aspirin").
        drug_form: The specific form of the drug (e.g., "low-dose IL-2").
        drug_generic_name: The generic name of the drug (e.g., "Aldesleukin").
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    return asyncio.run(
        run_pipeline_async(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
            **kwargs,
        )
    )


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
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path to save the research results (JSON format)",
    ),
):
    """
    Run the deep research pipeline for a given disease indication.

    The pipeline executes a map-reduce architecture:
    1. Meta-planner creates structured research outline
    2. Parallel evidence collectors retrieve evidence for each section
    3. Aggregator merges and deduplicates evidence
    4. Validator validates and identifies gaps
    5. Writer generates final structured output
    """
    logger.info(
        f"Starting deep research pipeline for indication: {indication}, drug: {drug_name}"
    )

    try:
        shared_state = run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
        )

        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(shared_state.model_dump_json(indent=2))
            logger.info(f"Results saved to: {output}")
        else:
            typer.echo(shared_state.model_dump_json(indent=2))

        logger.info("Pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
