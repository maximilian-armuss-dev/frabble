from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..formal.grammar.config import GrammarConfig
from ..generator.config import GeneratorConfig
from .config import CaseSetConfig
from .sampling import derive_seed


@dataclass(frozen=True)
class SampledBoardParameters:
    seed: int
    dimensions: int
    board_depth: int


@dataclass(frozen=True)
class CaseCoordinates:
    board_size: int
    round_index: int


def sample_board_parameters(
    config: CaseSetConfig,
    coordinates: CaseCoordinates,
    base_generation: GeneratorConfig,
) -> SampledBoardParameters:
    board_seed = derive_seed(
        config.root_seed,
        coordinates.board_size,
        coordinates.round_index,
        "board",
    )
    return SampledBoardParameters(
        seed=board_seed,
        dimensions=base_generation.dimensions,
        board_depth=coordinates.board_size,
    )


def resolve_grammar_config(
    base: GrammarConfig,
    case_set: CaseSetConfig,
    board_size: int,
    round_index: int,
    grammar_id: str,
) -> GrammarConfig:
    seed = derive_seed(
        case_set.root_seed,
        board_size,
        round_index,
        "grammar",
    )
    data = base.model_dump(mode="json")
    data.update(
        {
            "config_name": grammar_id,
            "seed": seed,
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
    board_size: int,
    round_index: int,
) -> str:
    return f"{case_set}.b{board_size:03d}.r{round_index:02d}"


def evaluation_case_id(
    case_set: str,
    coordinates: CaseCoordinates,
) -> str:
    return (
        f"{case_set}.b{coordinates.board_size:03d}."
        f"r{coordinates.round_index:02d}"
    )
