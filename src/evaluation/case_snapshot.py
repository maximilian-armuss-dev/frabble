from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..formal.grammar.config import GrammarConfig
from ..generator.config import GeneratorConfig
from ..generator.reconstruction import board_before_transition
from ..generator.scenario_codec import board_to_json
from ..generator.scenario_io import load_scenario_run
from .artifacts import read_json
from .case_sampling import CaseCoordinates, SampledBoardParameters
from .models import EvaluationCase
from .preparation_artifacts import project_relative


@dataclass(frozen=True)
class PreparedGrammar:
    config: GrammarConfig
    path: Path
    actual_seed: int


@dataclass(frozen=True)
class PreparedScenario:
    config: GeneratorConfig
    path: Path


def build_evaluation_case(
    *,
    case_id: str,
    case_set: str,
    coordinates: CaseCoordinates,
    parameters: SampledBoardParameters,
    grammar: PreparedGrammar,
    grammar_sha256: str,
    scenario: PreparedScenario,
    scenario_sha256: str,
    case_set_config_hash: str,
    git_revision: str | None,
) -> EvaluationCase:
    scenario_run = load_scenario_run(scenario.path)
    board = board_before_transition(scenario_run, parameters.board_depth)
    transition = scenario_run.transitions[parameters.board_depth]
    return EvaluationCase(
        case_id=case_id,
        case_set=case_set,
        board_size=coordinates.board_size,

        sampling_round=coordinates.round_index,
        seeds={
            "grammar_requested": grammar.config.seed,
            "grammar_used": grammar.actual_seed,
            "board": parameters.seed,
        },
        parameters={
            "grammar": grammar.config.model_dump(mode="json"),
            "generation": scenario.config.model_dump(mode="json"),
            "board_depth": parameters.board_depth,
        },
        grammar=read_json(grammar.path),
        board=board_to_json(board),
        rack=transition.rack,
        ground_truth_move=transition.move.to_json(),
        provenance={
            "grammar_artifact": project_relative(grammar.path),
            "scenario_artifact": project_relative(scenario.path),
            "grammar_sha256": grammar_sha256,
            "scenario_sha256": scenario_sha256,
            "case_set_config_sha256": case_set_config_hash,
            "git_revision": git_revision,
        },
    )
