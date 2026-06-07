from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from typing import Any

from src.evaluation.artifacts import read_json, write_json_atomic
from src.evaluation.result_aggregation import (
    build_aggregate,
    compact_summary,
    iter_result_rows,
    write_results_csv,
)
from src.evaluation.result_index import load_or_build_result_index


class ResultAggregationTests(unittest.TestCase):
    def test_legacy_attempt_coordinates_and_reasoning_are_enriched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_path = Path(temp_dir) / "case.json"
            write_json_atomic(
                case_path,
                {
                    "tier": "medium",
                    "sampling_round": 2,
                    "grammar_sample_index": 3,
                    "board_sample_index": 4,
                },
            )
            attempt = _attempt(
                case_id="case-a",
                reasoning_effort=None,
                model_config={"reasoning_depth": "high"},
            )
            attempt["case_file"] = str(case_path)
            for field in (
                "tier",
                "sampling_round",
                "grammar_sample_index",
                "board_sample_index",
            ):
                attempt.pop(field)

            aggregate = build_aggregate([attempt])

        group = aggregate["groups"][0]
        self.assertEqual(group["tier"], "medium")
        self.assertEqual(group["reasoning_effort"], "high")
        self.assertEqual(
            (
                group["grammars"][0]["sampling_round"],
                group["grammars"][0]["grammar_sample_index"],
            ),
            (2, 3),
        )
        self.assertNotIn("tier", attempt)
        self.assertIsNone(attempt["reasoning_effort"])

    def test_outcomes_constraints_retries_and_resources_use_correct_attempts(self):
        passed = _attempt(
            case_id="pass",
            retry_count=1,
            elapsed=1.0,
            provider_ms="900",
            prompt_tokens=10,
            completion_tokens=8,
            reasoning_tokens=5,
            total_tokens=18,
        )
        failed = _attempt(
            case_id="fail",
            overall=False,
            failure_type=None,
            retry_count=2,
            elapsed=3.0,
            provider_ms="1100",
            prompt_tokens=30,
            completion_tokens=12,
            reasoning_tokens=7,
            total_tokens=42,
            false_constraints=("parse_ok", "rack_valid"),
        )
        transport = _transport_attempt(case_id="transport", retry_count=4)

        aggregate = build_aggregate([passed, failed, transport])
        overall = aggregate["overall"]

        self.assertEqual(
            (
                overall["total_attempts"],
                overall["completed"],
                overall["passed"],
                overall["failed"],
                overall["transport_errors"],
            ),
            (3, 2, 1, 1, 1),
        )
        self.assertEqual(overall["pass_rate"], 0.5)
        self.assertEqual(overall["retry_count_total"], 7)
        self.assertEqual(overall["primary_failures"], {"unknown": 1})
        self.assertEqual(overall["failed_constraints"]["parse_ok"], 1)
        self.assertEqual(overall["failed_constraints"]["rack_valid"], 1)
        self.assertEqual(overall["constraint_pass_rates"]["parse_ok"], 0.5)
        self.assertEqual(
            overall["timing"]["llm_elapsed_seconds"],
            {
                "count": 2,
                "sum": 4.0,
                "mean": 2.0,
                "median": 2.0,
                "min": 1.0,
                "max": 3.0,
            },
        )
        self.assertEqual(
            overall["timing"]["provider_processing_ms"]["mean"],
            1000.0,
        )
        self.assertEqual(overall["usage"]["prompt_tokens"]["mean"], 20.0)
        self.assertEqual(overall["usage"]["reasoning_tokens"]["sum"], 12.0)
        self.assertEqual(overall["grammars"][0]["total_attempts"], 2)

    def test_numeric_summaries_ignore_missing_and_non_numeric_values(self):
        valid = _attempt(
            case_id="valid",
            elapsed=2.5,
            provider_ms="1250",
            prompt_tokens=12,
        )
        invalid = _attempt(case_id="invalid")
        invalid["llm_elapsed_seconds"] = "not-a-number"
        invalid["provider_metadata"] = {"provider_processing_ms": None}
        invalid["usage"] = {
            "prompt_tokens": "invalid",
            "completion_tokens": None,
            "total_tokens": 9,
            "completion_tokens_details": {},
        }

        overall = build_aggregate([valid, invalid])["overall"]

        self.assertEqual(overall["timing"]["llm_elapsed_seconds"]["count"], 1)
        self.assertEqual(overall["timing"]["llm_elapsed_seconds"]["mean"], 2.5)
        self.assertEqual(overall["usage"]["prompt_tokens"]["count"], 1)
        self.assertEqual(overall["usage"]["prompt_tokens"]["sum"], 12.0)
        self.assertEqual(overall["usage"]["reasoning_tokens"]["count"], 1)
        self.assertEqual(overall["usage"]["reasoning_tokens"]["sum"], 5.0)
        self.assertEqual(overall["usage"]["total_tokens"]["count"], 2)

    def test_grammar_aggregation_keeps_rounds_separate_and_counts_boards(self):
        attempts = [
            _attempt(case_id="r0-g0-b0", board=0),
            _attempt(
                case_id="r0-g0-b1",
                board=1,
                overall=False,
                failure_type="rack",
            ),
            _attempt(case_id="r0-g1-b0", grammar=1, board=0),
            _attempt(case_id="r0-g1-b1", grammar=1, board=1),
            _attempt(
                case_id="r1-g0-b0",
                sampling_round=1,
                board=0,
                overall=False,
                failure_type="word_extension",
            ),
        ]

        grammars = build_aggregate(attempts)["groups"][0]["grammars"]

        self.assertEqual(
            [
                (
                    grammar["sampling_round"],
                    grammar["grammar_sample_index"],
                    grammar["total_attempts"],
                    grammar["pass_rate"],
                )
                for grammar in grammars
            ],
            [
                (0, 0, 2, 0.5),
                (0, 1, 2, 1.0),
                (1, 0, 1, 0.0),
            ],
        )
        self.assertEqual(grammars[0]["primary_failures"], {"rack": 1})
        self.assertEqual(
            grammars[2]["primary_failures"],
            {"word_extension": 1},
        )

    def test_explicit_reasoning_effort_takes_precedence_over_legacy_metadata(self):
        aggregate = build_aggregate(
            [
                _attempt(
                    case_id="explicit",
                    reasoning_effort="low",
                    model_config={"reasoning_depth": "high"},
                ),
                _attempt(
                    case_id="legacy",
                    reasoning_effort=None,
                    model_config={"reasoning_depth": "high"},
                ),
            ]
        )

        self.assertEqual(
            {
                (group["reasoning_effort"], group["completed"])
                for group in aggregate["groups"]
            },
            {("low", 1), ("high", 1)},
        )

    def test_compact_summary_uses_weighted_counts_across_groups(self):
        attempts = [
            _attempt(case_id="a", model="model-a"),
            _attempt(
                case_id="b",
                model="model-b",
                overall=False,
                failure_type="rack",
            ),
            _attempt(
                case_id="c",
                model="model-b",
                overall=False,
                failure_type="rack",
            ),
            _transport_attempt(case_id="d", model="model-b"),
        ]

        summary = compact_summary(build_aggregate(attempts))

        self.assertEqual(summary["completed"], 3)
        self.assertEqual(summary["transport_errors"], 1)
        self.assertEqual(summary["by_tier"]["low"]["total"], 3)
        self.assertEqual(summary["by_tier"]["low"]["passed"], 1)
        self.assertAlmostEqual(summary["by_tier"]["low"]["pass_rate"], 1 / 3)
        self.assertEqual(summary["by_tier"]["low"]["transport_errors"], 1)
        self.assertEqual(summary["by_model"]["model-b"]["total"], 2)
        self.assertEqual(summary["by_model"]["model-b"]["transport_errors"], 1)

    def test_result_rows_use_scope_specific_denominators_and_dimensions(self):
        aggregate = build_aggregate(
            [
                _attempt(case_id="pass"),
                _attempt(
                    case_id="fail",
                    overall=False,
                    failure_type="rack",
                    false_constraints=("rack_valid",),
                ),
                _transport_attempt(case_id="transport"),
            ]
        )
        rows = list(iter_result_rows(aggregate))

        failed = _row(rows, "overall", "outcome", "failed")
        transport = _row(rows, "overall", "outcome", "transport_errors")
        primary = _row(rows, "overall", "primary_failure", "rack")
        constraint = _row(
            rows,
            "overall",
            "failed_constraint",
            "rack_valid",
        )
        grammar = _row(rows, "grammar", "outcome", "passed")
        group_timing = _row(
            rows,
            "group",
            "timing",
            "llm_elapsed_seconds_mean",
        )

        self.assertEqual(
            (failed["count"], failed["denominator"], failed["rate"]),
            (1, 2, 0.5),
        )
        self.assertEqual(
            (transport["count"], transport["denominator"], transport["rate"]),
            (1, 3, 1 / 3),
        )
        self.assertEqual(
            (primary["count"], primary["denominator"], primary["rate"]),
            (1, 1, 1.0),
        )
        self.assertEqual(
            (constraint["count"], constraint["denominator"], constraint["rate"]),
            (1, 2, 0.5),
        )
        self.assertEqual(grammar["sampling_round"], 0)
        self.assertEqual(grammar["grammar_sample_index"], 0)
        self.assertEqual(grammar["reasoning_effort"], "high")
        self.assertEqual(group_timing["value"], 1.0)

    def test_csv_round_trip_preserves_empty_and_numeric_metric_shapes(self):
        aggregate = build_aggregate(
            [
                _attempt(case_id="pass"),
                _transport_attempt(case_id="transport"),
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = write_results_csv(
                Path(temp_dir) / "nested" / "results.csv",
                aggregate,
            )
            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        outcome = _row(rows, "overall", "outcome", "passed")
        timing = _row(
            rows,
            "overall",
            "timing",
            "llm_elapsed_seconds_mean",
        )
        self.assertEqual(outcome["count"], "1")
        self.assertEqual(outcome["denominator"], "1")
        self.assertEqual(outcome["value"], "")
        self.assertEqual(timing["count"], "")
        self.assertEqual(timing["denominator"], "")
        self.assertEqual(timing["value"], "1.0")

    def test_empty_aggregate_has_no_fabricated_rates_or_resource_values(self):
        aggregate = build_aggregate([])
        overall = aggregate["overall"]
        rows = list(iter_result_rows(aggregate))

        self.assertEqual(overall["total_attempts"], 0)
        self.assertIsNone(overall["pass_rate"])
        self.assertEqual(overall["primary_failures"], {})
        self.assertIsNone(overall["usage"]["total_tokens"]["mean"])
        self.assertEqual(aggregate["groups"], [])
        self.assertTrue(
            all(
                row["rate"] is None
                for row in rows
                if row["metric_category"] in {"outcome", "failed_constraint"}
            )
        )
        self.assertFalse(
            any(row["metric_category"] in {"timing", "usage"} for row in rows)
        )


class ResultIndexTests(unittest.TestCase):
    def test_index_separates_efforts_representations_and_ignores_incomplete_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "case-set"
            case_file = case_root / "cases" / "shared-case.json"
            write_json_atomic(
                case_file,
                {
                    "tier": "low",
                    "sampling_round": 0,
                    "grammar_sample_index": 0,
                    "board_sample_index": 0,
                },
            )
            older_high = _attempt(
                case_id=None,
                overall=False,
                failure_type="rack",
                reasoning_effort=None,
                model_config={"reasoning_effort": "high"},
            )
            older_high["case_file"] = str(case_file)
            low = _attempt(
                case_id=None,
                reasoning_effort="low",
            )
            low["case_file"] = str(case_file)
            alternate_representation = _attempt(
                case_id=None,
                representation="automaton",
            )
            alternate_representation["case_file"] = str(case_file)
            _write_run(
                case_root / "runs" / "older",
                status="complete",
                completed_at="2026-06-01T10:00:00+00:00",
                attempts=[older_high, low, alternate_representation],
            )
            newer_high = _attempt(
                case_id=None,
                reasoning_effort="high",
            )
            newer_high["case_file"] = str(case_file)
            _write_run(
                case_root / "runs" / "newer",
                status="complete",
                completed_at="2026-06-02T10:00:00+00:00",
                attempts=[newer_high],
            )
            _write_run(
                case_root / "runs" / "incomplete",
                status="incomplete",
                completed_at=None,
                attempts=[
                    _attempt(
                        case_id="ignored",
                        model="ignored-model",
                    )
                ],
            )

            index = load_or_build_result_index(case_root)

        self.assertEqual(index["source_attempts"], 4)
        self.assertEqual(index["indexed_attempts"], 3)
        self.assertEqual(index["overwritten_attempts"], 1)
        self.assertEqual(len(index["source_runs"]), 2)
        groups = index["aggregate"]["groups"]
        self.assertEqual(
            {
                (group["language_representation"], group["reasoning_effort"])
                for group in groups
            },
            {
                ("forbidden-snippets", "high"),
                ("forbidden-snippets", "low"),
                ("automaton", "high"),
            },
        )
        self.assertEqual(index["aggregate"]["overall"]["passed"], 3)
        self.assertNotIn(
            "ignored-model",
            {group["model"] for group in groups},
        )

    def test_cached_index_rebuilds_when_completed_run_set_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "case-set"
            _write_run(
                case_root / "runs" / "first",
                status="complete",
                completed_at="2026-06-01T10:00:00+00:00",
                attempts=[_attempt(case_id="case-a")],
            )
            first = load_or_build_result_index(case_root)
            cached = load_or_build_result_index(case_root)
            self.assertEqual(first["updated_at"], cached["updated_at"])

            _write_run(
                case_root / "runs" / "second",
                status="complete",
                completed_at="2026-06-02T10:00:00+00:00",
                attempts=[_attempt(case_id="case-b")],
            )
            rebuilt = load_or_build_result_index(case_root)
            persisted = read_json(case_root / "results-index.json")

        self.assertEqual(rebuilt["indexed_attempts"], 2)
        self.assertEqual(len(rebuilt["source_runs"]), 2)
        self.assertEqual(persisted["source_runs"], rebuilt["source_runs"])


def _attempt(
    *,
    case_id: str | None,
    model: str = "gpt-5-mini",
    representation: str = "forbidden-snippets",
    reasoning_effort: str | None = "high",
    model_config: dict[str, Any] | None = None,
    overall: bool = True,
    failure_type: str | None = None,
    retry_count: int = 0,
    elapsed: Any = 1.0,
    provider_ms: Any = "900",
    prompt_tokens: Any = 10,
    completion_tokens: Any = 8,
    reasoning_tokens: Any = 5,
    total_tokens: Any = 18,
    false_constraints: tuple[str, ...] = (),
    sampling_round: int = 0,
    grammar: int = 0,
    board: int = 0,
) -> dict[str, Any]:
    constraints = {
        "parse_ok": True,
        "sequence_valid": True,
        "min_length_fulfilled": True,
        "spatial_valid": True,
        "overlap_valid": True,
        "no_word_extension": True,
        "cross_words_valid": True,
        "rack_valid": True,
    }
    for constraint in false_constraints:
        constraints[constraint] = False
    attempt = {
        "status": "complete",
        "tier": "low",
        "sampling_round": sampling_round,
        "grammar_sample_index": grammar,
        "board_sample_index": board,
        "model": model,
        "language_representation": representation,
        "reasoning_effort": reasoning_effort,
        "model_config": model_config or {},
        "retry_count": retry_count,
        "llm_elapsed_seconds": elapsed,
        "provider_metadata": {"provider_processing_ms": provider_ms},
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "completion_tokens_details": {
                "reasoning_tokens": reasoning_tokens,
            },
        },
        "evaluation": {
            "overall": overall,
            "failure_type": failure_type,
            **constraints,
        },
    }
    if case_id is not None:
        attempt["case_id"] = case_id
    return attempt


def _transport_attempt(
    *,
    case_id: str,
    model: str = "gpt-5-mini",
    retry_count: int = 0,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "transport_error",
        "tier": "low",
        "sampling_round": 0,
        "grammar_sample_index": 0,
        "board_sample_index": 0,
        "model": model,
        "language_representation": "forbidden-snippets",
        "reasoning_effort": "high",
        "retry_count": retry_count,
    }


def _row(
    rows: list[dict[str, Any]],
    scope: str,
    category: str,
    name: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row["scope"] == scope
        and row["metric_category"] == category
        and row["metric_name"] == name
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one row for {(scope, category, name)}, got {matches}"
        )
    return matches[0]


def _write_run(
    run_dir: Path,
    *,
    status: str,
    completed_at: str | None,
    attempts: list[dict[str, Any]],
) -> None:
    write_json_atomic(
        run_dir / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": run_dir.name,
            "config_hash": run_dir.name,
            "status": status,
            "completed_at": completed_at,
        },
    )
    for index, attempt in enumerate(attempts):
        write_json_atomic(
            run_dir / "attempts" / f"attempt-{index}.json",
            attempt,
        )


if __name__ == "__main__":
    unittest.main()
