from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
GENERATION_CONFIG_DIR = CONFIG_DIR / "generation"


class ConfigError(ValueError):
    pass


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
    template_centroid_weight: float = Field(ge=0)
    template_new_cell_bonus_weight: float = Field(ge=0)
    template_local_density_penalty_weight: float = Field(ge=0)
    template_domain_slack_weight: float = Field(default=1.0, ge=0)


class GeneratorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_name: str
    dimensions: int = Field(ge=2)
    seed: int
    grammar_path: str
    initial_word_axis: int
    initial_word_length: int
    length_distribution: LengthDistribution
    top_anchor_count: int = Field(gt=0)
    max_anchor_count: int | None = Field(default=None, gt=0)
    top_template_count: int = Field(gt=0)
    target_witness_count: int = Field(gt=0)
    scoring: ScoringConfig
    additional_rack_noise: int = Field(ge=0)
    output_path: str
    include_search_logs: bool

    @model_validator(mode="after")
    def validate_generator(self) -> "GeneratorConfig":
        if self.initial_word_axis < 0 or self.initial_word_axis >= self.dimensions:
            raise ValueError("initial_word_axis is outside configured dimensions.")
        return self


def resolve_config_path(config_name: str) -> Path:
    if not config_name:
        raise ConfigError("--config must not be empty.")
    if "/" in config_name or "\\" in config_name:
        raise ConfigError("--config must be a config name, not a path.")
    filename = config_name if config_name.endswith(".yaml") else f"{config_name}.yaml"
    return GENERATION_CONFIG_DIR / filename


def load_generator_config(config_name: str) -> GeneratorConfig:
    from ..formal.grammar.serialization import load_grammar

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

    grammar_path = Path(config.grammar_path)
    if not grammar_path.is_absolute():
        grammar_path = PROJECT_ROOT / grammar_path
    if not grammar_path.exists():
        raise ConfigError(f"grammar_path does not exist: {grammar_path}")
    grammar, _cfg, _name = load_grammar(grammar_path)

    if config.initial_word_length < grammar.min_word_length:
        raise ConfigError(
            f"initial_word_length ({config.initial_word_length}) must be >= "
            f"grammar min_word_length ({grammar.min_word_length})."
        )
    if config.length_distribution.start < grammar.min_word_length:
        raise ConfigError(
            f"length_distribution.start ({config.length_distribution.start}) must be >= "
            f"grammar min_word_length ({grammar.min_word_length})."
        )

    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError("Config root must be a mapping.")
    return data
