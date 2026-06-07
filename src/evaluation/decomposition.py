from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..generator.config import PROJECT_ROOT
from .artifacts import content_sha256, read_json, write_json_atomic
from .config import RunConfig
from .models import (
    DecompositionAdapter,
    DecompositionRequest,
    DecompositionResult,
    EvaluationCase,
)
from .run_artifacts import latest_completed_run

EVALUATION_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluation"


class StubDecompositionAdapter:
    async def decompose(
        self,
        request: DecompositionRequest,
    ) -> DecompositionResult:
        return DecompositionResult(
            request_id=request.request_id,
            status="not_implemented",
            details={
                "message": "Decomposition adapter has not been implemented yet."
            },
        )


async def decompose_run(
    config: RunConfig,
    *,
    adapter: DecompositionAdapter | None = None,
) -> dict[str, Any]:
    source_run = _latest_matching_completed_run(config)
    output_dir = source_run / "decomposition"
    active_adapter = adapter or StubDecompositionAdapter()
    processed = 0

    for attempt_path in sorted((source_run / "attempts").glob("*.json")):
        attempt = read_json(attempt_path)
        if attempt.get("status") != "complete":
            continue
        if bool(dict(attempt.get("evaluation", {})).get("overall")):
            continue
        request_id = f"decompose__{attempt['job_id']}"
        request_path = output_dir / "requests" / f"{request_id}.json"
        result_path = output_dir / "results" / f"{request_id}.json"
        if result_path.exists():
            continue
        evaluation_case = EvaluationCase.model_validate(
            read_json(Path(str(attempt["case_file"])))
        )
        request = DecompositionRequest(
            request_id=request_id,
            case=evaluation_case,
            failed_attempt=attempt,
            requested_at=datetime.now(timezone.utc),
        )
        write_json_atomic(request_path, request.model_dump(mode="json"))
        result = await active_adapter.decompose(request)
        write_json_atomic(result_path, result.model_dump(mode="json"))
        processed += 1

    summary = {
        "schema_version": 1,
        "source_run": source_run.name,
        "run_config": config.config_name,
        "processed": processed,
        "status": "complete",
    }
    write_json_atomic(output_dir / "summary.json", summary)
    return summary


def _latest_matching_completed_run(config: RunConfig) -> Path:
    config_hash = content_sha256(config.model_dump(mode="json"))
    runs_dir = EVALUATION_OUTPUT_DIR / config.case_set / "runs"
    source_run = latest_completed_run(runs_dir, config_hash)
    if source_run is None:
        raise ValueError(
            f"No completed evaluation run matches config {config.config_name!r}."
        )
    return source_run
