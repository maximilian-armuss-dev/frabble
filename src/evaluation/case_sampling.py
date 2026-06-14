from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..formal.grammar.config import GrammarConfig
from ..generator.config import GeneratorConfig
from .config import CaseSetConfig, NumericAxis, TierConfig
from .sampling import derive_seed, sample_axis


@dataclass(frozen=True)
class SampledBoardParameters:
    seed: int
    dimensions: int
    board_depth: int


@dataclass(frozen=True)
class CaseCoordinates:
    tier_name: str
    round_index: int
    grammar_index: int
    board_index: int


def sample_board_parameters(
    config: CaseSetConfig,
    tier: TierConfig,
    coordinates: CaseCoordinates,
) -> SampledBoardParameters:
    board_seed = derive_seed(
        config.root_seed,
        coordinates.tier_name,
        coordinates.round_index,
        coordinates.grammar_index,
        coordinates.board_index,
        "board",
    )
    return SampledBoardParameters(
        seed=board_seed,
        dimensions=_sample_integer(tier.dimensions, board_seed, "dimensions"),
        board_depth=_sample_integer(tier.board_depth, board_seed, "board_depth"),
    )


def resolve_grammar_config(
    base: GrammarConfig,
    case_set: CaseSetConfig,
    tier_name: str,
    tier: TierConfig,
    round_index: int,
    grammar_index: int,
    grammar_id: str,
) -> GrammarConfig:
    seed = derive_seed(
        case_set.root_seed,
        tier_name,
        round_index,
        grammar_index,
        "grammar",
    )
    data = base.model_dump(mode="json")
    data.update(
        {
            "config_name": grammar_id,
            "seed": seed,
            "alphabet_size": _sample_integer(
                tier.alphabet_size,
                seed,
                "alphabet_size",
            ),
            "forbidden_fraction": float(
                sample_axis(
                    tier.forbidden_fraction,
                    seed=derive_seed(seed, "forbidden_fraction"),
                    integer=False,
                )
            ),
            "k": _sample_integer(tier.k, seed, "k"),
            "output_path": None,
            "show_stats": False,
        }
    )
    return GrammarConfig.model_validate(data)


def resolve_generation_config(
    base: GeneratorConfig,
    *,
    scenario_id: str,
    parameters: SampledBoardParameters,
    grammar_path: Path,
    output_path: Path,
) -> GeneratorConfig:
    data = base.model_dump(mode="json")
    data.update(
        {
            "config_name": scenario_id,
            "dimensions": parameters.dimensions,
            "seed": parameters.seed,
            "grammar": None,
            "grammar_path": str(grammar_path),
            "target_witness_count": parameters.board_depth + 1,
            "output_path": str(output_path),
        }
    )
    return GeneratorConfig.model_validate(data)


def grammar_artifact_id(
    case_set: str,
    tier: str,
    round_index: int,
    grammar_index: int,
) -> str:
    return f"{case_set}.{tier}.r{round_index:02d}.g{grammar_index:02d}"


def evaluation_case_id(
    case_set: str,
    coordinates: CaseCoordinates,
) -> str:
    return (
        f"{case_set}.{coordinates.tier_name}.r{coordinates.round_index:02d}."
        f"g{coordinates.grammar_index:02d}.b{coordinates.board_index:02d}"
    )


def _sample_integer(axis: NumericAxis, seed: int, axis_name: str) -> int:
    return int(
        sample_axis(
            axis,
            seed=derive_seed(seed, axis_name),
            integer=True,
        )
    )
