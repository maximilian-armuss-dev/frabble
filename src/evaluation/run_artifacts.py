from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import read_json, utc_now, write_json_atomic
from .attempts import attempt_has_valid_response
from .config import RunConfig
from .result_aggregation import (
    build_aggregate,
    compact_summary,
    write_results_csv,
)


def select_or_create_run(
    case_root: Path,
    config: RunConfig,
    config_hash: str,
    *,
    new_run: bool = False,
) -> tuple[Path, dict[str, Any]]:
    if new_run:
        return _create_run(case_root / "runs", config, config_hash)
    matching = _matching_runs(
        case_root / "runs",
        config_hash,
        statuses={"in_progress", "incomplete", "complete"},
        timestamp_field="created_at",
        resume_config=config,
    )
    if matching:
        _, path, manifest = max(matching, key=lambda item: item[0])
        # Execution policy may change between sessions without changing the jobs.
        manifest["config"] = config.model_dump(mode="json")
        manifest["config_hash"] = config_hash
        manifest["updated_at"] = utc_now()
        write_json_atomic(path / "run-manifest.json", manifest)
        return path, manifest
    return _create_run(case_root / "runs", config, config_hash)


def latest_completed_run(runs_dir: Path, config_hash: str) -> Path | None:
    candidates = _matching_runs(
        runs_dir,
        config_hash,
        statuses={"complete"},
        timestamp_field="completed_at",
    )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def attempt_is_final(path: Path) -> bool:
    if not path.exists():
        return False
    return attempt_has_valid_response(read_json(path))


def load_attempts(run_dir: Path) -> list[dict[str, Any]]:
    attempts_dir = run_dir / "attempts"
    if not attempts_dir.exists():
        return []
    return [read_json(path) for path in sorted(attempts_dir.glob("*.json"))]


def finalize_run(
    run_dir: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    attempts = load_attempts(run_dir)
    manifest["completed_jobs"] = sum(
        attempt_has_valid_response(attempt) for attempt in attempts
    )
    manifest["error_jobs"] = len(attempts) - manifest["completed_jobs"]
    is_complete = (
        manifest["error_jobs"] == 0
        and manifest["completed_jobs"] == manifest.get("total_jobs", len(attempts))
    )
    manifest["status"] = "complete" if is_complete else "incomplete"
    manifest["completed_at"] = (
        (manifest.get("completed_at") or utc_now()) if is_complete else None
    )
    manifest["updated_at"] = utc_now()
    write_json_atomic(run_dir / "run-manifest.json", manifest)

    aggregate = build_aggregate(attempts)
    summary = compact_summary(aggregate)
    write_json_atomic(run_dir / "summary.json", summary)
    write_json_atomic(run_dir / "aggregate.json", aggregate)
    write_results_csv(run_dir / "results.csv", aggregate)
    return summary


def summarize_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    return compact_summary(build_aggregate(attempts))


def _matching_runs(
    runs_dir: Path,
    config_hash: str,
    *,
    statuses: set[str],
    timestamp_field: str,
    resume_config: RunConfig | None = None,
) -> list[tuple[str, Path, dict[str, Any]]]:
    if not runs_dir.exists():
        return []

    candidates: list[tuple[str, Path, dict[str, Any]]] = []
    for manifest_path in runs_dir.glob("*/run-manifest.json"):
        manifest = read_json(manifest_path)
        if resume_config is None:
            config_matches = manifest.get("config_hash") == config_hash
        else:
            stored_config = manifest.get("config", {})
            config_matches = isinstance(stored_config, dict) and {
                key: value for key, value in stored_config.items() if key != "execution"
            } == resume_config.model_dump(mode="json", exclude={"execution"})
        if (
            config_matches
            and manifest.get("status") in statuses
        ):
            candidates.append(
                (
                    str(manifest.get(timestamp_field, "")),
                    manifest_path.parent,
                    manifest,
                )
            )
    return candidates


def _create_run(
    runs_dir: Path,
    config: RunConfig,
    config_hash: str,
) -> tuple[Path, dict[str, Any]]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{timestamp}_{config.config_name}_{config_hash[:8]}"
    run_dir = runs_dir / run_id
    now = utc_now()
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "run_config": config.config_name,
        "case_set": config.case_set,
        "config_hash": config_hash,
        "config": config.model_dump(mode="json"),
        "status": "in_progress",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "attempted_jobs": 0,
    }
    write_json_atomic(run_dir / "run-manifest.json", manifest)
    return run_dir, manifest
