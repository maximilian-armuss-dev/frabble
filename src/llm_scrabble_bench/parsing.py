from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Move


class SubmittedMove(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: tuple[int, ...] = Field(
        description="Zero-based start vector for the first token."
    )
    axis: int = Field(ge=0, description="Board axis along which the token sequence runs.")
    # Ich hab einfach mal word length auf min = 2 gesetzt
    tokens: str = Field(min_length=2)

    @field_validator("tokens", mode="before")
    @classmethod
    def normalize_tokens(cls, value: object) -> str:
        if isinstance(value, list):
            value = "".join(str(token) for token in value)
        return str(value).strip().upper()

    def to_move(self) -> Move:
        return Move(
            start=self.start,
            axis=self.axis,
            tokens=self.tokens,
        )


def parse_submitted_move(raw_text: str) -> SubmittedMove:
    return SubmittedMove.model_validate_json(raw_text.strip())


def parse_move(raw_text: str) -> Move:
    return parse_submitted_move(raw_text).to_move()
