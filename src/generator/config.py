from __future__ import annotations

from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..configuration import NamedYamlConfigSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
GENERATION_CONFIG_DIR = CONFIG_DIR / "generation"


class ConfigError(ValueError):
    pass


GENERATION_CONFIG_SOURCE = NamedYamlConfigSource(
    directory=GENERATION_CONFIG_DIR,
    kind="generation",
    error_type=ConfigError,
)


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
    template_centroid_weight: float = Field(ge=0)
    template_local_density_penalty_weight: float = Field(ge=0)


class GeneratorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_name: str
    dimensions: int = Field(ge=2)
    seed: int
    grammar: str | None = None
    grammar_path: str | None = None
    initial_word_axis: int
    initial_word_length: int
    length_distribution: LengthDistribution
    fixed_final_transition_length: int | None = Field(default=None, gt=0)
    top_anchor_count: int = Field(gt=0)
    max_anchor_count: int | None = Field(default=None, gt=0)
    top_template_count: int = Field(gt=0)
    target_witness_count: int = Field(gt=0)
    scoring: ScoringConfig
    additional_rack_noise: int = Field(default=0, ge=0)
    output_path: str | None = None
    include_search_logs: bool

    @model_validator(mode="after")
    def validate_generator(self) -> "GeneratorConfig":
        if self.initial_word_axis < 0 or self.initial_word_axis >= self.dimensions:
            raise ValueError("initial_word_axis is outside configured dimensions.")
        if (self.grammar is None) == (self.grammar_path is None):
            raise ValueError("Exactly one of grammar or grammar_path must be configured.")
        if self.grammar is not None and (
            "/" in self.grammar
            or "\\" in self.grammar
            or self.grammar.endswith(".json")
        ):
            raise ValueError("grammar must be an ID without path or suffix.")
        return self


def resolve_config_path(config_name: str) -> Path:
    return GENERATION_CONFIG_SOURCE.path(config_name)


def resolve_grammar_path(config: GeneratorConfig) -> Path:
    if config.grammar is not None:
        return PROJECT_ROOT / "outputs" / "grammars" / f"{config.grammar}.json"
    if config.grammar_path is None:
        raise ConfigError("Generator config has no grammar reference.")
    grammar_path = Path(config.grammar_path)
    return grammar_path if grammar_path.is_absolute() else PROJECT_ROOT / grammar_path


def resolve_output_path(config: GeneratorConfig) -> Path:
    if config.output_path is None:
        return PROJECT_ROOT / "outputs" / "scenarios" / f"{config.config_name}.json"
    output = Path(config.output_path)
    return output if output.is_absolute() else PROJECT_ROOT / output


def resolve_scenario_grammar_path(
    scenario_config: Mapping[str, object],
    *,
    scenario_path: Path | None = None,
) -> Path:
    grammar = scenario_config.get("grammar")
    if grammar:
        return PROJECT_ROOT / "outputs" / "grammars" / f"{grammar}.json"
    raw_path = scenario_config.get("grammar_path")
    if not raw_path:
        raise ConfigError("Scenario config has no grammar or grammar_path reference.")
    direct = Path(str(raw_path))
    candidates = [
        direct,
        PROJECT_ROOT / direct,
    ]
    if scenario_path is not None:
        candidates.append(scenario_path.parent / direct)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise ConfigError(f"Grammar file not found: {raw_path}")


def load_generator_config(
    config_name: str,
    *,
    validate_grammar: bool = True,
) -> GeneratorConfig:
    from ..formal.grammar.serialization import load_grammar

    config = GENERATION_CONFIG_SOURCE.load(config_name, GeneratorConfig)
    if not validate_grammar:
        return config

    grammar_path = resolve_grammar_path(config)
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
    if (
        config.fixed_final_transition_length is not None
        and config.fixed_final_transition_length < grammar.min_word_length
    ):
        raise ConfigError(
            "fixed_final_transition_length "
            f"({config.fixed_final_transition_length}) must be >= "
            f"grammar min_word_length ({grammar.min_word_length})."
        )

    return config
