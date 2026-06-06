from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from ..domain.board import Board
from ..domain.models import Move, ScenarioTransition
from ..formal.language import StrictlyLocalLanguage
from ..generator.scenario_codec import board_from_json


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    case_id: str
    case_set: str
    tier: str
    sampling_round: int
    grammar_sample_index: int
    board_sample_index: int
    seeds: dict[str, int]
    parameters: dict[str, Any]
    grammar: dict[str, Any]
    board: dict[str, Any]
    rack: tuple[str, ...]
    ground_truth_move: dict[str, Any]
    provenance: dict[str, Any]

    def to_language(self) -> StrictlyLocalLanguage:
        return StrictlyLocalLanguage(
            language_id=str(self.grammar["name"]),
            alphabet=tuple(str(symbol) for symbol in self.grammar["alphabet"]),
            k=int(self.grammar["k"]),
            forbidden_snippets=tuple(
                tuple(str(symbol) for symbol in snippet)
                for snippet in self.grammar["forbidden"]
            ),
            min_word_length=int(self.grammar["min_word_length"]),
            seed=int(self.grammar["seed"]) if self.grammar.get("seed") is not None else None,
        )

    def to_board(self) -> Board:
        return board_from_json(self.board)

    def to_ground_truth_move(self) -> Move:
        return Move(
            start=tuple(int(value) for value in self.ground_truth_move["start"]),
            axis=int(self.ground_truth_move["axis"]),
            sequence=tuple(str(symbol) for symbol in self.ground_truth_move["sequence"]),
        )

    def to_transition(self) -> ScenarioTransition:
        return ScenarioTransition(
            rack=self.rack,
            move=self.to_ground_truth_move(),
            placed=(),
            search_log=None,
        )


class DecompositionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    request_id: str
    case: EvaluationCase
    failed_attempt: dict[str, Any]
    requested_at: datetime


class DecompositionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    request_id: str
    status: str
    details: dict[str, Any]


class DecompositionAdapter(Protocol):
    async def decompose(
        self,
        request: DecompositionRequest,
    ) -> DecompositionResult: ...
