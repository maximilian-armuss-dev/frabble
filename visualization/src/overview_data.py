"""Small, prompt-free records for the multidimensional evaluation overview."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Mapping, Sequence


OUTCOMES = {
    "valid": ("Valid", "#72C58C", "V", "circle"),
    "truncated": ("Truncated", "#E36A6A", "T", "triangle-up"),
    "semantic": ("Semantic failure", "#91BDF2", "S", "x"),
    "format": ("Format failure", "#B49BD5", "F", "diamond"),
    "provider": ("Provider response error", "#67748e", "E", "square"),
    "transport": ("Transport / request error", "#9299A3", "X", "cross"),
    "unknown": ("Unclassified failure", "#C5CBD4", "?", "star"),
}


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None
    return None


def outcome(attempt: Mapping[str, Any]) -> str:
    if attempt.get("status") != "complete":
        return "transport"
    if attempt.get("provider_metadata", {}).get("finish_reason") == "error":
        return "provider"
    evaluation = attempt.get("evaluation", {})
    if evaluation.get("overall"):
        return "valid"
    failure = evaluation.get("failure_type")
    if failure == "truncated":
        return "truncated"
    if failure == "parse":
        return "format"
    return "semantic" if failure else "unknown"


def attempt_record(attempt: Mapping[str, Any]) -> dict[str, Any]:
    """Keep chart inputs without copying prompts, raw answers or reasoning."""
    evaluation = attempt.get("evaluation", {})
    usage = attempt.get("usage", {})
    config = attempt.get("model_config", {})
    category = outcome(attempt)
    valid = category == "valid"
    score = number(evaluation.get("letter_score_total")) if valid else None
    optimum = number(attempt.get("optimal_score"))
    elapsed = number(attempt.get("llm_elapsed_seconds_total"))
    if elapsed is None:
        elapsed = number(attempt.get("llm_elapsed_seconds"))
    wait = number(attempt.get("retry_wait_seconds_total")) or 0
    limit = number(config.get("request_max_tokens"))
    if limit is None:
        limit = number(config.get("max_completion_tokens"))
    return {
        **{key: attempt.get(key) for key in (
            "case_id", "model", "dimensions", "board_size", "sampling_round",
            "language_representation", "reasoning_effort",
        )},
        "completed": attempt.get("status") == "complete",
        "outcome": category,
        "failure": evaluation.get("failure_type"),
        "message": evaluation.get("message") or attempt.get("error_type") or "",
        "violations": [key for key, value in evaluation.items()
                       if value is False and key != "overall"],
        "finish_reason": attempt.get("provider_metadata", {}).get("finish_reason"),
        "score": score,
        "optimal_score": optimum,
        "score_ratio": score / optimum if score is not None and optimum and optimum > 0 else None,
        "overlap": number(evaluation.get("overlap_count")) if valid else None,
        "prompt_tokens": number(usage.get("prompt_tokens")),
        "completion_tokens": number(usage.get("completion_tokens")),
        "reasoning_tokens": number((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")),
        "token_limit": limit,
        "runtime_minutes": (elapsed + wait) / 60 if elapsed is not None else None,
        "cost_usd": number(usage.get("cost")),
    }


def reported_cost(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Sum reported final-record costs; missing costs are never treated as free."""
    costs = [number(a.get("usage", {}).get("cost")) for a in attempts]
    known = [cost for cost in costs if cost is not None]
    return {
        "usd": math.fsum(known) if known else None,
        "reported": len(known),
        "attempts": len(attempts),
        "missing": len(attempts) - len(known),
        "retries": sum(int(a.get("retry_count") or 0) for a in attempts),
    }


def overview_payload(
    all_attempts: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
) -> dict[str, Any]:
    records = [attempt_record(a) for a in selected]
    cell_counts = Counter(
        (r["model"], r["dimensions"], r["board_size"],
         r["language_representation"], r["reasoning_effort"])
        for r in records
    )
    return {
        "run_id": run_id,
        "attempts": records,
        "run_cost": reported_cost(all_attempts),
        "selection_cost": reported_cost(selected),
        "model_costs": {
            model: {
                "run": reported_cost([a for a in all_attempts if a["model"] == model]),
                "selection": reported_cost([a for a in selected if a["model"] == model]),
            }
            for model in sorted({a["model"] for a in all_attempts})
        },
        "cell_counts": sorted(set(cell_counts.values())),
    }
