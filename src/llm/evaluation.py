from __future__ import annotations

from dataclasses import dataclass

from ..domain.board import Board
from ..domain.models import Move
from ..formal.language import StrictlyLocalLanguage
from ..formal.parsing import SubmittedMove
from ..formal.validation import (
    _extends_existing_axis_sequence,
    _touches_same_axis_neighbor,
    _validate_created_sequences,
    validate_move,
)


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
    overall_result = validate_move(board, language, rack, move)

    try:
        coords = board.coords_for_slot(move.start, move.axis, len(move.sequence))
    except Exception:
        return GranularEvaluation(
            overall=overall_result.ok,
            parse_ok=True,
            sequence_valid=_check_sequence_valid(language, move),
            min_length_fulfilled=_check_min_length(language, move),
            spatial_valid=False,
            overlap_valid=False,
            no_word_extension=False,
            cross_words_valid=False,
            rack_symbols_used=0,
            rack_usage_ratio=0.0,
            failure_type=overall_result.failure_type,
            message=overall_result.message,
        )

    rack_symbols_used, touched_existing, spatial_valid = _scan_coords(board, move, coords)

    return GranularEvaluation(
        overall=overall_result.ok,
        parse_ok=True,
        sequence_valid=_check_sequence_valid(language, move),
        min_length_fulfilled=_check_min_length(language, move),
        spatial_valid=spatial_valid,
        overlap_valid=_check_overlap(board, touched_existing),
        no_word_extension=_check_no_word_extension(board, language, move, coords),
        cross_words_valid=_check_cross_words(board, language, move, coords, spatial_valid),
        rack_symbols_used=rack_symbols_used,
        rack_usage_ratio=rack_symbols_used / len(rack) if rack else 0.0,
        failure_type=overall_result.failure_type,
        message=overall_result.message,
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


def _check_sequence_valid(language: StrictlyLocalLanguage, move: Move) -> bool:
    return language.accepts(move.sequence)


def _check_min_length(language: StrictlyLocalLanguage, move: Move) -> bool:
    return len(move.sequence) >= language.min_word_length


def _scan_coords(
    board: Board,
    move: Move,
    coords: tuple[tuple[int, ...], ...],
) -> tuple[int, bool, bool]:
    """Return (rack_symbols_used, touched_existing, spatial_valid)."""
    rack_symbols_used = 0
    touched_existing = False
    spatial_valid = True
    for coord, symbol in zip(coords, move.sequence, strict=True):
        current = board.get(coord)
        if current is None:
            rack_symbols_used += 1
        elif current != symbol:
            spatial_valid = False
        else:
            touched_existing = True
    return rack_symbols_used, touched_existing, spatial_valid


def _check_overlap(board: Board, touched_existing: bool) -> bool:
    return not board.has_tiles() or touched_existing


def _check_no_word_extension(
    board: Board,
    language: StrictlyLocalLanguage,
    move: Move,
    coords: tuple[tuple[int, ...], ...],
) -> bool:
    try:
        same_axis_overlap = any(
            board.get(coord) is not None and move.axis in board.axes_at(coord)
            for coord in coords
        )
        touches_neighbor = _touches_same_axis_neighbor(board, coords, move.axis)
        extends_sequence = _extends_existing_axis_sequence(board, coords, move.axis, language)
        return not same_axis_overlap and not touches_neighbor and not extends_sequence
    except Exception:
        return False


def _check_cross_words(
    board: Board,
    language: StrictlyLocalLanguage,
    move: Move,
    coords: tuple[tuple[int, ...], ...],
    spatial_valid: bool,
) -> bool:
    if not spatial_valid:
        return False
    try:
        next_board = board.place(move)
        return _validate_created_sequences(next_board, coords, move.axis, language).ok
    except Exception:
        return False
