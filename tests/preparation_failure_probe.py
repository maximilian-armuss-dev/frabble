"""Fault injection in real spawned processes, isolated from the test runner."""
from __future__ import annotations

from contextlib import contextmanager
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preparation_probe import reference_config
from src.evaluation.case_sampling import resolve_generation_config
from src.evaluation.prepare import prepare_case_set


def main():
    mode, directory, output = sys.argv[1:]
    root = Path(directory)
    config = reference_config().model_copy(update={"sampling_rounds": 1, "board_sizes": [1]})
    starts, updates, exits = [], {}, []
    triggered = False

    @contextmanager
    def progress(scenario_id, total):
        nonlocal triggered
        starts.append([scenario_id, total])
        updates[scenario_id] = 0
        if not triggered:
            triggered = True
            if mode == "crash":
                mp.active_children()[0].kill()
            if mode == "interrupt":
                os.kill(os.getpid(), signal.SIGINT)

        def update(amount):
            assert amount > 0
            updates[scenario_id] += amount

        try:
            yield update
        finally:
            exits.append(scenario_id)

    def resolve(*args, **kwargs):
        result = resolve_generation_config(*args, **kwargs)
        if mode == "error" and ".d2." in kwargs["scenario_id"]:
            return result.model_copy(update={"grammar_path": str(root / "missing.json")})
        return result

    error = None
    with patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", root):
        try:
            with patch("src.evaluation.case_preparation.resolve_generation_config", resolve):
                prepare_case_set(config, workers=2, generation_progress_factory=progress)
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
        manifest_path = root / "reference" / "prepare-manifest.json"
        before = json.loads(manifest_path.read_text())
        paths = list((root / "reference" / "scenarios").glob("*.json"))
        saved = {str(path): [path.read_bytes(), path.stat().st_mtime_ns] for path in paths}
        children = [child.pid for child in mp.active_children()]
        after = prepare_case_set(config, workers=1)
        reused = all(
            path.read_bytes() == value[0] and path.stat().st_mtime_ns == value[1]
            for name, value in saved.items() for path in [Path(name)]
            if path.stem in before["scenarios"]
        )
    Path(output).write_text(json.dumps({
        "error": error, "before": before, "after": after, "children": children,
        "reused": reused, "starts": starts, "updates": updates, "exits": exits,
    }))


if __name__ == "__main__":
    main()
