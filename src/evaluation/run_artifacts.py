from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import read_json, utc_now, write_json_atomic
from .config import RunConfig


def select_or_create_run(
    case_root: Path,
    config: RunConfig,
    config_hash: str,
) -> tuple[Path, dict[str, Any]]:
    resumable = _matching_runs(
        case_root / "runs",
        config_hash,
        statuses={"in_progress", "incomplete"},
        timestamp_field="created_at",
    )
    if resumable:
        _, path, manifest = max(resumable, key=lambda item: item[0])
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
    attempt = read_json(path)
    if attempt.get("status") == "complete":
        return True
    return attempt.get("status") == "transport_error" and not attempt.get(
        "retryable",
        False,
    )


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
    has_retryable_errors = any(
        attempt.get("status") == "transport_error"
        and bool(attempt.get("retryable"))
        for attempt in attempts
    )
    manifest["status"] = "incomplete" if has_retryable_errors else "complete"
    manifest["completed_at"] = None if has_retryable_errors else utc_now()
    manifest["completed_jobs"] = sum(
        attempt.get("status") == "complete" for attempt in attempts
    )
    manifest["error_jobs"] = sum(
        attempt.get("status") == "transport_error" for attempt in attempts
    )
    write_json_atomic(run_dir / "run-manifest.json", manifest)

    summary = summarize_attempts(attempts)
    write_json_atomic(run_dir / "summary.json", summary)
    return summary


def summarize_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [item for item in attempts if item.get("status") == "complete"]
    passed = [item for item in completed if _attempt_passed(item)]
    by_tier: dict[str, dict[str, int]] = {}
    for attempt in completed:
        tier = str(attempt.get("tier"))
        bucket = by_tier.setdefault(tier, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(_attempt_passed(attempt))

    return {
        "schema_version": 1,
        "total_attempts": len(attempts),
        "completed": len(completed),
        "passed": len(passed),
        "failed": len(completed) - len(passed),
        "transport_errors": len(attempts) - len(completed),
        "by_tier": by_tier,
    }


def _matching_runs(
    runs_dir: Path,
    config_hash: str,
    *,
    statuses: set[str],
    timestamp_field: str,
) -> list[tuple[str, Path, dict[str, Any]]]:
    if not runs_dir.exists():
        return []

    candidates: list[tuple[str, Path, dict[str, Any]]] = []
    for manifest_path in runs_dir.glob("*/run-manifest.json"):
        manifest = read_json(manifest_path)
        if (
            manifest.get("config_hash") == config_hash
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


def _attempt_passed(attempt: dict[str, Any]) -> bool:
    return bool(dict(attempt.get("evaluation", {})).get("overall"))
