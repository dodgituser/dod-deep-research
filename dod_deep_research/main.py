import logging
from datetime import datetime
from pathlib import Path

import typer

from dod_deep_research.clients import invoke_gemini, invoke_openai
from dod_deep_research.core import load_prompt, list_prompts
from dod_deep_research.models import GeminiModels, OpenAIModels, Provider, get_provider
from dod_deep_research.schemas import CliArgs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RESEARCH_DIR = Path("research")

app = typer.Typer()


@app.command()
def main(
    prompt: str = typer.Argument(
        ..., help="Prompt name from registry or direct prompt text"
    ),
    model: str = typer.Option(..., "--model", "-m", help="Model name to use"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (defaults to research/ directory with timestamped filename)",
    ),
    disease: str | None = typer.Option(
        None, "--disease", "-d", help="Disease indication for prompt"
    ),
    drug_name: str | None = typer.Option(
        None, "--drug-name", help="Drug name for prompt"
    ),
    drug_form: str | None = typer.Option(
        None, "--drug-form", help="Drug form for prompt"
    ),
    drug_generic_name: str | None = typer.Option(
        None, "--drug-generic-name", help="Drug generic name for prompt"
    ),
):
    """Deep research CLI entry point."""
    cli_args = CliArgs(
        prompt=prompt,
        model=model,
        output=output,
        disease=disease,
        drug_name=drug_name,
        drug_form=drug_form,
        drug_generic_name=drug_generic_name,
    )

    logger.info(f"Starting deep research with model: {cli_args.model}")

    prompt_text = load_prompt(cli_args.prompt, **cli_args.to_prompt_kwargs())
    provider = get_provider(cli_args.model)
    logger.info(f"Determined provider: {provider}")

    if provider == Provider.GEMINI:
        try:
            gemini_model = GeminiModels(cli_args.model)
            logger.debug(f"Using Gemini model: {gemini_model}")
        except ValueError:
            gemini_model = GeminiModels.DEEP_RESEARCH_PRO_PREVIEW_12_2025
            logger.warning(
                f"Invalid model '{cli_args.model}', defaulting to {gemini_model}"
            )
        logger.info("Invoking Gemini API")
        result = invoke_gemini(prompt_text, model=gemini_model)
    else:
        try:
            openai_model = OpenAIModels(cli_args.model)
            logger.debug(f"Using OpenAI model: {openai_model}")
        except ValueError:
            openai_model = OpenAIModels.O3_DEEP_RESEARCH
            logger.warning(
                f"Invalid model '{cli_args.model}', defaulting to {openai_model}"
            )
        logger.info("Invoking OpenAI API")
        result = invoke_openai(prompt_text, model=openai_model)

    logger.info("Received response from API")

    if cli_args.output is None:
        RESEARCH_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cli_args.output = RESEARCH_DIR / f"research_{timestamp}.txt"

    cli_args.output.parent.mkdir(parents=True, exist_ok=True)
    cli_args.output.write_text(str(result))
    logger.info(f"Saved output to: {cli_args.output}")


@app.command()
def list_prompts_cmd():
    """List all available prompts."""
    prompts = list_prompts()
    if prompts:
        logger.info("Available prompts:")
        for prompt in prompts:
            logger.info(f"  - {prompt}")
    else:
        logger.info("No prompts found.")


if __name__ == "__main__":
    app()
