from __future__ import annotations

from dataclasses import dataclass

from ..domain.board import Board
from ..formal.language import StrictlyLocalLanguage
from ..formal.parsing import SubmittedMove
from ..formal.validation import validate_move_detailed


@dataclass(frozen=True)
class GranularEvaluation:
    overall: bool
    parse_ok: bool
    sequence_valid: bool
    min_length_fulfilled: bool
    spatial_valid: bool
    overlap_valid: bool
    no_word_extension: bool
    cross_words_valid: bool
    rack_symbols_used: int
    rack_usage_ratio: float
    failure_type: str | None
    message: str

    def to_json(self) -> dict[str, object]:
        return {
            "overall": self.overall,
            "parse_ok": self.parse_ok,
            "sequence_valid": self.sequence_valid,
            "min_length_fulfilled": self.min_length_fulfilled,
            "spatial_valid": self.spatial_valid,
            "overlap_valid": self.overlap_valid,
            "no_word_extension": self.no_word_extension,
            "cross_words_valid": self.cross_words_valid,
            "rack_symbols_used": self.rack_symbols_used,
            "rack_usage_ratio": self.rack_usage_ratio,
            "failure_type": self.failure_type,
            "message": self.message,
        }


def evaluate_granular(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[str, ...],
    submitted: SubmittedMove | None,
    parse_error: str | None = None,
) -> GranularEvaluation:
    if submitted is None:
        return _parse_failed(parse_error)

    move = submitted.to_move()
    report = validate_move_detailed(board, language, rack, move)

    return GranularEvaluation(
        overall=report.overall,
        parse_ok=True,
        sequence_valid=report.sequence_valid,
        min_length_fulfilled=report.min_length_fulfilled,
        spatial_valid=report.spatial_valid,
        overlap_valid=report.overlap_valid,
        no_word_extension=report.no_word_extension,
        cross_words_valid=report.cross_words_valid,
        rack_symbols_used=report.rack_symbols_used,
        rack_usage_ratio=report.rack_usage_ratio,
        failure_type=report.failure_type,
        message=report.message,
    )


def _parse_failed(parse_error: str | None) -> GranularEvaluation:
    return GranularEvaluation(
        overall=False,
        parse_ok=False,
        sequence_valid=False,
        min_length_fulfilled=False,
        spatial_valid=False,
        overlap_valid=False,
        no_word_extension=False,
        cross_words_valid=False,
        rack_symbols_used=0,
        rack_usage_ratio=0.0,
        failure_type="parse",
        message=parse_error or "Failed to parse model response.",
    )
