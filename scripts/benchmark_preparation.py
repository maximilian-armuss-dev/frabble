"""Offline preparation matrix. Every trial starts in a new temporary directory.

Run with the repository's Python environment; no LLM calls or production writes.
The frozen pre-cache enumerator is used only as a measurement reference.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


@contextmanager
def instrumentation():
    from src.benchmark import optimality
    from src.generator.engine import ScenarioGenerator
    from reference_enumeration import _enumerate_slots as uncached

    metrics = {"enumeration_seconds": 0.0, "optimization_seconds": 0.0,
               "generator_step_seconds": 0.0, "enumerations": 0, "steps": 0}
    enumerate_slots = uncached if os.environ["FRABBLE_BENCH_CACHE"] == "0" else optimality._enumerate_slots
    optimize = ScenarioGenerator._optimal_move
    step = ScenarioGenerator._generate_next_transition
    initial = ScenarioGenerator.generate_initial_transition

    def measured_enumeration(*args, **kwargs):
        start = time.perf_counter()
        try:
            return enumerate_slots(*args, **kwargs)
        finally:
            metrics["enumeration_seconds"] += time.perf_counter() - start
            metrics["enumerations"] += 1

    def measured_optimize(*args, **kwargs):
        start = time.perf_counter()
        try:
            return optimize(*args, **kwargs)
        finally:
            metrics["optimization_seconds"] += time.perf_counter() - start

    def measured_step(function, *args, **kwargs):
        start = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            metrics["generator_step_seconds"] += time.perf_counter() - start
            metrics["steps"] += 1

    try:
        with (
            patch.object(optimality, "_enumerate_slots", measured_enumeration),
            patch.object(ScenarioGenerator, "_optimal_move", measured_optimize),
            patch.object(ScenarioGenerator, "_generate_next_transition", lambda *a, **k: measured_step(step, *a, **k)),
            patch.object(ScenarioGenerator, "generate_initial_transition", lambda *a, **k: measured_step(initial, *a, **k)),
        ):
            yield
    finally:
        metrics["optimization_excluding_enumeration_seconds"] = (
            metrics["optimization_seconds"] - metrics["enumeration_seconds"]
        )
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        metrics["process_peak_rss_bytes"] = rss if sys.platform == "darwin" else rss * 1024
        directory = Path(os.environ["FRABBLE_BENCH_METRICS"])
        (directory / f"{os.getpid()}.json").write_text(json.dumps(metrics))


def measured_worker(connection):
    from src.evaluation.scenario_workers import _worker_main
    with instrumentation():
        _worker_main(connection)


def trial(spec_path: Path):
    from src.evaluation.config import CaseSetConfig
    from src.evaluation.prepare import prepare_case_set
    from src.evaluation import scenario_workers

    spec = json.loads(spec_path.read_text())
    root = spec_path.parent
    metrics = root / "metrics"
    metrics.mkdir()
    os.environ["FRABBLE_BENCH_METRICS"] = str(metrics)
    os.environ["FRABBLE_BENCH_CACHE"] = str(int(spec["cache"]))
    config = CaseSetConfig(
        config_name="benchmark", generation_config="evaluation_base",
        grammar_config="evaluation_base_grammar", root_seed=20261008,
        board_sizes=[spec["size"]], dimensions=[spec["dimensions"]],
        sampling_rounds=spec["rounds"],
    )
    error = None
    start = time.perf_counter()
    try:
        with (
            patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root / "artifacts"),
            patch.object(scenario_workers, "_worker_main", measured_worker),
            instrumentation(),
        ):
            manifest = prepare_case_set(config, workers=spec["workers"])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        path = root / "artifacts/benchmark/prepare-manifest.json"
        manifest = json.loads(path.read_text()) if path.exists() else {}
    duration = time.perf_counter() - start
    fingerprints = {}
    for scenario_id in manifest.get("scenarios", {}):
        path = root / "artifacts/benchmark/scenarios" / f"{scenario_id}.json"
        data = json.loads(path.read_text())
        for field in ("grammar_path", "output_path"):
            data["config"][field] = Path(data["config"][field]).name
        fingerprints[scenario_id] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    failures = manifest.get("failures", {})
    result = {
        **spec, "prepare_seconds": duration, "error": error,
        "failures": failures, "fingerprints": fingerprints,
        "certification_failures": sum("certify an optimal move" in value["error"] for value in failures.values()),
        "process_metrics": [json.loads(path.read_text()) for path in sorted(metrics.glob("*.json"))],
    }
    (root / "result.json").write_text(json.dumps(result, indent=2))


def run_trial(directory: Path, spec: dict) -> dict:
    import psutil  # Already supplied by the repository's ipykernel dependency.

    directory.mkdir()
    path = directory / "spec.json"
    path.write_text(json.dumps(spec))
    started = time.perf_counter()
    peak = 0
    rss_available = True
    with (directory / "process.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--trial", str(path)],
            stdout=log, stderr=log,
        )
        try:
            while process.poll() is None:
                if not rss_available:
                    time.sleep(0.1)
                    continue
                try:
                    parent = psutil.Process(process.pid)
                    rss = 0
                    for child in [parent, *parent.children(recursive=True)]:
                        try:
                            rss += child.memory_info().rss
                        except psutil.NoSuchProcess:
                            pass
                    peak = max(peak, rss)
                except psutil.NoSuchProcess:
                    pass
                except (psutil.AccessDenied, PermissionError):
                    rss_available = False
                time.sleep(0.1)
        except BaseException:
            # Let preparation reap its owned workers through its SIGINT path.
            process.send_signal(signal.SIGINT)
            process.wait(timeout=15)
            raise
    if process.returncode:
        raise RuntimeError(f"Trial exited {process.returncode}; see {directory / 'process.log'}")
    result = json.loads((directory / "result.json").read_text())
    result.update(
        wall_seconds=time.perf_counter() - started,
        sampled_tree_peak_rss_bytes=peak if rss_available else None,
    )
    (directory / "result.json").write_text(json.dumps(result, indent=2))
    return result


def reachable_bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        size += sum(reachable_bytes(item, seen) for pair in value.items() for item in pair)
    elif isinstance(value, (tuple, list, set, frozenset)):
        size += sum(reachable_bytes(item, seen) for item in value)
    return size


def enumeration_measurement(path: Path, repetitions: int):
    from src.benchmark import optimality
    from src.formal.grammar.serialization import load_grammar
    from src.generator.config import resolve_scenario_grammar_path
    from src.generator.scenario_io import load_scenario_run
    from reference_enumeration import _enumerate_slots as uncached

    run = load_scenario_run(path)
    language, _, _ = load_grammar(resolve_scenario_grammar_path(run.config, scenario_path=path))
    board = run.initial_board
    for transition in run.transitions[:-1]:
        board = board.place(transition.move)
    args = (board, language, run.transitions[-1].rack, language.letter_score_map())
    samples = {"uncached": [], "cached": []}
    expected = None
    for _ in range(repetitions):
        for name, function in (("uncached", uncached), ("cached", optimality._enumerate_slots)):
            start = time.perf_counter()
            slots = function(*args)
            samples[name].append(time.perf_counter() - start)
            if expected is None:
                expected = slots
            elif slots != expected:
                raise AssertionError(f"Slot difference: {path}")
    contexts = []
    original = optimality._SlotValidationContext

    def retain(*args):
        context = original(*args)
        contexts.append(context)
        return context

    with patch.object(optimality, "_SlotValidationContext", side_effect=retain):
        optimality._enumerate_slots(*args)
    memory = sum(reachable_bytes([context.axes, context.crosses]) for context in contexts)
    entries = [{"axes": len(context.axes), "crosses": len(context.crosses)} for context in contexts]
    contexts.clear()
    gc.collect()
    return {"scenario": str(path), "slots": len(expected), "seconds": samples,
            "cache_reachable_bytes": memory, "cache_entries": entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="5D 250/500 words plus small 10D; otherwise short smoke matrix")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--output-parent", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--enumeration-scenario", type=Path, action="append", default=[])
    parser.add_argument("--enumeration-only", action="store_true")
    parser.add_argument("--trial", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.trial:
        trial(args.trial)
        return
    if args.repetitions < 1 or args.rounds < 1:
        parser.error("repetitions and rounds must be positive")
    import ortools
    import psutil

    directory = Path(tempfile.mkdtemp(prefix="frabble-benchmark-", dir=args.output_parent))
    report = {
        "machine": {"platform": platform.platform(), "python": sys.version,
                    "ortools": ortools.__version__, "cpus": os.cpu_count(),
                    "ram_bytes": psutil.virtual_memory().total,
                    "hash_seed": os.environ.get("PYTHONHASHSEED", "random")},
        "scope": "full" if args.full else "short", "trials": [], "enumeration": [],
    }

    def save():
        (directory / "report.json").write_text(json.dumps(report, indent=2))

    print(directory, flush=True)
    save()
    for path in args.enumeration_scenario:
        report["enumeration"].append(enumeration_measurement(path.resolve(), args.repetitions))
        save()
        print(f"Enumeration complete: {path.name}", flush=True)
    reference = {}
    matrix = [(5, 250), (5, 500), (10, 5)] if args.full else [(5, 5), (10, 3)]
    if args.enumeration_only:
        matrix = []
    for dimensions, size in matrix:
        for repetition in range(args.repetitions):
            for cache, workers in ((False, 1), (True, 1), (True, 2), (True, 4)):
                spec = dict(dimensions=dimensions, size=size, rounds=args.rounds,
                            cache=cache, workers=workers, repetition=repetition)
                result = run_trial(directory / f"trial-{len(report['trials']):03d}", spec)
                for scenario_id, fingerprint in result["fingerprints"].items():
                    if scenario_id in reference and reference[scenario_id] != fingerprint:
                        raise AssertionError(f"Scenario difference: {scenario_id}")
                    reference[scenario_id] = fingerprint
                report["trials"].append(result)
                save()
                print(f"{spec}: {result['wall_seconds']:.2f}s; error={result['error']}", flush=True)
    groups = {}
    for row in report["trials"]:
        key = f"d{row['dimensions']}-b{row['size']}-cache{int(row['cache'])}-w{row['workers']}"
        groups.setdefault(key, []).append(row)
    report["summary"] = {
        key: {"wall_median_seconds": statistics.median(row["wall_seconds"] for row in rows),
              "wall_range_seconds": [min(row["wall_seconds"] for row in rows), max(row["wall_seconds"] for row in rows)],
              "max_sampled_tree_rss_bytes": max((row["sampled_tree_peak_rss_bytes"] for row in rows if row["sampled_tree_peak_rss_bytes"] is not None), default=None),
              "failed_trials": sum(row["error"] is not None for row in rows),
              "certification_failures": sum(row["certification_failures"] for row in rows)}
        for key, rows in groups.items()
    }
    save()
    print(f"Report: {directory / 'report.json'}", flush=True)


if __name__ == "__main__":
    main()
