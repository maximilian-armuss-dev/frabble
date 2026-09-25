from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..domain.board import Board
from ..domain.models import Move, ScenarioTransition
from ..formal.language import StrictlyLocalLanguage
from ..generator.scenario_codec import board_from_json


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1, 2] = 2
    case_id: str
    case_set: str
    board_size: int
    dimensions: int | None = None
    sampling_round: int
    seeds: dict[str, int]
    parameters: dict[str, Any]
    grammar: dict[str, Any]
    board: dict[str, Any]
    rack: tuple[str, ...]
    optimal_move: dict[str, Any] | None = None
    optimal_score: int | None = None
    # Historical version-1 cases contain a valid move without a certificate.
    ground_truth_move: dict[str, Any] | None = Field(default=None, exclude=True)
    provenance: dict[str, Any]

    @model_validator(mode="after")
    def validate_reference(self) -> "EvaluationCase":
        if self.schema_version == 2 and (
            self.optimal_move is None or self.optimal_score is None
        ):
            raise ValueError("Version-2 cases require optimal_move and optimal_score.")
        if self.schema_version == 2 and self.ground_truth_move is not None:
            raise ValueError("Version-2 cases must not contain ground_truth_move.")
        if self.schema_version == 1 and self.ground_truth_move is None:
            raise ValueError("Version-1 cases require ground_truth_move.")
        if self.schema_version == 1 and (
            self.optimal_move is not None or self.optimal_score is not None
        ):
            raise ValueError("Version-1 cases cannot claim an optimum.")
        return self

    @property
    def reference_move(self) -> dict[str, Any]:
        move = self.optimal_move if self.schema_version == 2 else self.ground_truth_move
        if move is None:
            raise ValueError("Case has no reference move.")
        return move

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
            letter_scores=tuple(
                sorted(
                    (str(symbol), int(score))
                    for symbol, score in self.grammar.get("letter_scores", {}).items()
                )
            ),
            seed=int(self.grammar["seed"]) if self.grammar.get("seed") is not None else None,
        )

    def to_board(self) -> Board:
        return board_from_json(self.board)

    def to_reference_move(self) -> Move:
        reference = self.reference_move
        return Move(
            start=tuple(int(value) for value in reference["start"]),
            axis=int(reference["axis"]),
            sequence=tuple(str(symbol) for symbol in reference["sequence"]),
        )

    def to_transition(self) -> ScenarioTransition:
        return ScenarioTransition(
            rack=self.rack,
            move=self.to_reference_move(),
            placed=(),
            search_log=None,
            optimal_score=self.optimal_score,
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
