from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from ..configuration import NamedYamlConfigSource
from ..generator.config import PROJECT_ROOT

EVALUATION_CONFIG_DIR = PROJECT_ROOT / "config" / "evaluation"
CASE_SET_CONFIG_DIR = EVALUATION_CONFIG_DIR / "case_sets"
RUN_CONFIG_DIR = EVALUATION_CONFIG_DIR / "runs"
DEFAULT_LANGUAGE_REPRESENTATION = "forbidden-snippets"


class EvaluationConfigError(ValueError):
    pass


CASE_SET_CONFIG_SOURCE = NamedYamlConfigSource(
    directory=CASE_SET_CONFIG_DIR,
    kind="case-set",
    error_type=EvaluationConfigError,
)
RUN_CONFIG_SOURCE = NamedYamlConfigSource(
    directory=RUN_CONFIG_DIR,
    kind="run",
    error_type=EvaluationConfigError,
)


class NumericRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min: float
    max: float

    @field_validator("max")
    @classmethod
    def validate_max(cls, value: float, info) -> float:
        minimum = info.data.get("min")
        if minimum is not None and value < minimum:
            raise ValueError("range max must be >= min.")
        return value


NumericAxis = int | float | NumericRange


class CaseSetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_name: str
    generation_config: str
    grammar_config: str
    root_seed: int
    sampling_rounds: int = Field(default=1, gt=0)
    board_sizes: list[int]

    @field_validator("board_sizes")
    @classmethod
    def validate_board_sizes(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("At least one board size must be configured.")
        if any(isinstance(size, bool) or size < 0 for size in value):
            raise ValueError("Board sizes must be >= 0.")
        if len(value) != len(set(value)):
            raise ValueError("Board sizes must not contain duplicates.")
        return value


class ExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_concurrency: int = Field(default=10, gt=0)
    max_concurrency_per_model: int | None = Field(default=None, gt=0)
    max_retries: int = Field(default=5, ge=0)


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_name: str
    case_set: str
    models: dict[str, list[int | str]]
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @field_validator("models")
    @classmethod
    def validate_models(
        cls,
        value: dict[str, list[int | str]],
    ) -> dict[str, list[int | str]]:
        if not value:
            raise ValueError("models must not be empty.")
        normalized_models: dict[str, list[int | str]] = {}
        for model_name, board_sizes in value.items():
            if not model_name.strip():
                raise ValueError("Model names must not be empty.")
            if not board_sizes:
                raise ValueError(
                    f"Model {model_name!r} must select at least one board size."
                )
            normalized = [
                item.strip() if isinstance(item, str) else item
                for item in board_sizes
            ]
            if len(normalized) != len(set(normalized)):
                raise ValueError(
                    f"Model {model_name!r} contains duplicate board sizes."
                )
            if "all" in normalized and normalized != ["all"]:
                raise ValueError(
                    f"Model {model_name!r} must not mix 'all' with board sizes."
                )
            invalid = [
                item
                for item in normalized
                if not (
                    item == "all"
                    or (
                        isinstance(item, int)
                        and not isinstance(item, bool)
                        and item >= 0
                    )
                )
            ]
            if invalid:
                raise ValueError(
                    f"Model {model_name!r} contains invalid board sizes: {invalid}"
                )
            normalized_models[model_name.strip()] = normalized
        return normalized_models


def load_case_set_config(config_name: str) -> CaseSetConfig:
    return CASE_SET_CONFIG_SOURCE.load(config_name, CaseSetConfig)


def load_run_config(config_name: str) -> RunConfig:
    return RUN_CONFIG_SOURCE.load(config_name, RunConfig)
