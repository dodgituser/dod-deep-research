from typing import Callable

from dod_deep_research.prompts.indication_prompt import generate_indication_prompt
from dod_deep_research.prompts.prompt_example import get_example_prompt

_PROMPTS: dict[str, Callable[..., str]] = {
    "example": get_example_prompt,
    "indication": generate_indication_prompt,
}


def resolve(name: str, **kwargs) -> str:
    """Resolve prompt by name."""
    return _PROMPTS[name](**kwargs)


def list_all() -> list[str]:
    """List all prompt names."""
    return sorted(_PROMPTS.keys())
