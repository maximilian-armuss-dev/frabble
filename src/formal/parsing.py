from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..domain.models import Move


class SubmittedMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: tuple[int, ...] = Field(
        description="Start vector for the first symbol in the submitted sequence."
    )
    axis: int = Field(ge=0, description="Board axis along which the sequence runs.")
    sequence: tuple[str, ...] = Field(min_length=1)

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
