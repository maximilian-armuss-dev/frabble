from __future__ import annotations

import asyncio
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import litellm
from openrouter import errors as openrouter_errors
from pydantic import BaseModel

from src.configuration import NamedYamlConfigSource
from src.evaluation.artifacts import read_json, write_json_atomic
from src.evaluation.config import (
    CaseSetConfig,
    NumericRange,
    RunConfig,
    load_case_set_config,
)
from src.evaluation.decomposition import decompose_run
from src.evaluation.job_execution import (
    ModelCooldowns,
    _execute_after_cooldown,
    execute_with_retries,
    exception_details,
    is_retryable,
    parse_duration,
    retry_delay,
    transport_error_result,
)
from src.evaluation.jobs import (
    EVALUATION_REASONING_EFFORT,
    build_evaluation_jobs,
    evaluation_reasoning_effort,
)
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


def tiny_case_set(*, board_sizes: list[int] | None = None) -> CaseSetConfig:
    return CaseSetConfig.model_validate(
        {
            "config_name": "tiny",
            "generation_config": "evaluation_base",
            "grammar_config": "evaluation_base_grammar",
            "root_seed": 7,
            "sampling_rounds": 1,
            "board_sizes": board_sizes or [0],
        }
    )


def tiny_run(
    *,
    concurrency: int = 2,
    concurrency_per_model: int | None = None,
) -> RunConfig:
    model_name = ENV.get_registered_model_names()[0]
    return RunConfig.model_validate(
        {
            "config_name": "tiny_run",
            "case_set": "tiny",
            "models": {model_name: ["all"]},
            "execution": {
                "max_concurrency": concurrency,
                "max_concurrency_per_model": concurrency_per_model,
                "max_retries": 0,
            },
        }
    )


class EvaluationConfigTests(unittest.TestCase):
    def test_case_set_loads_board_sizes(self):
        config = load_case_set_config("1r_10-50-150")

        self.assertEqual(config.board_sizes, [10, 50, 150])
        self.assertEqual(config.sampling_rounds, 1)
        self.assertNotIn("tiers", config.model_dump(mode="json"))

    def test_evaluation_rejects_obsolete_reasoning_config(self):
        payload = tiny_run().model_dump(mode="json")
        payload["reasoning_effort"] = "high"

        with self.assertRaisesRegex(ValueError, "Extra inputs are not permitted"):
            RunConfig.model_validate(payload)

    def test_evaluation_rejects_obsolete_language_representation_config(self):
        payload = tiny_run().model_dump(mode="json")
        payload["language_representations"] = ["forbidden-snippets"]

        with self.assertRaisesRegex(ValueError, "Extra inputs are not permitted"):
            RunConfig.model_validate(payload)

    def test_evaluation_rejects_mixed_all_and_board_sizes(self):
        payload = tiny_run().model_dump(mode="json")
        model_name = next(iter(payload["models"]))
        payload["models"][model_name] = ["all", 50]

        with self.assertRaisesRegex(ValueError, "must not mix 'all'"):
            RunConfig.model_validate(payload)

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
            "<b>Board size:</b> 50",
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
            "<b>Board size:</b> 50<br><b>Representation:</b>",
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
            ["Grammar 1"],
        )
        self.assertEqual(
            list(grammar_figure.data[0].customdata[0]),
            ["r00"],
        )
        self.assertEqual(list(grammar_figure.data[0].z[0]), [0.25])

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
            ["test-model"],
        )
        self.assertEqual(
            list(latency_figure.data[0].cells.values[1]),
            ["12.50 s"],
        )
        self.assertEqual(len(plot_latency_tables(aggregate)), 1)

    def test_case_set_loads_latest_run_and_run_id_loads_exact_run(self):
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
            run_source, older_aggregate = load_evaluation_results(
                None,
                run_id="older",
                project_root=project_root,
            )

        self.assertEqual(source.name, "newer")
        self.assertEqual(run_source.name, "older")
        self.assertEqual(aggregate["overall"]["passed"], 1)
        self.assertEqual(
            {group["model"] for group in aggregate["groups"]},
            {"gpt-5-mini"},
        )
        self.assertEqual(older_aggregate["overall"]["passed"], 1)
        self.assertEqual(older_aggregate["overall"]["failed"], 1)

    def test_evaluation_plots_include_only_models_in_selected_run(self):
        aggregate = _multi_group_plot_aggregate()

        pass_figure = plot_pass_rate_heatmaps(aggregate)[0]
        self.assertEqual(list(pass_figure.data[0].x), ["10", "50", "150"])
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
            list(
                dict.fromkeys(
                    (trace.x[0][0], trace.x[1][0]) for trace in failure_figure.data
                )
            ),
            [
                ("10", "gpt-5-mini"),
                ("50", "gpt-5"),
                ("50", "gpt-5-mini"),
                ("150", "gpt-5-mini"),
            ],
        )
        self.assertEqual(failure_figure.layout.xaxis.type, "multicategory")

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
            list(zip(*token_figure.data[0].x)),
            [
                ("10", "gpt-5-mini"),
                ("50", "gpt-5"),
                ("50", "gpt-5-mini"),
                ("150", "gpt-5-mini"),
            ],
        )

        runtime_figure = plot_latency_tables(aggregate)[0]
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[0]),
            ["gpt-5", "gpt-5-mini"],
        )
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[1]),
            ["-", "10.00 s"],
        )
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[2]),
            ["25.00 s", "20.00 s"],
        )
        self.assertEqual(
            list(runtime_figure.data[0].cells.values[3]),
            ["-", "30.00 s"],
        )

    def test_case_set_ignores_newer_in_progress_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            case_root = project_root / "outputs" / "evaluation" / "tiny"
            _write_completed_run(
                case_root / "runs" / "run-a",
                completed_at="2026-06-01T10:00:00+00:00",
                attempts=[_attempt(overall=True, grammar=0)],
                case_set="tiny",
            )
            _write_run_manifest(
                case_root / "runs" / "run-b",
                case_set="tiny",
                status="in_progress",
                completed_at=None,
            )

            source, aggregate = load_evaluation_results(
                "tiny",
                project_root=project_root,
            )

        self.assertEqual(source.name, "run-a")
        self.assertEqual(aggregate["overall"]["completed"], 1)

    def test_evaluation_result_selection_requires_exactly_one_selector(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            load_evaluation_results(None, None)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            load_evaluation_results("tiny", "run-a")

    def test_model_specific_board_sizes_expand_to_expected_jobs(self):
        model_names = ENV.get_registered_model_names()
        config = RunConfig.model_validate(
            {
                "config_name": "model_board_sizes",
                "case_set": "tiny",
                "models": {
                    model_names[0]: [10, 50],
                    model_names[1]: [150],
                },
            }
        )
        jobs = build_evaluation_jobs(
            config,
            {
                "cases": {
                    str(board_size): {
                        "board_size": board_size,
                        "path": f"outputs/evaluation/tiny/cases/{board_size}.json",
                    }
                    for board_size in (10, 50, 150)
                }
            },
        )

        self.assertEqual(len(jobs), 3)
        self.assertEqual(len({job.job_id for job in jobs}), 3)
        self.assertEqual(
            {(job.model_name, job.case_path.stem) for job in jobs},
            {
                (model_names[0], "10"),
                (model_names[0], "50"),
                (model_names[1], "150"),
            },
        )
        self.assertTrue(
            all(
                job.reasoning_effort == EVALUATION_REASONING_EFFORT
                for job in jobs
            )
        )

    def test_reasoning_effort_is_backend_specific(self):
        self.assertEqual(evaluation_reasoning_effort("openai_gpt-5"), "high")
        self.assertEqual(evaluation_reasoning_effort("or_gpt-5-5"), "xhigh")

    def test_summary_groups_models_board_sizes_failures_and_constraints(self):
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
        self.assertEqual(summary["by_board_size"]["50"]["total"], 3)
        self.assertEqual(summary["by_model"]["gpt-5-mini"]["total"], 2)
        self.assertEqual(len(summary["by_group"]), 2)

    def test_aggregate_reports_word_length_and_overlap_quality_metrics(self):
        attempts = [
            _attempt(
                overall=True,
                grammar=0,
                main_word_length=3,
                overlap_count=1,
                letter_score_total=4,
            ),
            _attempt(
                overall=True,
                grammar=0,
                main_word_length=5,
                overlap_count=3,
                letter_score_total=8,
            ),
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
        letter_score_total = aggregate["overall"]["quality"]["letter_score_total"]
        self.assertEqual(main_word_length["count"], 2)
        self.assertEqual(main_word_length["mean"], 4.0)
        self.assertEqual(overlap_count["count"], 2)
        self.assertEqual(overlap_count["mean"], 2.0)
        self.assertEqual(letter_score_total["count"], 2)
        self.assertEqual(letter_score_total["mean"], 6.0)

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
        grammar = load_grammar_config("evaluation_base_grammar")
        generation = load_generator_config("evaluation_base")

        self.assertEqual(grammar.config_name, "evaluation_base_grammar")
        self.assertEqual(generation.config_name, "evaluation_base")
        self.assertEqual(generation.grammar, "evaluation_base_grammar")
        self.assertTrue(str(resolve_grammar_path(generation)).endswith(
            "outputs/grammars/evaluation_base_grammar.json"
        ))
        self.assertTrue(str(resolve_output_path(generation)).endswith(
            "outputs/scenarios/evaluation_base.json"
        ))

    def test_truncated_normal_sampling_is_deterministic_and_bounded(self):
        axis = NumericRange(min=0, max=1)
        seed = derive_seed(42, 50, 0)

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

    def test_openrouter_transport_errors_use_evaluation_retry_policy(self):
        response = SimpleNamespace(
            status_code=429,
            text="rate limited",
            headers={"retry-after": "2.5"},
        )
        rate_limit = openrouter_errors.OpenRouterError(
            "rate limited",
            raw_response=response,
        )
        unavailable = openrouter_errors.OpenRouterError(
            "unavailable",
            raw_response=SimpleNamespace(
                status_code=503,
                text="unavailable",
                headers={},
            ),
        )

        self.assertTrue(is_retryable(rate_limit))
        self.assertTrue(is_retryable(openrouter_errors.NoResponseError("timeout")))
        self.assertTrue(is_retryable(unavailable))
        self.assertEqual(retry_delay(rate_limit, retry_index=0), 2.5)

    def test_openrouter_transport_error_persists_request_configuration(self):
        model_name = "or_deepseek-v4-pro"
        job = SimpleNamespace(
            job_id="job",
            case_path=Path("case.json"),
            model_name=model_name,
            reasoning_effort=EVALUATION_REASONING_EFFORT,
            language_representation="forbidden-snippets",
        )

        result = transport_error_result(
            job,
            RuntimeError("failed"),
            retry_count=0,
            retryable=False,
        )

        self.assertEqual(
            result["model_config"]["provider"]["only"],
            ["alibaba"],
        )
        self.assertEqual(
            result["model_config"]["request_max_tokens"],
            32384,
        )

    def test_openrouter_error_details_preserve_provider_response(self):
        error = openrouter_errors.OpenRouterError(
            "Provider returned error",
            raw_response=SimpleNamespace(
                status_code=400,
                text='{"error":{"metadata":{"raw":"invalid reasoning"}}}',
                headers={"x-request-id": "request-123"},
            ),
        )

        self.assertEqual(
            exception_details(error),
            {
                "http_status_code": 400,
                "error_body": (
                    '{"error":{"metadata":{"raw":"invalid reasoning"}}}'
                ),
                "request_id": "request-123",
            },
        )

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

        self.assertEqual(case["board_size"], 0)
        self.assertIn("grammar", case)
        self.assertIn("board", case)
        self.assertIn("rack", case)
        self.assertIn("grammar_sha256", case["provenance"])

    def test_clean_prepare_removes_existing_case_set_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            case_root = root / "tiny"
            stale_run = case_root / "runs" / "stale" / "attempt.json"
            stale_run.parent.mkdir(parents=True)
            stale_run.write_text("stale", encoding="utf-8")

            with patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root):
                manifest = prepare_case_set(tiny_case_set(), clean=True)

            self.assertFalse(stale_run.exists())
            self.assertEqual(manifest["status"], "complete")
            self.assertTrue((case_root / "prepare-manifest.json").exists())


class AsyncEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_per_model_semaphore_limits_same_model_calls(self):
        active = 0
        peak = 0

        async def fake_execute_job(*_args, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {}

        job = SimpleNamespace(model_name="same-model")
        global_semaphore = asyncio.Semaphore(3)
        model_semaphore = asyncio.Semaphore(1)
        with patch(
            "src.evaluation.job_execution.execute_job",
            side_effect=fake_execute_job,
        ):
            await asyncio.gather(
                *(
                    _execute_after_cooldown(
                        job,
                        retry_index=0,
                        semaphore=global_semaphore,
                        model_semaphore=model_semaphore,
                        cooldowns=ModelCooldowns(),
                        call_llm=SimpleNamespace(),
                    )
                    for _ in range(3)
                )
            )

        self.assertEqual(peak, 1)

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
                prepare_case_set(tiny_case_set(board_sizes=[0, 1, 2]))
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
        self.assertEqual(
            observed_reasoning_efforts,
            [EVALUATION_REASONING_EFFORT] * 3,
        )
        self.assertEqual(len(set(observed_prompts)), 3)
        self.assertEqual(
            progress_updates,
            [(0, 3), (1, 3), (2, 3), (3, 3)],
        )
        self.assertTrue(
            all(
                item["reasoning_effort"] == EVALUATION_REASONING_EFFORT
                for item in attempt_data
            )
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
        self.assertEqual(len(aggregate["groups"]), 3)
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
    letter_score_total: int | None = None,
) -> dict[str, object]:
    return {
        "status": "complete",
        "board_size": 50,
        "model": model,
        "language_representation": "forbidden-snippets",
        "sampling_round": 0,
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
            "letter_score_total": letter_score_total,
        },
    }


def _plot_aggregate() -> dict[str, object]:
    return {
        "groups": [
            {
                "board_size": 50,
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
                        "pass_rate": 0.25,
                    },
                ],
            }
        ]
    }


def _multi_group_plot_aggregate() -> dict[str, object]:
    groups = []
    for model, board_size, pass_rate, runtime in (
        ("gpt-5-mini", 10, 0.4, 10),
        ("gpt-5-mini", 50, 0.6, 20),
        ("gpt-5-mini", 150, 0.2, 30),
        ("gpt-5", 50, 0.8, 25),
    ):
        group = dict(_plot_aggregate()["groups"][0])
        group.update(
            {
                "model": model,
                "board_size": board_size,
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
