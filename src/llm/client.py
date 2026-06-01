from __future__ import annotations

from litellm import completion

from .env import ENV


def call_llm(system_prompt: str, user_prompt: str, model_name: str) -> str:
    config = ENV.get_model_config(model_name)

    kwargs = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": config.temperature,
        "api_key": config.api_key,
        "base_url": config.base_url if config.base_url else None,
        "reasoning_effort": config.reasoning_effort if config.reasoning_effort else None,
        "timeout": config.timeout_seconds,
    }

    response = completion(**kwargs)
    content = response.choices[0].message.content # Ignore linter error
    return content
