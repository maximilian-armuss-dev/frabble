from __future__ import annotations

import csv
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .artifacts import read_json

CONSTRAINT_FIELDS = (
    "parse_ok",
    "sequence_valid",
    "min_length_fulfilled",
    "spatial_valid",
    "overlap_valid",
    "no_word_extension",
    "cross_words_valid",
    "rack_valid",
)
GROUP_FIELDS = (
    "tier",
    "model",
    "language_representation",
    "reasoning_effort",
)
CSV_FIELDS = (
    "scope",
    "tier",
    "model",
    "language_representation",
    "reasoning_effort",
    "sampling_round",
    "grammar_sample_index",
    "metric_category",
    "metric_name",
    "count",
    "denominator",
    "rate",
    "value",
)


def build_aggregate(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = [_enrich_coordinates(attempt) for attempt in attempts]
    groups = [
        _aggregate_group(
            items,
            dimensions=dict(zip(GROUP_FIELDS, key, strict=True)),
        )
        for key, items in _group_by(enriched, GROUP_FIELDS)
    ]
    return {
        "schema_version": 2,
        "dimensions": list(GROUP_FIELDS),
        "overall": _aggregate_group(enriched, dimensions={}),
        "groups": groups,
    }


def compact_summary(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    overall = dict(aggregate["overall"])
    groups = list(aggregate["groups"])
    by_tier: dict[str, dict[str, int | float | None]] = {}
    by_model: dict[str, dict[str, int | float | None]] = {}
    for group in groups:
        _merge_compact_bucket(by_tier, str(group["tier"]), group)
        _merge_compact_bucket(by_model, str(group["model"]), group)

    return {
        "schema_version": 1,
        "total_attempts": overall["total_attempts"],
        "completed": overall["completed"],
        "passed": overall["passed"],
        "failed": overall["failed"],
        "pass_rate": overall["pass_rate"],
        "transport_errors": overall["transport_errors"],
        "primary_failures": overall["primary_failures"],
        "failed_constraints": overall["failed_constraints"],
        "by_tier": by_tier,
        "by_model": by_model,
        "by_group": [
            {
                **{field: group[field] for field in GROUP_FIELDS},
                "total": group["completed"],
                "passed": group["passed"],
                "failed": group["failed"],
                "pass_rate": group["pass_rate"],
                "transport_errors": group["transport_errors"],
            }
            for group in groups
        ],
    }


def write_results_csv(path: str | Path, aggregate: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(iter_result_rows(aggregate))
    temporary.replace(output)
    return output


def iter_result_rows(aggregate: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    overall = dict(aggregate["overall"])
    yield from _metric_rows("overall", overall, {})
    for group in aggregate["groups"]:
        dimensions = {field: group[field] for field in GROUP_FIELDS}
        yield from _metric_rows("group", group, dimensions)
        for grammar in group["grammars"]:
            grammar_dimensions = {
                **dimensions,
                "sampling_round": grammar["sampling_round"],
                "grammar_sample_index": grammar["grammar_sample_index"],
            }
            yield from _metric_rows("grammar", grammar, grammar_dimensions)


def _aggregate_group(
    attempts: list[dict[str, Any]],
    *,
    dimensions: dict[str, Any],
) -> dict[str, Any]:
    completed = [item for item in attempts if item.get("status") == "complete"]
    passed = [item for item in completed if _attempt_passed(item)]
    failed = [item for item in completed if not _attempt_passed(item)]
    primary_failures = Counter(
        str(item.get("evaluation", {}).get("failure_type") or "unknown")
        for item in failed
    )
    failed_constraints = {
        field: sum(
            item.get("evaluation", {}).get(field) is False for item in completed
        )
        for field in CONSTRAINT_FIELDS
    }
    constraint_pass_rates = {
        field: _rate(
            sum(item.get("evaluation", {}).get(field) is True for item in completed),
            len(completed),
        )
        for field in CONSTRAINT_FIELDS
    }
    grammar_groups = [
        _aggregate_grammar(items, key)
        for key, items in _group_by(
            completed,
            ("sampling_round", "grammar_sample_index"),
        )
        if all(value is not None for value in key)
    ]
    return {
        **dimensions,
        "total_attempts": len(attempts),
        "completed": len(completed),
        "passed": len(passed),
        "failed": len(failed),
        "pass_rate": _rate(len(passed), len(completed)),
        "transport_errors": len(attempts) - len(completed),
        "retry_count_total": sum(
            int(item.get("retry_count", 0)) for item in attempts
        ),
        "primary_failures": dict(sorted(primary_failures.items())),
        "failed_constraints": failed_constraints,
        "constraint_pass_rates": constraint_pass_rates,
        "timing": {
            "request_elapsed_seconds": _numeric_summary(
                _request_elapsed_seconds(item) for item in attempts
            ),
            "llm_elapsed_seconds": _numeric_summary(
                item.get("llm_elapsed_seconds") for item in completed
            ),
            "llm_elapsed_seconds_total": _numeric_summary(
                item.get("llm_elapsed_seconds_total") for item in completed
            ),
            "retry_wait_seconds_total": _numeric_summary(
                item.get("retry_wait_seconds_total") for item in completed
            ),
            "provider_processing_ms": _numeric_summary(
                item.get("provider_metadata", {}).get("provider_processing_ms")
                for item in completed
            ),
        },
        "usage": {
            "prompt_tokens": _numeric_summary(
                item.get("usage", {}).get("prompt_tokens") for item in completed
            ),
            "completion_tokens": _numeric_summary(
                item.get("usage", {}).get("completion_tokens") for item in completed
            ),
            "reasoning_tokens": _numeric_summary(
                item.get("usage", {})
                .get("completion_tokens_details", {})
                .get("reasoning_tokens")
                for item in completed
            ),
            "total_tokens": _numeric_summary(
                item.get("usage", {}).get("total_tokens") for item in completed
            ),
        },
        "quality": {
            "rack_symbols_used": _numeric_summary(
                item.get("evaluation", {}).get("rack_symbols_used")
                for item in completed
            ),
            "rack_usage_ratio": _numeric_summary(
                item.get("evaluation", {}).get("rack_usage_ratio")
                for item in completed
            ),
            "main_word_length": _numeric_summary(
                item.get("evaluation", {}).get("main_word_length")
                for item in completed
            ),
            "overlap_count": _numeric_summary(
                item.get("evaluation", {}).get("overlap_count")
                for item in completed
            ),
            "letter_score_total": _numeric_summary(
                item.get("evaluation", {}).get("letter_score_total")
                for item in completed
            ),
        },
        "grammars": grammar_groups,
    }


def _aggregate_grammar(
    attempts: list[dict[str, Any]],
    key: tuple[Any, ...],
) -> dict[str, Any]:
    failed = [item for item in attempts if not _attempt_passed(item)]
    passed_count = len(attempts) - len(failed)
    failures = Counter(
        str(item.get("evaluation", {}).get("failure_type") or "unknown")
        for item in failed
    )
    return {
        "sampling_round": key[0],
        "grammar_sample_index": key[1],
        "total_attempts": len(attempts),
        "completed": len(attempts),
        "passed": passed_count,
        "failed": len(failed),
        "pass_rate": _rate(passed_count, len(attempts)),
        "transport_errors": 0,
        "retry_count_total": sum(
            int(item.get("retry_count", 0)) for item in attempts
        ),
        "primary_failures": dict(sorted(failures.items())),
        "failed_constraints": {
            field: sum(
                item.get("evaluation", {}).get(field) is False for item in attempts
            )
            for field in CONSTRAINT_FIELDS
        },
        "constraint_pass_rates": {
            field: _rate(
                sum(
                    item.get("evaluation", {}).get(field) is True
                    for item in attempts
                ),
                len(attempts),
            )
            for field in CONSTRAINT_FIELDS
        },
        "timing": {},
        "usage": {},
        "quality": {
            "rack_symbols_used": _numeric_summary(
                item.get("evaluation", {}).get("rack_symbols_used")
                for item in attempts
            ),
            "rack_usage_ratio": _numeric_summary(
                item.get("evaluation", {}).get("rack_usage_ratio")
                for item in attempts
            ),
            "main_word_length": _numeric_summary(
                item.get("evaluation", {}).get("main_word_length")
                for item in attempts
            ),
            "overlap_count": _numeric_summary(
                item.get("evaluation", {}).get("overlap_count")
                for item in attempts
            ),
            "letter_score_total": _numeric_summary(
                item.get("evaluation", {}).get("letter_score_total")
                for item in attempts
            ),
        },
    }


def _metric_rows(
    scope: str,
    aggregate: Mapping[str, Any],
    dimensions: Mapping[str, Any],
) -> Iterable[dict[str, Any]]:
    base = {
        "scope": scope,
        **{field: dimensions.get(field) for field in CSV_FIELDS if field in dimensions},
    }
    completed = int(aggregate["completed"])
    failed = int(aggregate["failed"])
    for name in ("passed", "failed", "transport_errors"):
        denominator = (
            completed if name in {"passed", "failed"} else aggregate["total_attempts"]
        )
        count = int(aggregate[name])
        yield _row(base, "outcome", name, count, int(denominator))
    for name, count in aggregate["primary_failures"].items():
        yield _row(base, "primary_failure", name, int(count), failed)
    for name, count in aggregate["failed_constraints"].items():
        yield _row(base, "failed_constraint", name, int(count), completed)
    for family in ("timing", "usage", "quality"):
        for name, summary in aggregate.get(family, {}).items():
            for statistic in ("mean", "median", "min", "max", "sum"):
                value = summary.get(statistic)
                if value is not None:
                    yield _value_row(base, family, f"{name}_{statistic}", value)


def _row(
    base: Mapping[str, Any],
    category: str,
    name: str,
    count: int,
    denominator: int,
) -> dict[str, Any]:
    return {
        **base,
        "metric_category": category,
        "metric_name": name,
        "count": count,
        "denominator": denominator,
        "rate": _rate(count, denominator),
        "value": "",
    }


def _value_row(
    base: Mapping[str, Any],
    category: str,
    name: str,
    value: int | float,
) -> dict[str, Any]:
    return {
        **base,
        "metric_category": category,
        "metric_name": name,
        "count": "",
        "denominator": "",
        "rate": "",
        "value": value,
    }


def _numeric_summary(values: Iterable[Any]) -> dict[str, int | float | None]:
    numeric = []
    for value in values:
        if value is None:
            continue
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numeric:
        return {
            "count": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
        }
    total = sum(numeric)
    return {
        "count": len(numeric),
        "sum": total,
        "mean": total / len(numeric),
        "median": statistics.median(numeric),
        "min": min(numeric),
        "max": max(numeric),
    }


def _request_elapsed_seconds(attempt: Mapping[str, Any]) -> Any:
    total = attempt.get("llm_elapsed_seconds_total")
    return total if total is not None else attempt.get("llm_elapsed_seconds")


def _group_by(
    items: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> list[tuple[tuple[Any, ...], list[dict[str, Any]]]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for item in items:
        key = tuple(item.get(field) for field in fields)
        buckets.setdefault(key, []).append(item)
    return sorted(
        buckets.items(),
        key=lambda item: tuple(str(value) for value in item[0]),
    )


def _enrich_coordinates(attempt: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(attempt)
    if enriched.get("reasoning_effort") is None:
        model_config = dict(enriched.get("model_config", {}))
        enriched["reasoning_effort"] = model_config.get(
            "reasoning_effort",
            model_config.get("reasoning_depth"),
        )
    required = (
        "tier",
        "sampling_round",
        "grammar_sample_index",
        "board_sample_index",
    )
    if all(enriched.get(field) is not None for field in required):
        return enriched
    case_file = enriched.get("case_file")
    if not case_file:
        return enriched
    try:
        case = read_json(str(case_file))
    except (OSError, ValueError):
        return enriched
    for field in required:
        if enriched.get(field) is None:
            enriched[field] = case.get(field)
    return enriched


def _merge_compact_bucket(
    buckets: dict[str, dict[str, int | float | None]],
    key: str,
    group: Mapping[str, Any],
) -> None:
    bucket = buckets.setdefault(
        key,
        {"total": 0, "passed": 0, "failed": 0, "transport_errors": 0},
    )
    bucket["total"] = int(bucket["total"] or 0) + int(group["completed"])
    bucket["passed"] = int(bucket["passed"] or 0) + int(group["passed"])
    bucket["failed"] = int(bucket["failed"] or 0) + int(group["failed"])
    bucket["transport_errors"] = int(bucket["transport_errors"] or 0) + int(
        group["transport_errors"]
    )
    bucket["pass_rate"] = _rate(
        int(bucket["passed"] or 0),
        int(bucket["total"] or 0),
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _attempt_passed(attempt: Mapping[str, Any]) -> bool:
    return bool(dict(attempt.get("evaluation", {})).get("overall"))
