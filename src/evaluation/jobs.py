from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..generator.config import PROJECT_ROOT
from ..llm.env import ENV
from .config import DEFAULT_LANGUAGE_REPRESENTATION, RunConfig

EVALUATION_REASONING_EFFORT = "high"
EVALUATION_OPENROUTER_REASONING_EFFORT = "xhigh"


@dataclass(frozen=True)
class EvaluationJob:
    job_id: str
    case_path: Path
    model_name: str
    language_representation: str
    reasoning_effort: str


def build_evaluation_jobs(
    config: RunConfig,
    prepare_manifest: dict[str, Any],
) -> list[EvaluationJob]:
    available_board_sizes = {
        int(entry["board_size"])
        for entry in prepare_manifest["cases"].values()
        if isinstance(entry, dict)
    }
    model_board_sizes = resolve_model_board_sizes(
        config.models,
        available_models=ENV.get_registered_model_names(),
        available_board_sizes=sorted(available_board_sizes),
    )

    jobs: list[EvaluationJob] = []
    for case_id, entry in sorted(prepare_manifest["cases"].items()):
        case_path = _project_path(str(entry["path"]))
        board_size = int(entry["board_size"])
        for model_name, board_sizes in model_board_sizes.items():
            if board_size not in board_sizes:
                continue
            reasoning_effort = evaluation_reasoning_effort(model_name)
            jobs.append(
                EvaluationJob(
                    job_id="__".join(
                        (
                            safe_id(case_id),
                            safe_id(model_name),
                            reasoning_effort,
                            safe_id(DEFAULT_LANGUAGE_REPRESENTATION),
                        )
                    ),
                    case_path=case_path,
                    model_name=model_name,
                    language_representation=DEFAULT_LANGUAGE_REPRESENTATION,
                    reasoning_effort=reasoning_effort,
                )
            )
    return jobs


def evaluation_reasoning_effort(model_name: str) -> str:
    model_config = ENV.get_model_config(model_name)
    if model_config.backend == "openrouter":
        return EVALUATION_OPENROUTER_REASONING_EFFORT
    return EVALUATION_REASONING_EFFORT


def resolve_model_board_sizes(
    configured: dict[str, list[int | str]],
    *,
    available_models: list[str],
    available_board_sizes: list[int],
) -> dict[str, list[int]]:
    unknown_models = sorted(set(configured) - set(available_models))
    if unknown_models:
        raise ValueError(
            f"Unknown models: {unknown_models}. Available: {available_models}"
    )
    mixed_all = sorted(
        model_name
        for model_name, sizes in configured.items()
        if "all" in sizes and sizes != ["all"]
    )
    if mixed_all:
        raise ValueError(
            f"Models using board size 'all' must not list other sizes: {mixed_all}"
        )
    unknown_board_sizes = sorted(
        {
            size
            for sizes in configured.values()
            for size in sizes
            if size != "all" and size not in available_board_sizes
        }
    )
    if unknown_board_sizes:
        raise ValueError(
            "Unknown board sizes: "
            f"{unknown_board_sizes}. Available: {available_board_sizes}"
        )
    return {
        model_name: (
            list(available_board_sizes)
            if configured[model_name] == ["all"]
            else sorted(int(size) for size in configured[model_name])
        )
        for model_name in sorted(configured)
    }


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
