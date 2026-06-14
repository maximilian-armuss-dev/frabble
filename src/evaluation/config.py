from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from ..configuration import NamedYamlConfigSource
from ..generator.config import PROJECT_ROOT
from ..llm.representers import LANGUAGE_REPRESENTERS

EVALUATION_CONFIG_DIR = PROJECT_ROOT / "config" / "evaluation"
CASE_SET_CONFIG_DIR = EVALUATION_CONFIG_DIR / "case_sets"
RUN_CONFIG_DIR = EVALUATION_CONFIG_DIR / "runs"
TIER_CONFIG_DIR = EVALUATION_CONFIG_DIR / "tiers"


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
TIER_CONFIG_SOURCE = NamedYamlConfigSource(
    directory=TIER_CONFIG_DIR,
    kind="tier",
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


class TierConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimensions: int | NumericRange
    board_depth: int | NumericRange
    forbidden_fraction: float | NumericRange

    @model_validator(mode="after")
    def validate_axes(self) -> "TierConfig":
        _validate_axis_bounds(self.dimensions, "dimensions", minimum=2)
        _validate_axis_bounds(self.board_depth, "board_depth", minimum=0)
        _validate_axis_bounds(
            self.forbidden_fraction,
            "forbidden_fraction",
            minimum=0,
            maximum=1,
        )
        return self


class TierSetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_name: str
    tiers: dict[str, TierConfig]

    @field_validator("tiers")
    @classmethod
    def validate_tiers(cls, value: dict[str, TierConfig]) -> dict[str, TierConfig]:
        if not value:
            raise ValueError("At least one tier must be configured.")
        for name in value:
            _validate_identifier(name, field="tier")
        return value


class CaseSetBaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    config_name: str
    generation_config: str
    grammar_config: str
    tier_config: str
    root_seed: int
    sampling_rounds: int = Field(default=1, gt=0)
    grammar_samples_per_tier: int = Field(default=3, gt=0)
    boards_per_grammar: int = Field(default=10, gt=0)


class CaseSetFileConfig(CaseSetBaseConfig):
    tiers: list[str]

    @field_validator("tiers")
    @classmethod
    def validate_tier_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one tier must be configured.")
        normalized = [name.strip() for name in value]
        if any(not name for name in normalized):
            raise ValueError("Tier names must not be empty.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Tier names must not contain duplicates.")
        for name in normalized:
            _validate_identifier(name, field="tier")
        return normalized


class CaseSetConfig(CaseSetBaseConfig):
    tiers: dict[str, TierConfig]

    @field_validator("tiers")
    @classmethod
    def validate_tiers(cls, value: dict[str, TierConfig]) -> dict[str, TierConfig]:
        if not value:
            raise ValueError("At least one tier must be configured.")
        for name in value:
            _validate_identifier(name, field="tier")
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
    models: dict[str, list[str]]
    language_representations: list[str] | str
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @field_validator("language_representations")
    @classmethod
    def validate_selection(cls, value: list[str] | str) -> list[str] | str:
        if isinstance(value, str):
            if value != "all":
                raise ValueError("Selection strings must be 'all'.")
            return value
        if not value:
            raise ValueError("Selection lists must not be empty.")
        if len(value) != len(set(value)):
            raise ValueError("Selection lists must not contain duplicates.")
        return value

    @field_validator("models")
    @classmethod
    def validate_models(
        cls,
        value: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        if not value:
            raise ValueError("models must not be empty.")
        normalized_models: dict[str, list[str]] = {}
        for model_name, tiers in value.items():
            if not model_name.strip():
                raise ValueError("Model names must not be empty.")
            if not tiers:
                raise ValueError(
                    f"Model {model_name!r} must select at least one tier."
                )
            normalized = [tier.strip() for tier in tiers]
            if any(not tier for tier in normalized):
                raise ValueError(
                    f"Model {model_name!r} contains an empty tier."
                )
            if len(normalized) != len(set(normalized)):
                raise ValueError(
                    f"Model {model_name!r} contains duplicate tiers."
                )
            normalized_models[model_name.strip()] = normalized
        return normalized_models

    @field_validator("language_representations")
    @classmethod
    def validate_language_representations(
        cls, value: list[str] | str
    ) -> list[str] | str:
        if value == "all":
            return value
        unknown = sorted(set(value) - set(LANGUAGE_REPRESENTERS))
        if unknown:
            raise ValueError(f"Unknown language representations: {unknown}")
        return value


def load_case_set_config(config_name: str) -> CaseSetConfig:
    file_config = CASE_SET_CONFIG_SOURCE.load(config_name, CaseSetFileConfig)
    tier_set = load_tier_set_config(file_config.tier_config)
    unknown = sorted(set(file_config.tiers) - set(tier_set.tiers))
    if unknown:
        raise EvaluationConfigError(
            f"Unknown tiers {unknown} in tier config "
            f"'{file_config.tier_config}'. Available: {sorted(tier_set.tiers)}"
        )
    data = file_config.model_dump(mode="json", exclude={"tiers"})
    data["tiers"] = {
        tier_name: tier_set.tiers[tier_name]
        for tier_name in file_config.tiers
    }
    return CaseSetConfig.model_validate(data)


def load_tier_set_config(config_name: str) -> TierSetConfig:
    return TIER_CONFIG_SOURCE.load(config_name, TierSetConfig)


def load_run_config(config_name: str) -> RunConfig:
    return RUN_CONFIG_SOURCE.load(config_name, RunConfig)


def _validate_identifier(value: str, *, field: str) -> None:
    if not value or "/" in value or "\\" in value or value.endswith((".yaml", ".yml")):
        raise EvaluationConfigError(
            f"{field} must be a non-empty identifier without path or suffix."
        )


def _validate_axis_bounds(
    value: NumericAxis,
    field: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> None:
    values = (value.min, value.max) if isinstance(value, NumericRange) else (value,)
    if any(item < minimum for item in values):
        raise ValueError(f"{field} must be >= {minimum}.")
    if maximum is not None and any(item > maximum for item in values):
        raise ValueError(f"{field} must be <= {maximum}.")
