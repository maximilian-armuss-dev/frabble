from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from src.configuration import NamedYamlConfigSource
from src.evaluation.artifacts import read_json
from src.evaluation.config import CaseSetConfig, RunConfig
from src.evaluation.decomposition import decompose_run
from src.evaluation.job_execution import parse_duration, retry_delay
from src.evaluation.prepare import prepare_case_set
from src.evaluation.runner import evaluate_run
from src.evaluation.sampling import derive_seed, sample_axis
from src.formal.grammar.config import load_grammar_config
from src.generator.config import (
    load_generator_config,
    resolve_grammar_path,
    resolve_output_path,
)
from src.llm.client import LLMCallResult


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
    return RunConfig.model_validate(
        {
            "config_name": "tiny_run",
            "case_set": "tiny",
            "tiers": "all",
            "models": ["gpt-5-mini"],
            "language_representations": ["forbidden-snippets"],
            "execution": {
                "max_concurrency": concurrency,
                "max_retries": 0,
            },
        }
    )


class EvaluationConfigTests(unittest.TestCase):
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

        async def fake_call(_system: str, _user: str, _model: str) -> LLMCallResult:
            nonlocal active, peak
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
                    result = await evaluate_run(tiny_run(concurrency=2))
                decomposition = await decompose_run(tiny_run(concurrency=2))

            attempts = list(
                (Path(result["run_dir"]) / "attempts").glob("*.json")
            )

        self.assertEqual(len(attempts), 3)
        self.assertEqual(result["summary"]["completed"], 3)
        self.assertGreaterEqual(peak, 2)
        self.assertLessEqual(peak, 2)
        self.assertEqual(decomposition["processed"], 3)


if __name__ == "__main__":
    unittest.main()
