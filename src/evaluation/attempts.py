from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import content_sha256, read_json, write_json_atomic


def attempt_has_valid_response(attempt: dict[str, Any]) -> bool:
    # Older runs stored provider response errors as completed parse failures.
    return (
        attempt.get("status") == "complete"
        and attempt.get("provider_metadata", {}).get("finish_reason") != "error"
    )


def persist_attempt(
    run_dir: Path,
    job_id: str,
    attempt: dict[str, Any],
) -> None:
    path = run_dir / "attempts" / f"{job_id}.json"
    if path.exists():
        previous = read_json(path)
        if not attempt_has_valid_response(previous):
            # Archive before replacing, so manual retries retain diagnostics.
            # A content hash also makes archiving safe to repeat after a crash.
            write_json_atomic(
                run_dir / "attempt-history" / job_id / f"{content_sha256(previous)}.json",
                previous,
            )
    write_json_atomic(path, attempt)
