from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigError(ValueError):
    pass


class LanguageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language_id: str
    alphabet: tuple[str, ...]
    k: int
    forbidden_snippets: tuple[tuple[str, ...], ...]
    min_word_length: int

    @field_validator("alphabet")
    @classmethod
    def validate_alphabet(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _validate_alphabet(value)
        return value

    @model_validator(mode="after")
    def validate_language(self) -> "LanguageConfig":
        _validate_v1_language_shape(self.k, self.min_word_length)
        alphabet = set(self.alphabet)
        for snippet in self.forbidden_snippets:
            if not snippet:
                raise ValueError("forbidden snippets must not be empty.")
            if len(snippet) > self.k:
                raise ValueError("forbidden snippets must not be wider than k.")
            if set(snippet) - alphabet:
                raise ValueError("forbidden snippets must use only alphabet symbols.")
        return self


class LengthDistribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(gt=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self) -> "LengthDistribution":
        if self.start > self.end:
            raise ValueError("length_distribution.start must be <= end.")
        return self


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_centroid_weight: float = Field(ge=0)
    anchor_free_span_weight: float = Field(ge=0)
    template_bbox_weight: float = Field(ge=0)
    template_centroid_weight: float = Field(ge=0)
    template_new_cell_bonus_weight: float = Field(ge=0)
    template_local_density_penalty_weight: float = Field(ge=0)


class GeneratorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_name: str
    dimensions: int
    seed: int
    language: LanguageConfig
    initial_word_axis: int
    initial_word_length: int
    length_distribution: LengthDistribution
    top_anchor_count: int = Field(gt=0)
    top_template_count: int = Field(gt=0)
    failure_budget: int = Field(gt=0)
    target_witness_count: int = Field(gt=0)
    scoring: ScoringConfig
    additional_rack_noise: int = Field(ge=0)
    output_path: str
    include_search_logs: bool

    @model_validator(mode="after")
    def validate_generator(self) -> "GeneratorConfig":
        if self.dimensions != 2:
            raise ValueError("V1 supports exactly dimensions = 2.")
        if self.initial_word_axis < 0 or self.initial_word_axis >= self.dimensions:
            raise ValueError("initial_word_axis is outside configured dimensions.")
        if self.initial_word_length < self.language.min_word_length:
            raise ValueError("initial_word_length must satisfy min_word_length.")
        if self.length_distribution.start < self.language.min_word_length:
            raise ValueError("length_distribution.start must satisfy min_word_length.")
        return self


def _validate_alphabet(value: tuple[str, ...]) -> None:
    if not value:
        raise ValueError("alphabet must not be empty.")
    if len(set(value)) != len(value):
        raise ValueError("alphabet must contain unique symbols.")
    if any(not symbol for symbol in value):
        raise ValueError("alphabet symbols must be non-empty strings.")


def _validate_v1_language_shape(k: int, min_word_length: int) -> None:
    if k != 2:
        raise ValueError("V1 supports exactly k = 2.")
    if min_word_length != 3:
        raise ValueError("V1 supports exactly min_word_length = 3.")


def resolve_config_path(config_name: str) -> Path:
    if not config_name:
        raise ConfigError("--config must not be empty.")
    if "/" in config_name or "\\" in config_name:
        raise ConfigError("--config must be a config name, not a path.")
    filename = config_name if config_name.endswith(".yaml") else f"{config_name}.yaml"
    return CONFIG_DIR / filename


def load_generator_config(config_name: str) -> GeneratorConfig:
    path = resolve_config_path(config_name)
    if not path.exists():
        raise ConfigError(f"Config file does not exist: {path}")
    raw = _read_yaml(path)
    try:
        config = GeneratorConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
    expected_name = path.stem
    if config.config_name != expected_name:
        raise ConfigError(
            f"config_name must match file name: expected {expected_name!r}, got {config.config_name!r}."
        )
    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping.")
    return data
