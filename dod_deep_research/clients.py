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


OPENAI_CLIENT = OpenAIClientConfig().create_client()
GEMINI_CLIENT = GeminiClientConfig().create_client()


def invoke_gemini(
    prompt: str,
    model: GeminiModels = GeminiModels.DEEP_RESEARCH_PRO_PREVIEW_12_2025,
    config: types.GenerateContentConfig | None = None,
) -> str | None:
    """
    Invokes the Gemini API to generate content.

    Args:
        prompt (str): Text prompt to send to the model.
        model (GeminiModels, optional): Gemini model to use.
            Defaults to GeminiModels.DEEP_RESEARCH_PRO_PREVIEW_12_2025.
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

    response = GEMINI_CLIENT.models.generate_content(
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
    model: OpenAIModels = OpenAIModels.O3_DEEP_RESEARCH,
    response_format: BaseModel | None = None,
) -> BaseModel:
    """
    Invokes the OpenAI API to generate content.

    Args:
        prompt (str): Text prompt to send to the model.
        model (OpenAIModels, optional): OpenAI model to use.
            Defaults to OpenAIModels.O3_DEEP_RESEARCH.
        response_format (BaseModel, optional): Pydantic model for structured response.
            Defaults to None.

    Returns:
        BaseModel: Parsed response matching response_format schema.
    """
    result = OPENAI_CLIENT.chat.completions.parse(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format=response_format,
        max_completion_tokens=4096,
    )
    response = result.choices[0].message
    result = response.parsed
    return result
