from __future__ import annotations

import os

from litellm import completion

from .config import get_llm_config


def call_llm(system_prompt: str, user_prompt: str) -> str:
    config = get_llm_config()

    # Set API key in environment for litellm
    os.environ["OPENAI_API_KEY"] = config.api_key
    os.environ["ANTHROPIC_API_KEY"] = config.api_key
    os.environ["COHERE_API_KEY"] = config.api_key
    os.environ["GEMINI_API_KEY"] = config.api_key

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
    }

    # Add reasoning effort for models that support it (e.g., o1, o3)
    if config.reasoning_effort:
        kwargs["reasoning"] = {"effort": config.reasoning_effort}

    response = completion(**kwargs)

    # Extract the text content from the response
    if hasattr(response, "choices") and len(response.choices) > 0:
        message = response.choices[0].message
        if hasattr(message, "content") and message.content:
            return message.content

    raise RuntimeError("LLM response did not contain valid content.")
