from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

ConfigModel = TypeVar("ConfigModel", bound=BaseModel)
ConfigErrorType = type[ValueError]


@dataclass(frozen=True)
class NamedYamlConfigSource:
    directory: Path
    kind: str
    error_type: ConfigErrorType

    def path(self, config_name: str) -> Path:
        self._validate_name(config_name)
        return self.directory / f"{config_name}.yaml"

    def load(
        self,
        config_name: str,
        model_type: type[ConfigModel],
    ) -> ConfigModel:
        path = self.path(config_name)
        if not path.exists():
            raise self.error_type(
                f"{self.kind.capitalize()} config does not exist: {path}"
            )

        data = self._read_mapping(path)
        if "config_name" in data:
            raise self.error_type(
                f"config_name is derived from the {self.kind} config filename "
                "and must be omitted."
            )
        try:
            return model_type.model_validate(data | {"config_name": path.stem})
        except ValidationError as exc:
            raise self.error_type(str(exc)) from exc

    def _validate_name(self, config_name: str) -> None:
        if (
            not config_name
            or "/" in config_name
            or "\\" in config_name
            or config_name.endswith((".yaml", ".yml"))
        ):
            raise self.error_type(
                "--config must be a non-empty config name without path or suffix."
            )

    def _read_mapping(self, path: Path) -> dict[str, object]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise self.error_type(f"Config root must be a mapping: {path}")
        return data
