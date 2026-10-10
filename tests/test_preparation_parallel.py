from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from preparation_probe import reference_config
from support import generation_config, preparation_recipes
from src.evaluation.prepare import prepare_case_set
from src.evaluation.scenario_workers import (
    ScenarioTask, ScenarioWorkerError, resolve_worker_count, run_scenarios,
)
from src.generator.engine import ScenarioGenerator
from src.generator.readable_json import dumps_readable_json
from src.generator.scenario_codec import scenario_run_from_json, scenario_run_to_json
from src.generator.scenario_io import write_scenario_run

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


class ParallelPreparationTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(preparation_recipes())

    def probe(self, script, *args, hash_seed=1):
        result = subprocess.run(
            [sys.executable, str(HERE / script), *map(str, args)],
            cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": str(hash_seed)},
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_lost_worker_pipe_reports_tasks_and_reaps_processes_before_exitcode(self):
        # Linux may reset a pipe before the process sentinel reports its exit.
        # Inject each OS-level failure so this contract is also tested on macOS.
        for error_type in (EOFError, ConnectionResetError, BrokenPipeError):
            for operation in ("send", "recv"):
                with self.subTest(error=error_type.__name__, operation=operation):
                    context = Mock()
                    connections = [Mock(), Mock()]
                    children = [Mock(), Mock()]
                    processes = [Mock(exitcode=None), Mock(exitcode=None)]
                    for process in processes:
                        process.is_alive.side_effect = [True, False]
                    context.Pipe.side_effect = list(zip(connections, children))
                    context.Process.side_effect = processes
                    error = error_type("worker pipe lost")
                    getattr(connections[1], operation).side_effect = error
                    tasks = [ScenarioTask(name, {}) for name in ("first", "second", "pending")]
                    completed, failed = Mock(), Mock()

                    with (
                        patch("src.evaluation.scenario_workers.mp.get_context", return_value=context),
                        patch("src.evaluation.scenario_workers.wait", return_value=[connections[1]]),
                        self.assertRaises(ScenarioWorkerError) as caught,
                    ):
                        run_scenarios(tasks, workers=2, completed=completed, failed=failed)

                    self.assertIs(caught.exception.__cause__, error)
                    self.assertIn("affected scenarios: first, second", str(caught.exception))
                    self.assertEqual([call.args[0] for call in failed.call_args_list], tasks[:2])
                    completed.assert_not_called()
                    for process, connection, child in zip(processes, connections, children):
                        process.terminate.assert_called_once()
                        process.join.assert_called_once_with(timeout=2)
                        process.close.assert_called_once()
                        connection.close.assert_called_once()
                        child.close.assert_called_once()

    def test_baseline_serial_spawn_hash_seeds_and_byte_compatibility(self):
        baseline = json.loads((HERE / "fixtures/generation_reference.json").read_text())
        baseline.pop("metadata")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "report.json"
            self.probe("preparation_probe.py", root, report, "--workers", 1)
            self.assertEqual(json.loads(report.read_text()), baseline)
            originals = {
                path.name: path.read_bytes()
                for path in (root / "reference/scenarios").glob("*.json")
            }
            shutil.rmtree(root / "reference")
            self.probe("preparation_probe.py", root, report, "--workers", 2, "--cli", hash_seed=991)
            self.assertEqual(json.loads(report.read_text()), baseline)
            for path in (root / "reference/scenarios").glob("*.json"):
                self.assertEqual(path.read_bytes(), originals[path.name])

            # Missing snapshots are repaired without generating any scenarios.
            case = next((root / "reference/cases").glob("*.json"))
            case.unlink()
            with (
                patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root),
                patch("src.evaluation.case_preparation.run_scenarios") as pool,
                patch("src.evaluation.case_preparation.ScenarioGenerator") as generator,
            ):
                manifest = prepare_case_set(reference_config(), workers=4)
            pool.assert_not_called()
            generator.assert_not_called()
            self.assertTrue(case.exists())
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(len(manifest["grammars"]), 2)

            # A published file without manifest registration must be regenerated.
            manifest_path = root / "reference/prepare-manifest.json"
            orphan = next(iter(manifest["scenarios"]))
            manifest["scenarios"].pop(orphan)
            manifest_path.write_text(json.dumps(manifest))
            with (
                patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root),
                patch("src.evaluation.case_preparation.ScenarioGenerator", wraps=ScenarioGenerator) as generator,
            ):
                prepare_case_set(reference_config(), workers=1)
            self.assertEqual(generator.call_count, 1)

    def test_config_verification_preserves_existing_float_serialization(self):
        config = reference_config().model_copy(update={
            "sampling_rounds": 1, "board_sizes": [1], "dimensions": [2],
        })
        generation = generation_config()
        generation.scoring.anchor_centroid_weight = 0.1234567
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", Path(directory)),
            patch("src.evaluation.prepare.load_generator_config", return_value=generation),
        ):
            result = prepare_case_set(config, workers=1)
        self.assertEqual(result["status"], "complete")

    def test_real_worker_failure_crash_interrupt_and_resume(self):
        for mode in ("error", "crash", "interrupt"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "result.json"
                self.probe("preparation_failure_probe.py", mode, root, output)
                result = json.loads(output.read_text())
                self.assertIsNotNone(result["error"])
                self.assertEqual(result["children"], [])
                self.assertEqual(result["before"]["status"], "in_progress")
                self.assertTrue(result["before"]["failures"])
                self.assertEqual(result["after"]["status"], "complete")
                self.assertEqual(len(result["after"]["scenarios"]), 3)
                self.assertEqual(result["after"]["failures"], {})
                self.assertTrue(result["reused"])
                if mode == "error":
                    self.assertEqual(list(result["before"]["scenarios"]), ["reference.d5.b001.r00"])
                    self.assertNotIn("reference.d10.b001.r00", dict(result["starts"]))
                    self.assertEqual(result["updates"]["reference.d5.b001.r00"], 1)
                    self.assertEqual(sorted(result["exits"]), sorted(dict(result["starts"])))
                elif mode == "crash":
                    self.assertIn("affected scenarios:", result["error"])
                else:
                    self.assertIn("KeyboardInterrupt", result["error"])

    def test_worker_options_and_invalid_values_precede_clean(self):
        with patch("src.evaluation.scenario_workers.os.cpu_count", return_value=10):
            self.assertEqual(resolve_worker_count(None, 9), 4)
            self.assertEqual(resolve_worker_count(None, 2), 2)
        with patch("src.evaluation.scenario_workers.os.cpu_count", return_value=None):
            self.assertEqual(resolve_worker_count(None, 9), 1)
        self.assertEqual(resolve_worker_count(1, 9), 1)
        self.assertEqual(resolve_worker_count(8, 3), 3)
        self.assertEqual(resolve_worker_count(4, 0), 0)
        with patch("src.evaluation.prepare._clean_case_set_root") as clean:
            for invalid in (0, -1, 1.5, True):
                with self.assertRaisesRegex(ValueError, "workers"):
                    prepare_case_set(reference_config(), workers=invalid, clean=True)
            clean.assert_not_called()

    def test_atomic_serialization_preserves_bytes_and_previous_file_on_failure(self):
        baseline = json.loads((HERE / "fixtures/generation_reference.json").read_text())
        run = scenario_run_from_json(next(iter(baseline["scenarios"].values())))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.json"
            write_scenario_run(path, run)
            before = path.read_bytes()
            self.assertEqual(before, dumps_readable_json(scenario_run_to_json(run)).encode())
            with patch("src.generator.scenario_io.os.fsync", side_effect=OSError("disk failed")):
                with self.assertRaisesRegex(OSError, "disk failed"):
                    write_scenario_run(path, run)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
