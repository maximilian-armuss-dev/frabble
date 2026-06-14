from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from openrouter import OpenRouter, components

from ..formal.parsing import SubmittedMove
from .env import ModelConfig
from .result import LLMCallResult

OPENROUTER_PROVIDER_DEFAULTS = {
    "allow_fallbacks": False,
    "require_parameters": True,
}


def call_openrouter_detailed(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    reasoning_effort: str | None,
) -> LLMCallResult:
    with OpenRouter(**_client_kwargs(config)) as client:
        response = client.chat.send(
            **_request_kwargs(
                config,
                system_prompt,
                user_prompt,
                reasoning_effort=reasoning_effort,
            )
        )
    return _parse_response(response)


async def acall_openrouter_detailed(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    reasoning_effort: str | None,
) -> LLMCallResult:
    async with OpenRouter(**_client_kwargs(config)) as client:
        response = await client.chat.send_async(
            **_request_kwargs(
                config,
                system_prompt,
                user_prompt,
                reasoning_effort=reasoning_effort,
            )
        )
    return _parse_response(response)


def _client_kwargs(config: ModelConfig) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "api_key": config.api_key,
        "retry_config": None,
    }
    if config.base_url is not None:
        kwargs["server_url"] = config.base_url
    if config.timeout_seconds is not None:
        kwargs["timeout_ms"] = int(config.timeout_seconds * 1000)
    return kwargs


def _request_kwargs(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    reasoning_effort: str | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "model": config.request_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": config.max_completion_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "submitted_move",
                "strict": True,
                "schema": SubmittedMove.model_json_schema(),
            },
        },
        "provider": openrouter_provider_preferences(config),
        "reasoning": openrouter_reasoning(reasoning_effort),
        "x_open_router_metadata": "enabled",
        "stream": False,
        # The evaluation runner owns retries so every attempt is observable.
        "retries": None,
    }
    filtered = _without_none_or_empty(kwargs)
    filtered["retries"] = None
    return filtered


def openrouter_provider_preferences(
    config: ModelConfig,
) -> dict[str, object] | None:
    if config.provider is None:
        return None
    return {
        "only": [config.provider],
        **OPENROUTER_PROVIDER_DEFAULTS,
    }


def openrouter_reasoning(
    reasoning_effort: str | None,
) -> dict[str, object] | None:
    if reasoning_effort is None:
        return None
    return {"effort": reasoning_effort}


def _parse_response(response: components.ChatResult) -> LLMCallResult:
    try:
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        if not isinstance(content, str):
            raise TypeError("Completion content must be a string.")
    except (AttributeError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "OpenRouter returned an invalid completion response."
        ) from exc

    metadata: dict[str, object] = {
        "backend": "openrouter-sdk",
        "response_id": response.id,
        "model": response.model,
        "finish_reason": choice.finish_reason,
        "system_fingerprint": response.system_fingerprint,
        "service_tier": _optional_value(response.service_tier),
        "reasoning": _optional_value(message.reasoning),
        "reasoning_details": _as_list(message.reasoning_details),
        "openrouter": _as_dict(response.openrouter_metadata),
    }
    try:
        submitted = SubmittedMove.model_validate_json(content)
        content = submitted.model_dump_json()
    except Exception as exc:
        metadata["structured_output_error"] = str(exc)
    return LLMCallResult(
        content=content,
        usage=_as_dict(response.usage),
        metadata=_without_none_or_empty(metadata),
    )


def _optional_value(value: object) -> object | None:
    return None if value is None or not bool(value) else value


def _as_dict(value: Any) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(exclude_none=True))
    return {}


def _as_list(value: Any) -> list[object]:
    if value is None:
        return []
    return [
        _as_dict(item) if not isinstance(item, Mapping) else dict(item)
        for item in value
    ]


def _without_none_or_empty(
    values: Mapping[str, object],
) -> dict[str, object]:
    return {
        key: value
        for key, value in values.items()
        if value is not None and value != {} and value != []
    }
