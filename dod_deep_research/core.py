import logging
from pathlib import Path

from dod_deep_research.prompts import list_all, resolve

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(prompt_arg: str, **kwargs) -> str:
    """Load prompt from registry, file, or return as-is."""
    return resolve(prompt_arg, **kwargs)


def list_prompts() -> list[str]:
    """List all registered prompts."""
    return list_all()
