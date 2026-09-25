from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.board import Board
from ..domain.models import Move, ScenarioTransition
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
    if parameters.board_size == 0:
        board = Board.empty(parameters.dimensions)
        if scenario_run.initial_rack is None or scenario_run.initial_optimal_score is None:
            raise ValueError("Scenario lacks a certified initial move.")
        segment = scenario_run.initial_board.segments[0]
        move = Move(segment.start, segment.axis, segment.sequence)
        transition = ScenarioTransition(
            rack=scenario_run.initial_rack,
            move=move,
            placed=tuple(zip(move.coords(), move.sequence, strict=True)),
            search_log=None,
            optimal_score=scenario_run.initial_optimal_score,
        )
        if board.place(move) != scenario_run.initial_board:
            raise ValueError("Stored initial move does not match initial_board.")
    else:
        board = board_before_transition(scenario_run, parameters.board_depth)
        transition = scenario_run.transitions[parameters.board_depth]

    if len(board.segments) != coordinates.board_size:
        raise ValueError(
            "Evaluation board size mismatch: "
            f"expected {coordinates.board_size} words, got {len(board.segments)}."
        )
    if transition.optimal_score is None:
        raise ValueError("Generated transition lacks a certified optimal score.")
    return EvaluationCase(
        case_id=case_id,
        case_set=case_set,
        board_size=coordinates.board_size,
        dimensions=parameters.dimensions,
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
        optimal_move=transition.move.to_json(),
        optimal_score=transition.optimal_score,
        provenance={
            "grammar_artifact": project_relative(grammar.path),
            "scenario_artifact": project_relative(scenario.path),
            "grammar_sha256": grammar_sha256,
            "scenario_sha256": scenario_sha256,
            "case_set_config_sha256": case_set_config_hash,
            "git_revision": git_revision,
        },
    )
