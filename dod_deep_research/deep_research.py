"""Deep research pipeline entry point."""

import asyncio
import logging
import uuid
from pathlib import Path

import typer

from google.adk.agents import InvocationContext
from google.adk.sessions import InMemorySessionService, Session

from dod_deep_research.agents.sequential_agent import root_agent
from dod_deep_research.agents.shared_state import SharedState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = typer.Typer()


async def run_pipeline_async(indication: str, **kwargs) -> SharedState:
    """
    Run the sequential agent pipeline asynchronously and return populated shared state.

    Args:
        indication: The disease indication to research.
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    session_service = InMemorySessionService()
    app_name = "deep_research"
    user_id = "user"
    session_id = str(uuid.uuid4())

    session = Session(
        id=session_id,
        app_name=app_name,
        user_id=user_id,
        state={"indication": indication, **kwargs},
    )

    session_id = session_service.create_session(user_id=user_id, session_id=session_id)

    parent_context = InvocationContext(
        agent=root_agent, session=session, session_service=session_service
    )

    async for _ in root_agent.run_async(parent_context):
        pass

    updated_session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )

    state = updated_session.state

    shared_state = SharedState(
        research_plan=state.get("research_plan"),
        evidence_list=state.get("evidence_list"),
        validation_report=state.get("validation_report"),
        deep_research_output=state.get("deep_research_output"),
    )

    return shared_state


def run_pipeline(indication: str, **kwargs) -> SharedState:
    """
    Run the sequential agent pipeline and return populated shared state.

    Args:
        indication: The disease indication to research.
        **kwargs: Additional keyword arguments to pass to the pipeline.

    Returns:
        SharedState: Populated shared state with all agent outputs.
    """
    return asyncio.run(run_pipeline_async(indication, **kwargs))


@app.command()
def main(
    indication: str = typer.Argument(..., help="Disease indication to research"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path to save the research results (JSON format)",
    ),
):
    """
    Run the deep research pipeline for a given disease indication.

    The pipeline executes sequential agents (planner, retriever, validator, writer)
    to generate comprehensive research output.
    """
    logger.info(f"Starting deep research pipeline for indication: {indication}")

    try:
        shared_state = run_pipeline(indication)

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
