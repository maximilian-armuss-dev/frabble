from __future__ import annotations

from collections import Counter

from ..domain.board import Board
from ..domain.models import Coord, Move, ValidationResult
from .language import StrictlyLocalLanguage


def validate_move(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[str, ...],
    move: Move,
) -> ValidationResult:
    basic_result = _validate_basic_shape(board, language, move)
    if not basic_result.ok:
        return basic_result

    coords = board.coords_for_slot(move.start, move.axis, len(move.sequence))
    needed: Counter[str] = Counter()
    touched_existing = False
    placed_new_symbol = False

    for coord, symbol in zip(coords, move.sequence, strict=True):
        current = board.get(coord)
        if current is None:
            needed[symbol] += 1
            placed_new_symbol = True
            continue
        if current != symbol:
            return ValidationResult(
                False,
                "spatial_conflict",
                f"Board has {current} at {coord}, but move needs {symbol}.",
            )
        touched_existing = True
        if move.axis in board.axes_at(coord):
            return ValidationResult(
                False,
                "word_extension",
                "Move overlaps an existing word on the same axis.",
            )

    if not placed_new_symbol:
        return ValidationResult(False, "structural", "Move places no new symbol.")
    if board.has_tiles() and not touched_existing:
        return ValidationResult(
            False,
            "missing_overlap",
            "Move must overlap at least one existing symbol.",
        )
    if _touches_same_axis_neighbor(board, coords, move.axis):
        return ValidationResult(
            False,
            "word_extension",
            "Move extends an existing word along the same axis.",
        )

    next_board = board.place(move)
    sequence_result = _validate_created_sequences(next_board, coords, move.axis, language)
    if not sequence_result.ok:
        return sequence_result

    rack_counts = Counter(rack)
    missing = needed - rack_counts
    if missing:
        return ValidationResult(
            False,
            "rack",
            f"Rack does not contain the needed symbols: {dict(missing)}.",
        )
    return ValidationResult(True, None, "valid")


def _validate_basic_shape(
    board: Board,
    language: StrictlyLocalLanguage,
    move: Move,
) -> ValidationResult:
    if not move.sequence:
        return ValidationResult(False, "schema", "Sequence must not be empty.")
    if len(move.start) != board.dimensions:
        return ValidationResult(
            False,
            "schema",
            f"Start vector must have {board.dimensions} coordinates.",
        )
    if move.axis < 0 or move.axis >= board.dimensions:
        return ValidationResult(False, "schema", "Axis is outside board dimensions.")
    if any(symbol not in language.alphabet for symbol in move.sequence):
        return ValidationResult(False, "sequence", "Sequence contains unknown symbols.")
    if not language.accepts(move.sequence):
        return ValidationResult(
            False,
            "sequence",
            "Sequence is not accepted by the formal language.",
        )
    return ValidationResult(True, None, "valid")


def _touches_same_axis_neighbor(
    board: Board,
    coords: tuple[Coord, ...],
    axis: int,
) -> bool:
    before = _advance(coords[0], axis, -1)
    after = _advance(coords[-1], axis, 1)
    return axis in board.axes_at(before) or axis in board.axes_at(after)


def _validate_created_sequences(
    board: Board,
    move_coords: tuple[Coord, ...],
    move_axis: int,
    language: StrictlyLocalLanguage,
) -> ValidationResult:
    checked: set[tuple[int, Coord]] = set()
    for coord in move_coords:
        for axis in range(board.dimensions):
            sequence_coords = _line_coords(board, coord, axis)
            if len(sequence_coords) == 1:
                continue
            key = (axis, sequence_coords[0])
            if key in checked:
                continue
            checked.add(key)
            sequence = tuple(board.get(line_coord) for line_coord in sequence_coords)
            if any(symbol is None for symbol in sequence):
                raise RuntimeError("Internal sequence extraction returned an empty cell.")
            if axis == move_axis and tuple(sequence_coords) == move_coords:
                continue
            typed_sequence = tuple(str(symbol) for symbol in sequence)
            if not language.accepts(typed_sequence):
                failure = "invalid_main_word" if axis == move_axis else "invalid_cross_word"
                return ValidationResult(
                    False,
                    failure,
                    f"Created sequence on axis {axis} is not accepted: {typed_sequence}.",
                )
    return ValidationResult(True, None, "valid")


def _line_coords(board: Board, coord: Coord, axis: int) -> tuple[Coord, ...]:
    start = coord
    while board.get(_advance(start, axis, -1)) is not None:
        start = _advance(start, axis, -1)
    coords: list[Coord] = []
    current = start
    while board.get(current) is not None:
        coords.append(current)
        current = _advance(current, axis, 1)
    return tuple(coords)


def _advance(coord: Coord, axis: int, offset: int) -> Coord:
    return tuple(value + (offset if dim == axis else 0) for dim, value in enumerate(coord))

