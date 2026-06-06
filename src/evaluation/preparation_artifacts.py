from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..generator.config import PROJECT_ROOT
from .artifacts import file_sha256, read_json, utc_now, write_json_atomic
from .config import CaseSetConfig
from .models import DecompositionRequest, DecompositionResult, EvaluationCase


@dataclass
class PreparationManifest:
    path: Path
    data: dict[str, Any]

    @classmethod
    def load_or_create(
        cls,
        path: Path,
        config: CaseSetConfig,
        config_hash: str,
    ) -> "PreparationManifest":
        if path.exists():
            data = read_json(path)
            if data.get("config_hash") != config_hash:
                raise ValueError(
                    "Existing prepare manifest belongs to a different case-set "
                    "config. Use a new case-set name or remove the generated output."
                )
            return cls(path=path, data=data)

        return cls(
            path=path,
            data={
                "schema_version": 1,
                "case_set": config.config_name,
                "config_hash": config_hash,
                "status": "in_progress",
                "created_at": utc_now(),
                "completed_at": None,
                "grammars": {},
                "scenarios": {},
                "cases": {},
                "failures": {},
                "schemas": {},
            },
        )

    def artifact_matches(
        self,
        section: str,
        artifact_id: str,
        config_hash: str,
        path: Path,
    ) -> bool:
        entry = self.data[section].get(artifact_id)
        return (
            isinstance(entry, dict)
            and entry.get("status") == "complete"
            and entry.get("config_hash") == config_hash
            and path.exists()
            and entry.get("sha256") == file_sha256(path)
        )

    def record_artifact(
        self,
        section: str,
        artifact_id: str,
        entry: dict[str, Any],
    ) -> None:
        self.data[section][artifact_id] = entry
        self.clear_failure(artifact_id, save=False)
        self.save()

    def record_failure(self, artifact_id: str, exc: Exception) -> None:
        self.data["status"] = "in_progress"
        self.data["failures"][artifact_id] = {
            "error_type": type(exc).__name__,
            "error": str(exc),
            "timestamp": utc_now(),
        }
        self.save()

    def clear_failure(self, artifact_id: str, *, save: bool = True) -> None:
        removed = self.data["failures"].pop(artifact_id, None)
        if removed is not None and save:
            self.save()

    def write_interface_schemas(self, root: Path) -> None:
        schemas = {
            "evaluation-case": EvaluationCase.model_json_schema(),
            "decomposition-request": DecompositionRequest.model_json_schema(),
            "decomposition-result": DecompositionResult.model_json_schema(),
        }
        for name, schema in schemas.items():
            path = root / "schemas" / f"{name}.schema.json"
            write_json_atomic(path, schema)
            self.data["schemas"][name] = {
                "path": project_relative(path),
                "sha256": file_sha256(path),
            }
        self.save()

    def mark_complete(self) -> None:
        self.data["status"] = "complete"
        self.data["completed_at"] = utc_now()
        self.save()

    def save(self) -> None:
        write_json_atomic(self.path, self.data)


def artifact_entry(
    *,
    config_hash: str,
    path: Path,
    **metadata: object,
) -> dict[str, Any]:
    return {
        "status": "complete",
        "config_hash": config_hash,
        "path": project_relative(path),
        "sha256": file_sha256(path),
        **metadata,
    }


def project_relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
