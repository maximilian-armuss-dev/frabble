from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...configuration import NamedYamlConfigSource

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
GRAMMAR_CONFIG_DIR = CONFIG_DIR / "grammars"


class GrammarConfigError(ValueError):
    pass


GRAMMAR_CONFIG_SOURCE = NamedYamlConfigSource(
    directory=GRAMMAR_CONFIG_DIR,
    kind="grammar",
    error_type=GrammarConfigError,
)


class AutoResampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool
    max_attempts: int = Field(gt=0)
    perron_min: float = Field(ge=0)
    perron_max: float = Field(gt=0)
    resample_length_min: int = Field(gt=0)
    resample_length_max: int = Field(gt=0)
    min_word_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "AutoResampleConfig":
        if self.perron_min > self.perron_max:
            raise ValueError("auto_resample.perron_min must be <= perron_max.")
        if self.resample_length_min > self.resample_length_max:
            raise ValueError(
                "auto_resample.resample_length_min must be <= resample_length_max."
            )
        return self


class SLSamplingConfig(BaseModel):
    """Sampling settings persisted inside a concrete grammar artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alphabet_case: str
    forbidden_fraction: float = Field(ge=0, le=1)
    auto_resample: AutoResampleConfig


class GrammarConfig(SLSamplingConfig):
    """Complete, standalone grammar sampling configuration."""

    config_name: str
    alphabet_size: int = Field(ge=1, le=26)
    k: int = Field(ge=1)
    min_word_length: int | None = Field(default=None, ge=1)
    seed: int
    output_path: str | None = None
    show_stats: bool = False

    @model_validator(mode="after")
    def validate_grammar(self) -> "GrammarConfig":
        if self.alphabet_case not in {"upper", "lower"}:
            raise ValueError("alphabet_case must be 'upper' or 'lower'.")
        return self

    @property
    def resolved_min_word_length(self) -> int:
        return self.min_word_length if self.min_word_length is not None else self.k


def resolve_grammar_config_path(config_name: str) -> Path:
    return GRAMMAR_CONFIG_SOURCE.path(config_name)


def default_grammar_output_path(grammar_name: str) -> Path:
    return PROJECT_ROOT / "outputs" / "grammars" / f"{grammar_name}.json"


def resolve_grammar_output_path(config: GrammarConfig) -> Path:
    if config.output_path is None:
        return default_grammar_output_path(config.config_name)
    output = Path(config.output_path)
    return output if output.is_absolute() else PROJECT_ROOT / output


def load_grammar_config(config_name: str) -> GrammarConfig:
    return GRAMMAR_CONFIG_SOURCE.load(config_name, GrammarConfig)
