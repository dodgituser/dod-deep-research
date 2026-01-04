import logging
from pathlib import Path

from dod_deep_research.models import GeminiModels

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(prompt_arg: str) -> str:
    """Load prompt from file if it exists in prompts directory, otherwise return as-is."""
    prompt_path = PROMPTS_DIR / prompt_arg
    if prompt_path.exists() and prompt_path.is_file():
        logger.debug(f"Loading prompt from file: {prompt_path}")
        return prompt_path.read_text()
    logger.debug("Using prompt as direct text")
    return prompt_arg


def determine_provider(model_name: str) -> str:
    """Determine if model is Gemini or OpenAI based on model name."""
    model_lower = model_name.lower()
    if "gemini" in model_lower:
        return "gemini"
    try:
        GeminiModels(model_name)
        return "gemini"
    except ValueError:
        pass
    return "openai"
