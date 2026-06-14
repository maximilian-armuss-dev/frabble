from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..generator.config import PROJECT_ROOT
from ..llm.client import acall_llm_detailed
from .artifacts import content_sha256, read_json, utc_now, write_json_atomic
from .config import RunConfig
from .job_execution import AsyncLLMCaller, ModelCooldowns, execute_with_retries
from .jobs import EvaluationJob, build_evaluation_jobs
from .run_artifacts import attempt_is_final, finalize_run, select_or_create_run
from .sampling import derive_seed

EVALUATION_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluation"
ProgressCallback = Callable[[int, int], None]


async def evaluate_run(
    config: RunConfig,
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    case_root = EVALUATION_OUTPUT_DIR / config.case_set
    prepare_manifest = _load_completed_prepare_manifest(case_root, config.case_set)
    config_hash = content_sha256(config.model_dump(mode="json"))
    run_dir, manifest = select_or_create_run(case_root, config, config_hash)
    jobs = build_evaluation_jobs(config, prepare_manifest)
    pending_jobs = _pending_jobs(
        jobs,
        run_dir,
        config_hash,
    )
    progress = {"finished": len(jobs) - len(pending_jobs), "total": len(jobs)}
    if progress_callback is not None:
        progress_callback(progress["finished"], progress["total"])

    semaphore = asyncio.Semaphore(config.execution.max_concurrency)
    model_semaphores = {
        model_name: asyncio.Semaphore(
            config.execution.max_concurrency_per_model
        )
        for model_name in config.models
        if config.execution.max_concurrency_per_model is not None
    }
    cooldowns = ModelCooldowns()
    manifest_lock = asyncio.Lock()
    await asyncio.gather(
        *(
            _run_and_persist(
                job=job,
                semaphore=semaphore,
                model_semaphore=model_semaphores.get(job.model_name),
                cooldowns=cooldowns,
                max_retries=config.execution.max_retries,
                call_llm=acall_llm_detailed,
                run_dir=run_dir,
                manifest=manifest,
                manifest_lock=manifest_lock,
                progress=progress,
                progress_callback=progress_callback,
            )
            for job in pending_jobs
        )
    )

    summary = finalize_run(run_dir, manifest)
    return {"run_dir": str(run_dir), "manifest": manifest, "summary": summary}


async def _run_and_persist(
    *,
    job: EvaluationJob,
    semaphore: asyncio.Semaphore,
    model_semaphore: asyncio.Semaphore | None,
    cooldowns: ModelCooldowns,
    max_retries: int,
    call_llm: AsyncLLMCaller,
    run_dir: Path,
    manifest: dict[str, Any],
    manifest_lock: asyncio.Lock,
    progress: dict[str, int],
    progress_callback: ProgressCallback | None,
) -> None:
    result = await execute_with_retries(
        job,
        semaphore=semaphore,
        model_semaphore=model_semaphore,
        max_retries=max_retries,
        cooldowns=cooldowns,
        call_llm=call_llm,
    )
    write_json_atomic(run_dir / "attempts" / f"{job.job_id}.json", result)
    async with manifest_lock:
        manifest["updated_at"] = utc_now()
        manifest["attempted_jobs"] = int(manifest.get("attempted_jobs", 0)) + 1
        write_json_atomic(run_dir / "run-manifest.json", manifest)
        progress["finished"] += 1
        if progress_callback is not None:
            progress_callback(progress["finished"], progress["total"])


def _load_completed_prepare_manifest(
    case_root: Path,
    case_set: str,
) -> dict[str, Any]:
    manifest_path = case_root / "prepare-manifest.json"
    if not manifest_path.exists():
        raise ValueError(
            f"Case set is not prepared: {case_set}. "
            f"Run 'uv run prepare --config {case_set}' first."
        )
    manifest = read_json(manifest_path)
    if manifest.get("status") != "complete":
        raise ValueError(f"Case set is not complete: {case_set}")
    return manifest


def _pending_jobs(
    jobs: list[EvaluationJob],
    run_dir: Path,
    config_hash: str,
) -> list[EvaluationJob]:
    pending = [
        job
        for job in jobs
        if not attempt_is_final(run_dir / "attempts" / f"{job.job_id}.json")
    ]
    random.Random(derive_seed(0, config_hash, "job-order")).shuffle(pending)
    return pending
