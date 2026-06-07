from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from litellm import acompletion, completion

from ..formal.parsing import SubmittedMove
from .env import ENV, ModelConfig


@dataclass(frozen=True)
class LLMCallResult:
    content: str
    usage: Mapping[str, object]
    metadata: Mapping[str, object]


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    *,
    reasoning_effort: str | None = None,
) -> str:
    return call_llm_detailed(
        system_prompt,
        user_prompt,
        model_name,
        reasoning_effort=reasoning_effort,
    ).content


def call_llm_detailed(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    *,
    reasoning_effort: str | None = None,
) -> LLMCallResult:
    config = ENV.get_model_config(model_name)
    response = completion(
        **_completion_kwargs(
            config,
            system_prompt,
            user_prompt,
            reasoning_effort=reasoning_effort,
        )
    )
    return _parse_completion_response(response)


async def acall_llm_detailed(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    *,
    reasoning_effort: str | None = None,
) -> LLMCallResult:
    config = ENV.get_model_config(model_name)
    response = await acompletion(
        **_completion_kwargs(
            config,
            system_prompt,
            user_prompt,
            reasoning_effort=reasoning_effort,
        )
    )
    return _parse_completion_response(response)


def _parse_completion_response(response) -> LLMCallResult:
    content = response.choices[0].message.content or ""  # Ignore linter error
    headers = {
        str(key).lower(): value
        for key, value in (
            getattr(response, "_response_headers", None) or {}
        ).items()
    }
    metadata = {
        "backend": "litellm",
        "response_id": response.get("id"),
        "model": response.get("model"),
        "finish_reason": response.choices[0].finish_reason,
        "request_id": headers.get("x-request-id"),
        "provider_processing_ms": _first_present(
            headers,
            "openai-processing-ms",
            "x-openai-processing-ms",
        ),
        "system_fingerprint": response.get("system_fingerprint"),
        "rate_limits": _without_none(
            {
                key: headers.get(key)
                for key in (
                    "x-ratelimit-limit-requests",
                    "x-ratelimit-limit-tokens",
                    "x-ratelimit-remaining-requests",
                    "x-ratelimit-remaining-tokens",
                    "x-ratelimit-reset-requests",
                    "x-ratelimit-reset-tokens",
                    "retry-after",
                )
            }
        ),
    }
    try:
        submitted = SubmittedMove.model_validate_json(content)
        content = submitted.model_dump_json()
    except Exception as exc:
        metadata["structured_output_error"] = str(exc)
    return LLMCallResult(
        content=content,
        usage=_as_dict(response.get("usage")),
        metadata=_without_none(metadata),
    )


def _completion_kwargs(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    *,
    reasoning_effort: str | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": config.temperature,
        "reasoning_effort": reasoning_effort,
        "max_completion_tokens": config.max_completion_tokens,
        "response_format": SubmittedMove,
        # Retries are owned by the evaluation runner so they can be counted,
        # timed, and persisted. OpenAI's SDK otherwise retries twice by default.
        "max_retries": 0,
        "api_key": config.api_key,
        "base_url": config.base_url,
        "timeout": config.timeout_seconds,
    }
    return _without_none(kwargs)


def _as_dict(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return dict(model_dump(exclude_none=True))
    return {}


def _first_present(values: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        value = values.get(key)
        if value is not None:
            return value
    return None


def _without_none(values: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}
