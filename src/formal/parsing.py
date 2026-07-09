from __future__ import annotations

import json
import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.models import Move

_SYMBOL_SPLIT_PATTERN = re.compile(r"[\s,]+")


class SubmittedMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: tuple[int, ...] = Field(
        description="Start vector for the first symbol in the submitted sequence."
    )
    axis: int = Field(
        description="Board axis along which the sequence runs. Must be non-negative."
    )
    sequence: tuple[str, ...] = Field(min_length=1)

    @field_validator("axis")
    @classmethod
    def validate_axis(cls, value: int) -> int:
        if value < 0:
            raise ValueError("axis must be non-negative.")
        return value

    @field_validator("sequence", mode="before")
    @classmethod
    def normalize_sequence(cls, value: Iterable) -> tuple[str, ...]:
        if isinstance(value, str | bytes):
            raise ValueError("sequence must be a list of symbols, not a string.")
        return tuple(str(symbol).strip().upper() for symbol in value)

    def to_move(self) -> Move:
        return Move(
            start=self.start,
            axis=self.axis,
            sequence=self.sequence,
        )


def parse_submitted_move(raw_text: str) -> SubmittedMove:
    return SubmittedMove.model_validate_json(raw_text.strip())


def parse_move(raw_text: str) -> Move:
    return parse_submitted_move(raw_text).to_move()


def parse_submitted_move_lenient(raw_text: str) -> SubmittedMove:
    """Parse a response, tolerating common serialization mistakes in `sequence`.

    Some models emit the sequence as a single string ("Q J J" or "QJJ") or as a
    list holding the whole word in one element (["TAQJGL"]) instead of one array
    element per symbol. This recovers those into per-symbol lists so that a
    semantically correct move is not scored 0 for a formatting quirk. Relies on
    the benchmark invariant that every alphabet symbol is a single character.
    """
    data = json.loads(raw_text.strip())
    if isinstance(data, dict) and "sequence" in data:
        data = {**data, "sequence": _coerce_symbol_list(data["sequence"])}
    return SubmittedMove.model_validate(data)


def _coerce_symbol_list(value: object) -> object:
    if isinstance(value, str):
        return _split_symbols(value)
    if isinstance(value, (list, tuple)):
        symbols: list[str] = []
        for element in value:
            if isinstance(element, str):
                symbols.extend(_split_symbols(element))
            else:
                # Leave non-string elements for the schema validator to reject.
                return value
        return symbols
    return value


def _split_symbols(text: str) -> list[str]:
    tokens = [token for token in _SYMBOL_SPLIT_PATTERN.split(text.strip()) if token]
    symbols: list[str] = []
    for token in tokens:
        # A multi-character token is a whole word; split it into single symbols.
        symbols.extend(list(token) if len(token) > 1 else [token])
    return symbols
