from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .artifacts import read_json, utc_now, write_json_atomic
from .result_aggregation import build_aggregate

INDEX_FILENAME = "results-index.json"


def load_or_build_result_index(case_root: str | Path) -> dict[str, Any]:
    root = Path(case_root)
    source_runs = _completed_runs(root / "runs")
    if not source_runs:
        raise FileNotFoundError(
            f"No completed evaluation run found under {root / 'runs'}"
        )

    index_path = root / INDEX_FILENAME
    if index_path.exists():
        index = read_json(index_path)
        if index.get("source_runs") == source_runs:
            return index
    return build_result_index(root, source_runs=source_runs)


def build_result_index(
    case_root: str | Path,
    *,
    source_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(case_root)
    runs = source_runs if source_runs is not None else _completed_runs(root / "runs")
    if not runs:
        raise FileNotFoundError(
            f"No completed evaluation run found under {root / 'runs'}"
        )

    latest_attempts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    loaded_attempts = 0
    for run in runs:
        attempts_dir = root / "runs" / str(run["run_id"]) / "attempts"
        for attempt_path in sorted(attempts_dir.glob("*.json")):
            attempt = read_json(attempt_path)
            latest_attempts[_attempt_identity(attempt)] = attempt
            loaded_attempts += 1

    attempts = list(latest_attempts.values())
    index = {
        "schema_version": 1,
        "case_set": root.name,
        "updated_at": utc_now(),
        "source_runs": runs,
        "source_attempts": loaded_attempts,
        "indexed_attempts": len(attempts),
        "overwritten_attempts": loaded_attempts - len(attempts),
        "aggregate": build_aggregate(attempts),
    }
    write_json_atomic(root / INDEX_FILENAME, index)
    return index


def _completed_runs(runs_dir: Path) -> list[dict[str, Any]]:
    completed = []
    for manifest_path in runs_dir.glob("*/run-manifest.json"):
        manifest = read_json(manifest_path)
        if manifest.get("status") != "complete":
            continue
        completed.append(
            {
                "run_id": str(manifest.get("run_id") or manifest_path.parent.name),
                "completed_at": str(manifest.get("completed_at") or ""),
                "config_hash": str(manifest.get("config_hash") or ""),
            }
        )
    return sorted(
        completed,
        key=lambda run: (str(run["completed_at"]), str(run["run_id"])),
    )


def _attempt_identity(
    attempt: Mapping[str, Any],
) -> tuple[str, str, str, str]:
    case_id = attempt.get("case_id")
    if not case_id:
        case_file = attempt.get("case_file")
        case_id = Path(str(case_file)).stem if case_file else attempt.get("job_id")
    model_config = dict(attempt.get("model_config", {}))
    reasoning_effort = (
        attempt.get("reasoning_effort")
        or model_config.get("reasoning_effort")
        or model_config.get("reasoning_depth")
        or "default"
    )
    return (
        str(case_id or "unknown-case"),
        str(attempt.get("model") or "unknown-model"),
        str(attempt.get("language_representation") or "unknown-representation"),
        str(reasoning_effort),
    )
