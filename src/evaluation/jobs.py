from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..generator.config import PROJECT_ROOT
from ..llm.env import ENV
from ..llm.representers import LANGUAGE_REPRESENTERS
from .config import RunConfig


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
    available_tiers = {
        str(entry["tier"])
        for entry in prepare_manifest["cases"].values()
        if isinstance(entry, dict)
    }
    model_tiers = resolve_model_tiers(
        config.models,
        available_models=ENV.get_registered_model_names(),
        available_tiers=sorted(available_tiers),
    )
    representations = resolve_selection(
        config.language_representations,
        list(LANGUAGE_REPRESENTERS),
        "language representations",
    )

    jobs: list[EvaluationJob] = []
    for case_id, entry in sorted(prepare_manifest["cases"].items()):
        case_path = _project_path(str(entry["path"]))
        for model_name, tiers in model_tiers.items():
            if entry["tier"] not in tiers:
                continue
            for representation in representations:
                jobs.append(
                    EvaluationJob(
                        job_id="__".join(
                            (
                                safe_id(case_id),
                                safe_id(model_name),
                                safe_id(config.reasoning_effort),
                                safe_id(representation),
                            )
                        ),
                        case_path=case_path,
                        model_name=model_name,
                        language_representation=representation,
                        reasoning_effort=config.reasoning_effort,
                    )
                )
    return jobs


def resolve_model_tiers(
    configured: dict[str, list[str]],
    *,
    available_models: list[str],
    available_tiers: list[str],
) -> dict[str, list[str]]:
    unknown_models = sorted(set(configured) - set(available_models))
    if unknown_models:
        raise ValueError(
            f"Unknown models: {unknown_models}. Available: {available_models}"
        )
    mixed_all = sorted(
        model_name
        for model_name, tiers in configured.items()
        if "all" in tiers and tiers != ["all"]
    )
    if mixed_all:
        raise ValueError(
            f"Models using tier 'all' must not list other tiers: {mixed_all}"
        )
    unknown_tiers = sorted(
        {
            tier
            for tiers in configured.values()
            for tier in tiers
            if tier != "all" and tier not in available_tiers
        }
    )
    if unknown_tiers:
        raise ValueError(
            f"Unknown tiers: {unknown_tiers}. Available: {available_tiers}"
        )
    return {
        model_name: (
            list(available_tiers)
            if configured[model_name] == ["all"]
            else sorted(configured[model_name])
        )
        for model_name in sorted(configured)
    }


def resolve_selection(
    configured: list[str] | str,
    available: list[str],
    label: str,
) -> list[str]:
    if configured == "all":
        return list(available)
    unknown = sorted(set(configured) - set(available))
    if unknown:
        raise ValueError(f"Unknown {label}: {unknown}. Available: {available}")
    return list(configured)


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value)


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
