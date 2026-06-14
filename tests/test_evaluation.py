from __future__ import annotations

import asyncio
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import litellm
from pydantic import BaseModel

from src.configuration import NamedYamlConfigSource
from src.evaluation.artifacts import read_json, write_json_atomic
from src.evaluation.config import CaseSetConfig, RunConfig
from src.evaluation.decomposition import decompose_run
from src.evaluation.job_execution import (
    ModelCooldowns,
    execute_with_retries,
    parse_duration,
    retry_delay,
)
from src.evaluation.jobs import build_evaluation_jobs
from src.evaluation.prepare import prepare_case_set
from src.evaluation.result_aggregation import build_aggregate
from src.evaluation.runner import _pending_jobs, evaluate_run
from src.evaluation.run_artifacts import finalize_run, summarize_attempts
from src.evaluation.sampling import derive_seed, sample_axis
from src.formal.grammar.config import load_grammar_config
from src.generator.config import (
    load_generator_config,
    resolve_grammar_path,
    resolve_output_path,
)
from src.llm.client import LLMCallResult
from src.llm.env import ENV
from visualization.evaluation_figures import (
    latest_completed_case_set,
    load_evaluation_results,
    plot_grammar_pass_rates,
    plot_latency_tables,
    plot_pass_rate_heatmaps,
    plot_primary_failure_bars,
    plot_token_usage_bars,
)


class ExampleConfig(BaseModel):
    config_name: str
    value: int


def tiny_case_set(*, boards: int = 1) -> CaseSetConfig:
    return CaseSetConfig.model_validate(
        {
            "config_name": "tiny",
            "generation_config": "evaluation_base",
            "grammar_config": "evaluation_base",
            "root_seed": 7,
            "sampling_rounds": 1,
            "grammar_samples_per_tier": 1,
            "boards_per_grammar": boards,
            "tiers": {
                "low": {
                    "dimensions": 2,
                    "board_depth": {"min": 0, "max": 1},
                    "additional_rack_noise": 0,
                    "alphabet_size": 3,
                    "forbidden_fraction": 0.15,
                    "k": 2,
                }
            },
        }
    )


def tiny_run(*, concurrency: int = 2) -> RunConfig:
    model_name = ENV.get_registered_model_names()[0]
    return RunConfig.model_validate(
        {
            "config_name": "tiny_run",
            "case_set": "tiny",
            "models": {model_name: ["low"]},
            "language_representations": ["forbidden-snippets"],
            "reasoning_effort": "low",
            "execution": {
                "max_concurrency": concurrency,
                "max_retries": 0,
            },
        }
    )


class EvaluationConfigTests(unittest.TestCase):
    def test_evaluation_plots_sort_failures_and_expose_resources(self):
        aggregate = _plot_aggregate()

        failure_figure = plot_primary_failure_bars(aggregate)[0]
        self.assertEqual(
            [trace.name for trace in failure_figure.data],
            ["word_extension", "rack"],
        )
        self.assertEqual(
            [trace.y[0] for trace in failure_figure.data],
            [0.8, 0.2],
        )
        self.assertEqual(
            failure_figure.layout.legend.traceorder,
            "reversed",
        )
        self.assertIn(
            "<b>Tier:</b> low",
            failure_figure.layout.title.text,
        )
        self.assertIn(
            "<b>Representation:</b> forbidden-snippets",
            failure_figure.layout.title.text,
        )
        self.assertIn(
            "<b>Reasoning:</b> high",
            failure_figure.layout.title.text,
        )
        self.assertIn(
            "<b>Tier:</b> low<br><b>Representation:</b>",
            failure_figure.layout.title.text,
        )
        self.assertIn(
            "forbidden-snippets<br><b>Reasoning:</b> high",
            failure_figure.layout.title.text,
        )
        self.assertEqual(failure_figure.layout.title.xref, "paper")
        self.assertEqual(failure_figure.layout.title.y, 0.90)
        self.assertEqual(failure_figure.layout.title.yanchor, "top")
        self.assertEqual(failure_figure.layout.margin.t, 155)

        grammar_figure = plot_grammar_pass_rates(aggregate)[0]
        self.assertEqual(
            list(grammar_figure.data[0].x),
            ["Grammar 1", "Grammar 2"],
        )
        self.assertEqual(
            list(grammar_figure.data[0].customdata[0]),
            ["r00.g00", "r00.g01"],
        )
        self.assertEqual(list(grammar_figure.data[0].z[0]), [0.25, 0.75])

        token_figure = plot_token_usage_bars(aggregate)[0]
        self.assertEqual(
            [trace.name for trace in token_figure.data],
            ["prompt", "reasoning", "visible output"],
        )
        self.assertEqual(
            [trace.y[0] for trace in token_figure.data],
            [100.0, 60.0, 20.0],
        )

        latency_figure = plot_latency_tables(aggregate)[0]
        self.assertEqual(
            list(latency_figure.data[0].cells.values[0]),
            ["GPT-5 Nano", "GPT-5 Mini", "GPT-5", "test-model"],
        )
        self.assertEqual(
            list(latency_figure.data[0].cells.values[1]),
            ["-", "-", "-", "12.50 s"],
        )
        self.assertEqual(len(plot_latency_tables(aggregate)), 1)

    def test_pooled_result_index_keeps_distinct_cells_and_uses_latest_attempt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case_root = (
                project_root / "outputs" / "evaluation" / "tiny"
            )
            older = case_root / "runs" / "older"
            newer = case_root / "runs" / "newer"
            _write_completed_run(
                older,
                completed_at="2026-06-01T10:00:00+00:00",
                attempts=[
                    {
                        **_attempt(
                            overall=False,
                            grammar=0,
                            failure_type="rack",
                        ),
                        "case_id": "case-a",
                        "reasoning_effort": "high",
                    },
                    {
                        **_attempt(
                            overall=True,
                            model="gpt-5",
                            grammar=0,
                        ),
                        "case_id": "case-a",
                        "reasoning_effort": "high",
                    },
                ],
            )
            _write_completed_run(
                newer,
                completed_at="2026-06-02T10:00:00+00:00",
                attempts=[
                    {
                        **_attempt(overall=True, grammar=0),
                        "case_id": "case-a",
                        "reasoning_effort": "high",
                    }
                ],
            )

            source, aggregate = load_evaluation_results(
                "tiny",
                project_root=project_root,
            )
            index = read_json(source)
            run_source, older_aggregate = load_evaluation_results(
                "tiny",
                "older",
                project_root=project_root,
            )

        self.assertEqual(source.name, "results-index.json")
        self.assertEqual(run_source.name, "older")
        self.assertEqual(index["source_attempts"], 3)
        self.assertEqual(index["indexed_attempts"], 2)
        self.assertEqual(index["overwritten_attempts"], 1)
        self.assertEqual(index["latest_completed_run_id"], "newer")
        self.assertEqual(aggregate["overall"]["passed"], 2)
        self.assertEqual(
            {group["model"] for group in aggregate["groups"]},
            {"gpt-5-mini", "gpt-5"},
        )
        self.assertEqual(older_aggregate["overall"]["passed"], 1)
        self.assertEqual(older_aggregate["overall"]["failed"], 1)

    def test_evaluation_plots_include_all_models_and_tiers_in_pool(self):
        aggregate = _multi_group_plot_aggregate()

        pass_figure = plot_pass_rate_heatmaps(aggregate)[0]
        self.assertEqual(list(pass_figure.data[0].x), ["low", "medium", "high"])
        self.assertEqual(
            list(pass_figure.data[0].y),
            ["gpt-5", "gpt-5-mini"],
        )
        self.assertEqual(
            [list(row) for row in pass_figure.data[0].z],
            [[None, 0.8, None], [0.4, 0.6, 0.2]],
        )

        failure_figure = plot_primary_failure_bars(aggregate)[0]
        self.assertEqual(
            sorted({value for trace in failure_figure.data for value in trace.x}),
            [
                "gpt-5 · medium",
                "gpt-5-mini · high",
                "gpt-5-mini · low",
                "gpt-5-mini · medium",
            ],
        )
        self.assertEqual(
            list(failure_figure.layout.xaxis.categoryarray),
            [
                "gpt-5 · medium",
                "gpt-5-mini · low",
                "gpt-5-mini · medium",
                "gpt-5-mini · high",
            ],
        )

        grammar_figures = plot_grammar_pass_rates(aggregate)
        self.assertEqual(len(grammar_figures), 3)
        self.assertEqual(
            {
                tuple(figure.data[0].y)
                for figure in grammar_figures
            },
            {
                ("gpt-5-mini",),
                ("gpt-5", "gpt-5-mini"),
            },
        )

        token_figure = plot_token_usage_bars(aggregate)[0]
        self.assertEqual(
            list(token_figure.data[0].x),
            [
                "gpt-5 · medium",
                "gpt-5-mini · low",
                "gpt-5-mini · medium",
                "gpt-5-mini · high",
            ],
        )

        runtime_figure = plot_latency_tables(aggregate)[0]
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[0]),
            ["GPT-5 Nano", "GPT-5 Mini", "GPT-5"],
        )
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[1]),
            ["-", "10.00 s", "-"],
        )
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[2]),
            ["-", "20.00 s", "25.00 s"],
        )
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[3]),
            ["-", "30.00 s", "-"],
        )

    def test_none_case_set_selects_newest_completed_run_and_ignores_in_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            older_root = (
                project_root / "outputs" / "evaluation" / "older"
            )
            newer_root = (
                project_root / "outputs" / "evaluation" / "newer"
            )
            incomplete_root = (
                project_root / "outputs" / "evaluation" / "incomplete"
            )
            _write_completed_run(
                older_root / "runs" / "run-a",
                completed_at="2026-06-01T10:00:00+00:00",
                attempts=[_attempt(overall=True, grammar=0)],
                case_set="older",
            )
            _write_completed_run(
                newer_root / "runs" / "run-b",
                completed_at="2026-06-02T10:00:00+00:00",
                attempts=[_attempt(overall=True, grammar=0)],
                case_set="newer",
            )
            _write_run_manifest(
                incomplete_root / "runs" / "run-c",
                case_set="incomplete",
                status="in_progress",
                completed_at=None,
            )

            selected = latest_completed_case_set(project_root=project_root)
            source, aggregate = load_evaluation_results(
                None,
                project_root=project_root,
            )

        self.assertEqual(selected, "newer")
        self.assertEqual(source.parent.name, "newer")
        self.assertEqual(aggregate["overall"]["completed"], 1)

    def test_model_specific_tiers_expand_to_expected_jobs(self):
        model_names = ENV.get_registered_model_names()
        config = RunConfig.model_validate(
            {
                "config_name": "model_tiers",
                "case_set": "tiny",
                "models": {
                    model_names[0]: ["low", "medium"],
                    model_names[1]: ["high"],
                },
                "language_representations": ["forbidden-snippets"],
                "reasoning_effort": "high",
            }
        )
        jobs = build_evaluation_jobs(
            config,
            {
                "cases": {
                    tier: {
                        "tier": tier,
                        "path": f"outputs/evaluation/tiny/cases/{tier}.json",
                    }
                    for tier in ("low", "medium", "high")
                }
            },
        )

        self.assertEqual(len(jobs), 3)
        self.assertEqual(len({job.job_id for job in jobs}), 3)
        self.assertEqual(
            {(job.model_name, job.case_path.stem) for job in jobs},
            {
                (model_names[0], "low"),
                (model_names[0], "medium"),
                (model_names[1], "high"),
            },
        )
        self.assertTrue(
            all(job.reasoning_effort == "high" for job in jobs)
        )

    def test_summary_groups_models_tiers_failures_and_constraints(self):
        attempts = [
            _attempt(overall=True, grammar=0),
            _attempt(
                overall=False,
                grammar=0,
                failure_type="word_extension",
                no_word_extension=False,
            ),
            _attempt(
                overall=False,
                model="other-model",
                grammar=1,
                failure_type="invalid_cross_word",
                cross_words_valid=False,
            ),
        ]

        summary = summarize_attempts(attempts)

        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["primary_failures"]["word_extension"], 1)
        self.assertEqual(summary["failed_constraints"]["cross_words_valid"], 1)
        self.assertEqual(summary["by_tier"]["low"]["total"], 3)
        self.assertEqual(summary["by_model"]["gpt-5-mini"]["total"], 2)
        self.assertEqual(len(summary["by_group"]), 2)

    def test_aggregate_reports_word_length_and_overlap_quality_metrics(self):
        attempts = [
            _attempt(overall=True, grammar=0, main_word_length=3, overlap_count=1),
            _attempt(overall=True, grammar=0, main_word_length=5, overlap_count=3),
            _attempt(
                overall=False,
                grammar=0,
                failure_type="word_extension",
                no_word_extension=False,
            ),
        ]

        aggregate = build_aggregate(attempts)

        main_word_length = aggregate["overall"]["quality"]["main_word_length"]
        overlap_count = aggregate["overall"]["quality"]["overlap_count"]
        self.assertEqual(main_word_length["count"], 2)
        self.assertEqual(main_word_length["mean"], 4.0)
        self.assertEqual(overlap_count["count"], 2)
        self.assertEqual(overlap_count["mean"], 2.0)

    def test_exhausted_transport_error_finishes_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "case-set" / "runs" / "run"
            write_json_atomic(
                run_dir / "attempts" / "timeout.json",
                {
                    "status": "transport_error",
                    "retryable": True,
                    "retry_count": 0,
                    "llm_elapsed_seconds_total": 600.0,
                },
            )
            manifest = {
                "run_id": "run",
                "config_hash": "hash",
                "status": "in_progress",
                "config": {"execution": {"max_retries": 0}},
            }

            finalize_run(run_dir, manifest)

        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["error_jobs"], 1)
        self.assertIsNotNone(manifest["completed_at"])

    def test_named_yaml_source_derives_name_and_rejects_explicit_config_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = NamedYamlConfigSource(root, "example", ValueError)
            (root / "valid.yaml").write_text("value: 3\n", encoding="utf-8")
            (root / "invalid.yaml").write_text(
                "config_name: manual\nvalue: 3\n",
                encoding="utf-8",
            )

            loaded = source.load("valid", ExampleConfig)
            self.assertEqual(loaded.config_name, "valid")
            with self.assertRaisesRegex(ValueError, "must be omitted"):
                source.load("invalid", ExampleConfig)
            with self.assertRaisesRegex(ValueError, "without path or suffix"):
                source.load("valid.yaml", ExampleConfig)

    def test_standalone_config_ids_resolve_paths_without_yaml_fields(self):
        grammar = load_grammar_config("generator_v1_grammar")
        generation = load_generator_config("generator_v1")

        self.assertEqual(grammar.config_name, "generator_v1_grammar")
        self.assertEqual(generation.config_name, "generator_v1")
        self.assertEqual(generation.grammar, "generator_v1_grammar")
        self.assertTrue(str(resolve_grammar_path(generation)).endswith(
            "outputs/grammars/generator_v1_grammar.json"
        ))
        self.assertTrue(str(resolve_output_path(generation)).endswith(
            "outputs/scenarios/generator_v1.json"
        ))

    def test_truncated_normal_sampling_is_deterministic_and_bounded(self):
        axis = tiny_case_set().tiers["low"].board_depth
        seed = derive_seed(42, "low", 0, 0)

        first = sample_axis(axis, seed=seed, integer=True)
        second = sample_axis(axis, seed=seed, integer=True)

        self.assertEqual(first, second)
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 1)

    def test_retry_delay_uses_provider_reset_headers(self):
        exception = RuntimeError("rate limited")
        exception.response = SimpleNamespace(
            headers={
                "x-ratelimit-reset-requests": "1m2s",
                "x-ratelimit-reset-tokens": "250ms",
            }
        )

        self.assertEqual(parse_duration("1m2s"), 62)
        self.assertEqual(retry_delay(exception, retry_index=0), 62)

    def test_prepare_materializes_snapshot_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root):
                manifest = prepare_case_set(tiny_case_set())

            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(len(manifest["grammars"]), 1)
            self.assertEqual(len(manifest["scenarios"]), 1)
            self.assertEqual(len(manifest["cases"]), 1)
            self.assertEqual(len(manifest["schemas"]), 3)
            case_path = next((root / "tiny" / "cases").glob("*.json"))
            case = read_json(case_path)

        self.assertEqual(case["tier"], "low")
        self.assertIn("grammar", case)
        self.assertIn("board", case)
        self.assertIn("rack", case)
        self.assertIn("grammar_sha256", case["provenance"])


class AsyncEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_evaluate_limits_global_concurrency_and_decomposes_failures(self):
        active = 0
        peak = 0
        observed_reasoning_efforts: list[str | None] = []
        observed_prompts: list[str] = []
        progress_updates: list[tuple[int, int]] = []

        async def fake_call(
            _system: str,
            _user: str,
            _model: str,
            *,
            reasoning_effort: str | None = None,
        ) -> LLMCallResult:
            nonlocal active, peak
            observed_reasoning_efforts.append(reasoning_effort)
            observed_prompts.append(_user)
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
            return LLMCallResult(
                content='{"start":[0,0],"axis":0,"sequence":["A"]}',
                usage={"total_tokens": 1},
                metadata={"backend": "test"},
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root),
                patch("src.evaluation.runner.EVALUATION_OUTPUT_DIR", root),
                patch("src.evaluation.decomposition.EVALUATION_OUTPUT_DIR", root),
            ):
                prepare_case_set(tiny_case_set(boards=3))
                with patch(
                    "src.evaluation.runner.acall_llm_detailed",
                    side_effect=fake_call,
                ):
                    result = await evaluate_run(
                        tiny_run(concurrency=2),
                        progress_callback=lambda finished, total: (
                            progress_updates.append((finished, total))
                        ),
                    )
                decomposition = await decompose_run(tiny_run(concurrency=2))

            attempts = list(
                (Path(result["run_dir"]) / "attempts").glob("*.json")
            )
            attempt_data = [read_json(path) for path in attempts]
            aggregate_path = Path(result["run_dir"]) / "aggregate.json"
            results_path = Path(result["run_dir"]) / "results.csv"
            aggregate = read_json(aggregate_path)
            with results_path.open(encoding="utf-8", newline="") as handle:
                result_rows = list(csv.DictReader(handle))

        self.assertEqual(len(attempts), 3)
        self.assertEqual(result["summary"]["completed"], 3)
        self.assertEqual(observed_reasoning_efforts, ["low", "low", "low"])
        self.assertEqual(len(set(observed_prompts)), 3)
        self.assertEqual(
            progress_updates,
            [(0, 3), (1, 3), (2, 3), (3, 3)],
        )
        self.assertTrue(
            all(item["reasoning_effort"] == "low" for item in attempt_data)
        )
        self.assertTrue(
            all(item["request_attempt_count"] == 1 for item in attempt_data)
        )
        self.assertTrue(
            all(item["failed_attempts"] == [] for item in attempt_data)
        )
        self.assertTrue(
            all("prompt_sha256" in item for item in attempt_data)
        )
        self.assertEqual(len(aggregate["groups"]), 1)
        self.assertTrue(
            any(
                row["scope"] == "group"
                and row["metric_category"] == "outcome"
                and row["metric_name"] == "failed"
                for row in result_rows
            )
        )
        self.assertGreaterEqual(peak, 2)
        self.assertLessEqual(peak, 2)
        self.assertEqual(decomposition["processed"], 3)

    async def test_retry_diagnostics_include_failed_call_time(self):
        calls = 0

        async def fake_execute(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                error = litellm.Timeout(
                    "timed out",
                    model="gpt-5",
                    llm_provider="openai",
                )
                error._benchmark_llm_elapsed_seconds = 1200.0
                raise error
            return {"llm_elapsed_seconds": 250.0}

        with (
            patch(
                "src.evaluation.job_execution._execute_after_cooldown",
                side_effect=fake_execute,
            ),
            patch("src.evaluation.job_execution.retry_delay", return_value=0.0),
        ):
            result = await execute_with_retries(
                SimpleNamespace(model_name="gpt-5"),
                semaphore=asyncio.Semaphore(1),
                max_retries=1,
                cooldowns=ModelCooldowns(),
                call_llm=SimpleNamespace(),
            )

        self.assertEqual(result["request_attempt_count"], 2)
        self.assertEqual(result["llm_elapsed_seconds_total"], 1450.0)
        self.assertEqual(result["retry_wait_seconds_total"], 0.0)
        self.assertEqual(result["failed_attempts"][0]["elapsed_seconds"], 1200.0)

    async def test_pending_jobs_excludes_already_final_attempts(self):
        jobs = [
            SimpleNamespace(job_id="done"),
            SimpleNamespace(job_id="retryable"),
            SimpleNamespace(job_id="missing"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            write_json_atomic(
                run_dir / "attempts" / "done.json",
                {"status": "complete"},
            )
            write_json_atomic(
                run_dir / "attempts" / "retryable.json",
                {
                    "status": "transport_error",
                    "retryable": True,
                },
            )

            pending = _pending_jobs(jobs, run_dir, "config-hash")

        self.assertEqual(
            {job.job_id for job in pending},
            {"retryable", "missing"},
        )


def _attempt(
    *,
    overall: bool,
    model: str = "gpt-5-mini",
    grammar: int,
    failure_type: str | None = None,
    no_word_extension: bool = True,
    cross_words_valid: bool = True,
    main_word_length: int | None = None,
    overlap_count: int | None = None,
) -> dict[str, object]:
    return {
        "status": "complete",
        "tier": "low",
        "model": model,
        "language_representation": "forbidden-snippets",
        "sampling_round": 0,
        "grammar_sample_index": grammar,
        "board_sample_index": 0,
        "retry_count": 0,
        "llm_elapsed_seconds": 1.0,
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "completion_tokens_details": {"reasoning_tokens": 15},
        },
        "provider_metadata": {"provider_processing_ms": "900"},
        "evaluation": {
            "overall": overall,
            "failure_type": failure_type,
            "parse_ok": True,
            "sequence_valid": True,
            "min_length_fulfilled": True,
            "spatial_valid": True,
            "overlap_valid": True,
            "no_word_extension": no_word_extension,
            "cross_words_valid": cross_words_valid,
            "rack_valid": True,
            "main_word_length": main_word_length,
            "overlap_count": overlap_count,
        },
    }


def _plot_aggregate() -> dict[str, object]:
    return {
        "groups": [
            {
                "tier": "low",
                "model": "test-model",
                "reasoning_effort": "high",
                "language_representation": "forbidden-snippets",
                "completed": 10,
                "failed": 10,
                "pass_rate": 0.5,
                "primary_failures": {
                    "rack": 2,
                    "word_extension": 8,
                },
                "failed_constraints": {},
                "usage": {
                    "prompt_tokens": {"mean": 100},
                    "completion_tokens": {"mean": 80},
                    "reasoning_tokens": {"mean": 60},
                },
                "timing": {
                    "request_elapsed_seconds": {"mean": 12.5},
                    "llm_elapsed_seconds": {
                        "mean": 12.5,
                        "median": 10.0,
                    },
                    "provider_processing_ms": {"median": 9000.0},
                },
                "quality": {
                    "rack_usage_ratio": {"mean": 0.75},
                },
                "grammars": [
                    {
                        "sampling_round": 0,
                        "grammar_sample_index": 0,
                        "pass_rate": 0.25,
                    },
                    {
                        "sampling_round": 0,
                        "grammar_sample_index": 1,
                        "pass_rate": 0.75,
                    },
                ],
            }
        ]
    }


def _multi_group_plot_aggregate() -> dict[str, object]:
    groups = []
    for model, tier, pass_rate, runtime in (
        ("gpt-5-mini", "low", 0.4, 10),
        ("gpt-5-mini", "medium", 0.6, 20),
        ("gpt-5-mini", "high", 0.2, 30),
        ("gpt-5", "medium", 0.8, 25),
    ):
        group = dict(_plot_aggregate()["groups"][0])
        group.update(
            {
                "model": model,
                "tier": tier,
                "pass_rate": pass_rate,
                "timing": {
                    "request_elapsed_seconds": {"mean": runtime},
                    "llm_elapsed_seconds": {"mean": runtime},
                },
            }
        )
        groups.append(group)
    return {"groups": groups}


def _write_completed_run(
    run_dir: Path,
    *,
    completed_at: str,
    attempts: list[dict[str, object]],
    case_set: str | None = None,
) -> None:
    _write_run_manifest(
        run_dir,
        case_set=case_set,
        status="complete",
        completed_at=completed_at,
    )
    for index, attempt in enumerate(attempts):
        write_json_atomic(
            run_dir / "attempts" / f"attempt-{index}.json",
            attempt,
        )
    write_json_atomic(run_dir / "aggregate.json", build_aggregate(attempts))


def _write_run_manifest(
    run_dir: Path,
    *,
    case_set: str | None,
    status: str,
    completed_at: str | None,
) -> None:
    write_json_atomic(
        run_dir / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": run_dir.name,
            "case_set": case_set,
            "config_hash": run_dir.name,
            "status": status,
            "completed_at": completed_at,
        },
    )


if __name__ == "__main__":
    unittest.main()
