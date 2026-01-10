"""Deep research pipeline entry point."""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from google.genai import types

from google.adk import runners
from google.adk.apps.app import App
from google.adk.plugins import ReflectAndRetryToolPlugin

from dod_deep_research.agents.aggregator.schemas import EvidenceStore
from dod_deep_research.agents.collector.agent import create_targeted_collectors_agent
from dod_deep_research.agents.collector.schemas import CollectorResponse
from dod_deep_research.agents.research_head.agent import (
    aggregate_evidence_after_collectors,
    gap_driven_loop,
)
from dod_deep_research.agents.research_head.schemas import ResearchHeadPlan
from dod_deep_research.agents.sequence_agents import (
    post_aggregation_agent,
    pre_aggregation_agent,
)
from dod_deep_research.agents.shared_state import (
    DeepResearchOutput,
    SharedState,
    aggregate_evidence,
)
from dod_deep_research.agents.writer.schemas import WriterOutput
from dod_deep_research.prompts.indication_prompt import generate_indication_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Suppress verbose logs from Google GenAI and httpx
# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("google_adk.google.adk.models.google_llm").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _suppress_mcp_cleanup_errors(
    loop: asyncio.AbstractEventLoop, context: dict[str, Any]
) -> None:
    """Suppress non-critical MCP cleanup errors."""
    exception = context.get("exception")
    if exception:
        error_msg = str(exception)
        # Suppress errors related to MCP connection cleanup
        if (
            "multiple Transfer-Encoding headers" in error_msg
            or "asynchronous generator" in error_msg
            or "cancel scope" in error_msg
            or "athrow" in error_msg
            or "aclose" in error_msg
        ):
            return  # Suppress this error
    # Log other errors normally using default handler
    loop.default_exception_handler(context)


RESEARCH_DIR = Path(__file__).parent / "research"
app = typer.Typer()


def build_runner(
    agent: object,
    app_name: str,
) -> runners.InMemoryRunner:
    """
    Build an in-memory runner with the Reflect-and-Retry plugin.

    Args:
        agent: Root agent for the runner.
        app_name: Application name for the runner context.

    Returns:
        InMemoryRunner: Configured runner instance.
    """
    retry_plugin = ReflectAndRetryToolPlugin(max_retries=3)
    app_instance = App(
        name=app_name,
        root_agent=agent,
        plugins=[retry_plugin],
    )
    return runners.InMemoryRunner(app=app_instance)


async def run_agent(
    runner: runners.InMemoryRunner,
    user_id: str,
    session_id: str,
    new_message: types.Content,
) -> list[dict]:
    """
    Run an agent and collect JSON responses from events.

    Args:
        runner: The InMemoryRunner instance to use.
        user_id: User ID for the session.
        session_id: Session ID to run the agent in.
        new_message: The message to send to the agent.

    Returns:
        List of parsed JSON objects from final responses.
    """
    json_responses = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        if not event.is_final_response():
            logger.debug(f"Received intermediate event from {event.author}")
            continue

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    try:
                        parsed_json = json.loads(part.text)
                        logger.info(f"Parsed JSON response from agent '{event.author}'")
                        logger.debug(f"Parsed JSON: {parsed_json}")
                        json_responses.append(parsed_json)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse JSON from agent '{event.author}': {e}. "
                            f"Text preview: {part.text[:100]}..."
                        )

    return json_responses


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
    logger.info(
        f"Initializing pipeline: indication={indication}, drug_name={drug_name}, "
        f"drug_form={drug_form}, drug_generic_name={drug_generic_name}"
    )

    # Set exception handler to suppress MCP cleanup errors
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_suppress_mcp_cleanup_errors)
    except RuntimeError:
        pass

    app_name = "deep_research"
    user_id = "user"
    session_id = str(uuid.uuid4())

    prompt_text = generate_indication_prompt(
        disease=indication,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
    )
    logger.debug(f"Generated prompt: {prompt_text}")

    RESEARCH_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    events_dir = RESEARCH_DIR / f"{indication}-{timestamp}"
    events_dir.mkdir(exist_ok=True)
    events_file = events_dir / f"pipeline_events_{timestamp}.json"
    logger.info(f"Events will be saved to: {events_file}")

    new_message = types.Content(
        parts=[types.Part.from_text(text=prompt_text)],
        role="user",
    )

    # Phase 1: Run pre-aggregation agents (planner + collectors)
    logger.info("Starting pre-aggregation phase (planner + collectors)")
    runner_pre = build_runner(agent=pre_aggregation_agent, app_name=app_name)
    session = await runner_pre.session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        state={"indication": indication, "drug_name": drug_name, **kwargs},
    )
    logger.info(f"Created session: {session.id}")

    json_responses = await run_agent(
        runner_pre, session.user_id, session.id, new_message
    )

    logger.info("Pre-aggregation phase completed")

    # Refresh session to get updated state after agents have run
    updated_session = await runner_pre.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session.id,
    )
    # Extract section stores and run deterministic aggregation
    logger.info("Running deterministic evidence aggregation")
    state = updated_session.state

    # Debug: log all state keys
    logger.info(f"Session state keys: {list(state.keys())}")

    # Extract all evidence_store_section_* keys
    section_stores: dict[str, CollectorResponse] = {}
    for key, value in state.items():
        if key.startswith("evidence_store_section_"):
            section_name = key.replace("evidence_store_section_", "")
            try:
                if isinstance(value, dict):
                    section_stores[section_name] = CollectorResponse(**value)
                else:
                    section_stores[section_name] = value
            except Exception as e:
                logger.warning(
                    f"Failed to parse CollectorResponse for section '{section_name}': {e}"
                )

    logger.info(f"Aggregating evidence from {len(section_stores)} sections")
    evidence_store = aggregate_evidence(section_stores)
    logger.info(
        f"Aggregation complete: {len(evidence_store.items)} unique evidence items"
    )

    # Update session state directly with aggregated evidence
    session.state["evidence_store"] = evidence_store.model_dump()
    logger.info(f"Updated session {session.id} state with aggregated evidence")

    # Phase 2: Run gap-driven loop
    logger.info("Starting gap-driven loop phase")
    runner_loop = build_runner(agent=gap_driven_loop, app_name=app_name)

    session_loop = await runner_loop.session_service.create_session(
        app_name=app_name,
        user_id=session.user_id,
        session_id=session.id,
        state=session.state.copy(),
    )
    logger.info(f"Created session in gap-driven loop runner: {session_loop.id}")

    # Run loop iterations manually to handle dynamic targeted collectors
    loop_iteration = 0
    max_iterations = 5

    while loop_iteration < max_iterations:
        loop_iteration += 1
        logger.info(f"Gap-driven loop iteration {loop_iteration}")

        # Check if we have tasks from previous iteration and run targeted collectors
        research_head_plan_dict = session_loop.state.get("research_head_plan")
        if research_head_plan_dict:
            try:
                research_head_plan = ResearchHeadPlan(**research_head_plan_dict)
                if research_head_plan.tasks and research_head_plan.continue_research:
                    logger.info(
                        f"Running {len(research_head_plan.tasks)} targeted collectors"
                    )
                    # Create and run targeted collectors with aggregation callback
                    targeted_collectors = create_targeted_collectors_agent(
                        research_head_plan.tasks,
                        after_agent_callback=aggregate_evidence_after_collectors,
                    )
                    runner_targeted = build_runner(
                        agent=targeted_collectors, app_name=app_name
                    )

                    targeted_session = (
                        await runner_targeted.session_service.create_session(
                            app_name=app_name,
                            user_id=session_loop.user_id,
                            session_id=f"{session_loop.id}_targeted_{loop_iteration}",
                            state=session_loop.state.copy(),
                        )
                    )

                    await run_agent(
                        runner_targeted,
                        targeted_session.user_id,
                        targeted_session.id,
                        types.Content(
                            parts=[
                                types.Part.from_text(text="Collect evidence for tasks.")
                            ],
                            role="user",
                        ),
                    )

                    # Get updated state with new evidence (callback already aggregated)
                    updated_targeted_session = (
                        await runner_targeted.session_service.get_session(
                            app_name=app_name,
                            user_id=targeted_session.user_id,
                            session_id=targeted_session.id,
                        )
                    )
                    # Merge all state including aggregated evidence_store
                    session_loop.state.update(updated_targeted_session.state)
            except Exception as e:
                logger.warning(
                    f"Failed to process research_head_plan or run collectors: {e}"
                )

        # Run loop iteration (research head - aggregation already done by callback)
        loop_message = types.Content(
            parts=[types.Part.from_text(text="Continue gap analysis.")],
            role="user",
        )

        loop_responses = await run_agent(
            runner_loop, session_loop.user_id, session_loop.id, loop_message
        )
        json_responses.extend(loop_responses)

        # Refresh session to check if loop should exit
        updated_loop_session = await runner_loop.session_service.get_session(
            app_name=app_name,
            user_id=session_loop.user_id,
            session_id=session_loop.id,
        )
        session_loop.state = updated_loop_session.state

        # Check if ResearchHead called exit_loop or set continue_research=False
        research_head_plan_dict = session_loop.state.get("research_head_plan")
        if research_head_plan_dict:
            try:
                research_head_plan = ResearchHeadPlan(**research_head_plan_dict)
                if not research_head_plan.continue_research:
                    logger.info(
                        "ResearchHead determined gaps are resolved, exiting loop"
                    )
                    break
            except Exception:
                pass

    logger.info("Gap-driven loop phase completed")

    # Phase 3: Run post-aggregation agents (writer)
    logger.info("Starting post-aggregation phase (writer)")
    runner_post = build_runner(agent=post_aggregation_agent, app_name=app_name)

    # Create a new session in runner_post's session service with updated state
    session_post = await runner_post.session_service.create_session(
        app_name=app_name,
        user_id=session_loop.user_id,
        session_id=session_loop.id,
        state=session_loop.state.copy(),
    )
    logger.info(f"Created session in post-aggregation runner: {session_post.id}")

    # Create a continuation message (empty user message to continue pipeline)
    continuation_message = types.Content(
        parts=[types.Part.from_text(text="Continue with writing.")],
        role="user",
    )

    post_json_responses = await run_agent(
        runner_post, session_post.user_id, session_post.id, continuation_message
    )
    json_responses.extend(post_json_responses)

    logger.info("Pipeline execution completed")
    events_file.write_text(json.dumps(json_responses, indent=2))
    logger.info(f"Pipeline events saved to: {events_file}")

    # Retrieve final session state
    logger.debug("Retrieving final session state")
    final_session = await runner_post.session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_post.id,
    )
    state = final_session.state if final_session else session_post.state

    # Inject evidence deterministically from evidence_store into writer output
    writer_output_dict = state.get("deep_research_output")
    evidence_store_dict = state.get("evidence_store")

    if writer_output_dict and evidence_store_dict:
        writer_output = WriterOutput(**writer_output_dict)
        evidence_store = EvidenceStore(**evidence_store_dict)

        deep_research_output = DeepResearchOutput(
            **writer_output.model_dump(),
            evidence=evidence_store.items,
        )

        state["deep_research_output"] = deep_research_output.model_dump()
        logger.info(
            f"Injected {len(evidence_store.items)} evidence items into DeepResearchOutput"
        )

    logger.debug("Constructing SharedState from session state")
    shared_state = SharedState(
        drug_name=state.get("drug_name"),
        disease_name=state.get("indication"),
        research_plan=state.get("research_plan"),
        evidence_store=state.get("evidence_store"),
        research_head_plan=state.get("research_head_plan"),
        deep_research_output=state.get("deep_research_output"),
    )
    logger.info(
        f"SharedState populated: research_plan={'present' if shared_state.research_plan else 'missing'}, "
        f"evidence_store={'present' if shared_state.evidence_store else 'missing'}, "
        f"deep_research_output={'present' if shared_state.deep_research_output else 'missing'}"
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
    logger.debug("Running pipeline synchronously via asyncio.run")
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
        f"Starting deep research pipeline for indication: {indication}, drug: {drug_name}"
    )
    if drug_form:
        logger.info(f"Drug form specified: {drug_form}")
    if drug_generic_name:
        logger.info(f"Drug generic name specified: {drug_generic_name}")

    try:
        shared_state = run_pipeline(
            indication=indication,
            drug_name=drug_name,
            drug_form=drug_form,
            drug_generic_name=drug_generic_name,
        )

        typer.echo(shared_state.model_dump_json(indent=2))

        logger.info("Pipeline completed successfully")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
