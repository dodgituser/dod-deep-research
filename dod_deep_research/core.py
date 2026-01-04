import logging
from pathlib import Path

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


def list_prompts() -> list[str]:
    """List all available prompt files in the prompts directory."""
    if not PROMPTS_DIR.exists():
        return []
    return sorted(
        [
            f.name
            for f in PROMPTS_DIR.iterdir()
            if f.is_file() and f.name.startswith("prompt_")
        ]
    )
