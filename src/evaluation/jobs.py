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


def build_evaluation_jobs(
    config: RunConfig,
    prepare_manifest: dict[str, Any],
) -> list[EvaluationJob]:
    available_tiers = {
        str(entry["tier"])
        for entry in prepare_manifest["cases"].values()
        if isinstance(entry, dict)
    }
    tiers = resolve_selection(config.tiers, sorted(available_tiers), "tiers")
    models = resolve_selection(
        config.models,
        ENV.get_registered_model_names(),
        "models",
    )
    representations = resolve_selection(
        config.language_representations,
        list(LANGUAGE_REPRESENTERS),
        "language representations",
    )

    jobs: list[EvaluationJob] = []
    for case_id, entry in sorted(prepare_manifest["cases"].items()):
        if entry["tier"] not in tiers:
            continue
        case_path = _project_path(str(entry["path"]))
        for model_name in models:
            for representation in representations:
                jobs.append(
                    EvaluationJob(
                        job_id="__".join(
                            (
                                safe_id(case_id),
                                safe_id(model_name),
                                safe_id(representation),
                            )
                        ),
                        case_path=case_path,
                        model_name=model_name,
                        language_representation=representation,
                    )
                )
    return jobs


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
