import os

from google import genai
from google.genai import types
from openai import OpenAI
from pydantic import BaseModel

from dod_deep_research.models import GeminiModels, OpenAIModels


class GeminiClientConfig(BaseModel):
    def create_client(self) -> genai.Client:
        """
        Creates a Gemini API client.

        Returns:
            genai.Client: Configured Gemini client instance.
        """
        return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class OpenAIClientConfig(BaseModel):
    def create_client(self) -> OpenAI:
        """
        Creates an OpenAI API client.

        Returns:
            openai.OpenAI: Configured OpenAI client instance.
        """
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", "not_needed"),
        )


_openai_client = None
_gemini_client = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClientConfig().create_client()
    return _openai_client


def get_gemini_client() -> genai.Client:
    """Get or create Gemini client instance."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClientConfig().create_client()
    return _gemini_client


def invoke_gemini(
    prompt: str,
    model: GeminiModels = GeminiModels.GEMINI_20_FLASH_LITE,
    config: types.GenerateContentConfig | None = None,
) -> str | None:
    """
    Invokes the Gemini API to generate content.

    Args:
        prompt (str): Text prompt to send to the model.
        model (GeminiModels, optional): Gemini model to use.
            Defaults to GeminiModels.GEMINI_20_FLASH_LITE.
        config (GenerateContentConfig, optional): Generation configuration.
            Defaults to None.

    Returns:
        str: Generated text response.
    """
    contents = [
        types.Content(
            parts=[types.Part.from_text(text=prompt)],
            role="user",
        ),
        types.Content(
            parts=[types.Part.from_text(text="I'll begin writing my response now.")],
            role="model",
        ),
    ]

    response = get_gemini_client().models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )

    if response is None or not hasattr(response, "text") or response.text is None:
        return None

    text = response.text

    return text


def invoke_openai(
    prompt: str,
    model: OpenAIModels = OpenAIModels.GPT_5_NANO,
    response_format: BaseModel | None = None,
) -> BaseModel:
    """
    Invokes the OpenAI API to generate content.

    Args:
        prompt (str): Text prompt to send to the model.
        model (OpenAIModels, optional): OpenAI model to use.
            Defaults to OpenAIModels.GPT_5_NANO.
        response_format (BaseModel, optional): Pydantic model for structured response.
            Defaults to None.

    Returns:
        BaseModel: Parsed response matching response_format schema.
    """
    result = get_openai_client().chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=response_format,
        max_completion_tokens=4096,
    )
    response = result.choices[0].message
    result = response.parsed
    return result
