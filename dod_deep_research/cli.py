import logging
from datetime import datetime
from pathlib import Path

import typer

from dod_deep_research.clients import invoke_gemini, invoke_openai
from dod_deep_research.core import determine_provider, load_prompt
from dod_deep_research.models import GeminiModels, OpenAIModels

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
        ..., help="Prompt text or path to prompt file in prompts/"
    ),
    model: str = typer.Option(..., "--model", "-m", help="Model name to use"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (defaults to research/ directory with timestamped filename)",
    ),
):
    """Deep research CLI entry point."""
    logger.info(f"Starting deep research with model: {model}")

    prompt_text = load_prompt(prompt)
    provider = determine_provider(model)
    logger.info(f"Determined provider: {provider}")

    if provider == "gemini":
        try:
            gemini_model = GeminiModels(model)
            logger.debug(f"Using Gemini model: {gemini_model}")
        except ValueError:
            gemini_model = GeminiModels.GEMINI_20_FLASH_LITE
            logger.warning(f"Invalid model '{model}', defaulting to {gemini_model}")
        logger.info("Invoking Gemini API")
        result = invoke_gemini(prompt_text, model=gemini_model)
    else:
        try:
            openai_model = OpenAIModels(model)
            logger.debug(f"Using OpenAI model: {openai_model}")
        except ValueError:
            openai_model = OpenAIModels.GPT_5_NANO
            logger.warning(f"Invalid model '{model}', defaulting to {openai_model}")
        logger.info("Invoking OpenAI API")
        result = invoke_openai(prompt_text, model=openai_model)

    logger.info("Received response from API")

    if output is None:
        RESEARCH_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = RESEARCH_DIR / f"research_{timestamp}.txt"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(str(result))
    logger.info(f"Saved output to: {output}")


if __name__ == "__main__":
    app()
