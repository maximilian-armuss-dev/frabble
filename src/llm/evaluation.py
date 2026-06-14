from __future__ import annotations

from collections import Counter
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
    cross_words_valid: bool | None
    rack_valid: bool | None
    missing_rack_symbols: dict[str, int]
    rack_symbols_used: int
    rack_usage_ratio: float
    main_word_length: int | None
    overlap_count: int | None
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
            "rack_valid": self.rack_valid,
            "missing_rack_symbols": self.missing_rack_symbols,
            "rack_symbols_used": self.rack_symbols_used,
            "rack_usage_ratio": self.rack_usage_ratio,
            "main_word_length": self.main_word_length,
            "overlap_count": self.overlap_count,
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
    needed = Counter(
        symbol
        for coord, symbol in zip(move.coords(), move.sequence, strict=True)
        if board.get(coord) is None
    )
    missing = needed - Counter(rack)

    return GranularEvaluation(
        overall=report.overall,
        parse_ok=True,
        sequence_valid=report.sequence_valid,
        min_length_fulfilled=report.min_length_fulfilled,
        spatial_valid=report.spatial_valid,
        overlap_valid=report.overlap_valid,
        no_word_extension=report.no_word_extension,
        cross_words_valid=report.cross_words_valid if report.spatial_valid else None,
        rack_valid=not missing,
        missing_rack_symbols=dict(missing),
        rack_symbols_used=report.rack_symbols_used,
        rack_usage_ratio=report.rack_usage_ratio,
        main_word_length=len(move.sequence) if report.overall else None,
        overlap_count=(
            len(move.sequence) - report.rack_symbols_used if report.overall else None
        ),
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
        cross_words_valid=None,
        rack_valid=None,
        missing_rack_symbols={},
        rack_symbols_used=0,
        rack_usage_ratio=0.0,
        main_word_length=None,
        overlap_count=None,
        failure_type="parse",
        message=parse_error or "Failed to parse model response.",
    )
