from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

import litellm

from ..formal.parsing import SubmittedMove, parse_submitted_move
from ..llm.client import LLMCallResult
from ..llm.env import ENV
from ..llm.evaluation import evaluate_granular
from ..llm.prompting import build_prompt
from ..llm.representers import LANGUAGE_REPRESENTERS, RepresenterConfig
from .artifacts import read_json, utc_now
from .jobs import EvaluationJob
from .models import EvaluationCase

AsyncLLMCaller = Callable[[str, str, str], Awaitable[LLMCallResult]]


class ModelCooldowns:
    def __init__(self) -> None:
        self._deadlines: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, model_name: str) -> None:
        while (remaining := await self.remaining(model_name)) > 0:
            await asyncio.sleep(remaining)

    async def remaining(self, model_name: str) -> float:
        async with self._lock:
            deadline = self._deadlines.get(model_name, 0)
            return deadline - asyncio.get_running_loop().time()

    async def extend(self, model_name: str, delay: float) -> None:
        async with self._lock:
            deadline = asyncio.get_running_loop().time() + delay
            self._deadlines[model_name] = max(
                self._deadlines.get(model_name, 0),
                deadline,
            )


async def execute_with_retries(
    job: EvaluationJob,
    *,
    semaphore: asyncio.Semaphore,
    max_retries: int,
    cooldowns: ModelCooldowns,
    call_llm: AsyncLLMCaller,
) -> dict[str, Any]:
    for retry_index in range(max_retries + 1):
        try:
            return await _execute_after_cooldown(
                job,
                retry_index=retry_index,
                semaphore=semaphore,
                cooldowns=cooldowns,
                call_llm=call_llm,
            )
        except Exception as exc:
            retryable = is_retryable(exc)
            if not retryable or retry_index >= max_retries:
                return transport_error_result(job, exc, retry_index, retryable)

            delay = retry_delay(exc, retry_index)
            if isinstance(exc, litellm.RateLimitError):
                await cooldowns.extend(job.model_name, delay)
            await asyncio.sleep(delay)

    raise AssertionError("Retry loop exited unexpectedly.")


async def _execute_after_cooldown(
    job: EvaluationJob,
    *,
    retry_index: int,
    semaphore: asyncio.Semaphore,
    cooldowns: ModelCooldowns,
    call_llm: AsyncLLMCaller,
) -> dict[str, Any]:
    while True:
        await cooldowns.wait(job.model_name)
        async with semaphore:
            if await cooldowns.remaining(job.model_name) > 0:
                continue
            return await execute_job(job, retry_index, call_llm=call_llm)


async def execute_job(
    job: EvaluationJob,
    retry_index: int,
    *,
    call_llm: AsyncLLMCaller,
) -> dict[str, Any]:
    evaluation_case = EvaluationCase.model_validate(read_json(job.case_path))
    board = evaluation_case.to_board()
    language = evaluation_case.to_language()
    transition = evaluation_case.to_transition()
    representers = RepresenterConfig(
        language=LANGUAGE_REPRESENTERS[job.language_representation]
    )
    system_prompt, user_prompt = build_prompt(
        board,
        transition,
        language,
        representers,
    )

    started_at = perf_counter()
    result = await call_llm(system_prompt, user_prompt, job.model_name)
    elapsed = perf_counter() - started_at
    submitted, parse_error = _parse_response(result.content)
    evaluation = evaluate_granular(
        board,
        language,
        transition.rack,
        submitted,
        parse_error,
    )
    model_config = ENV.get_model_config(job.model_name)
    return {
        "schema_version": 1,
        "job_id": job.job_id,
        "case_id": evaluation_case.case_id,
        "case_file": str(job.case_path),
        "tier": evaluation_case.tier,
        "model": job.model_name,
        "model_config": {
            "model": model_config.model,
            "reasoning_effort": model_config.reasoning_effort,
            "max_completion_tokens": model_config.max_completion_tokens,
            "timeout_seconds": model_config.timeout_seconds,
        },
        "language_representation": job.language_representation,
        "status": "complete",
        "retry_count": retry_index,
        "timestamp": utc_now(),
        "llm_elapsed_seconds": elapsed,
        "usage": dict(result.usage),
        "provider_metadata": dict(result.metadata),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response": result.content,
        "parsed_move": submitted.model_dump(mode="json") if submitted else None,
        "evaluation": evaluation.to_json(),
        "ground_truth_move": evaluation_case.ground_truth_move,
    }


def transport_error_result(
    job: EvaluationJob,
    exc: Exception,
    retry_count: int,
    retryable: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "job_id": job.job_id,
        "case_file": str(job.case_path),
        "model": job.model_name,
        "language_representation": job.language_representation,
        "status": "transport_error",
        "retryable": retryable,
        "retry_count": retry_count,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "timestamp": utc_now(),
    }


def is_retryable(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            litellm.RateLimitError,
            litellm.Timeout,
            litellm.ServiceUnavailableError,
            litellm.InternalServerError,
        ),
    )


def retry_delay(exc: Exception, retry_index: int) -> float:
    headers = exception_headers(exc)
    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(float(retry_after), 0)
        except ValueError:
            pass

    reset_delays = [
        parse_duration(headers[key])
        for key in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens")
        if key in headers
    ]
    if reset_delays:
        return max(reset_delays)

    return min(2**retry_index, 60) + random.random()


def exception_headers(exc: Exception) -> dict[str, str]:
    response = getattr(exc, "response", None)
    raw_headers = (
        getattr(response, "headers", None)
        or getattr(exc, "headers", None)
        or {}
    )
    return {str(key).lower(): str(value) for key, value in raw_headers.items()}


def parse_duration(value: str) -> float:
    multipliers = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    return sum(
        float(number) * multipliers[unit]
        for number, unit in re.findall(r"([0-9.]+)(ms|s|m|h)", value)
    )


def _parse_response(content: str) -> tuple[SubmittedMove | None, str | None]:
    try:
        return parse_submitted_move(content), None
    except Exception as exc:
        return None, str(exc)
