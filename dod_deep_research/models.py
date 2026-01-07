from enum import StrEnum


class Provider(StrEnum):
    GEMINI = "gemini"
    OPENAI = "openai"


class GeminiModels(StrEnum):
    GEMINI_20_FLASH_LITE = "models/gemini-2.0-flash-lite"
    GEMINI_25_FLASH_LITE = "models/gemini-2.5-flash-lite"
    GEMINI_FLASH_LATEST = "models/gemini-flash-latest"
    GEMINI_FLASH_LITE_LATEST = "models/gemini-flash-lite-latest"
    GEMINI_25_PRO = "models/gemini-2.5-pro"
    GEMINI_30_PRO = "models/gemini-3.0-pro"


class OpenAIModels(StrEnum):
    O3_DEEP_RESEARCH = "o3-deep-research"


_MODEL_REGISTRY: dict[str, Provider] = {}


def _build_registry() -> dict[str, Provider]:
    """Build the model registry mapping model names to providers."""
    registry = {}
    for model in GeminiModels:
        registry[model.value] = Provider.GEMINI
    for model in OpenAIModels:
        registry[model.value] = Provider.OPENAI
    return registry


def get_provider(model_name: str) -> Provider:
    """
    Get the provider for a given model name.

    Args:
        model_name: The model name to look up.

    Returns:
        Provider enum value.
    """
    global _MODEL_REGISTRY
    if not _MODEL_REGISTRY:
        _MODEL_REGISTRY = _build_registry()

    model_lower = model_name.lower()

    # Check exact match first
    if model_name in _MODEL_REGISTRY:
        return _MODEL_REGISTRY[model_name]

    # Check case-insensitive match
    for model, provider in _MODEL_REGISTRY.items():
        if model.lower() == model_lower:
            return provider

    # Check if "gemini" is in the name
    if "gemini" in model_lower:
        return Provider.GEMINI

    # Default to OpenAI
    return Provider.OPENAI
