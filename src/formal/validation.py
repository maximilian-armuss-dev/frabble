from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..domain.board import Board
from ..domain.models import Coord, Move, Symbol, ValidationResult
from .language import StrictlyLocalLanguage


@dataclass(frozen=True)
class MoveValidationReport:
    result: ValidationResult
    sequence_valid: bool
    min_length_fulfilled: bool
    spatial_valid: bool
    overlap_valid: bool
    no_word_extension: bool
    cross_words_valid: bool
    rack_symbols_used: int
    rack_size: int

    @property
    def overall(self) -> bool:
        return self.result.ok

    @property
    def failure_type(self) -> str | None:
        return self.result.failure_type

    @property
    def message(self) -> str:
        return self.result.message

    @property
    def rack_usage_ratio(self) -> float:
        return self.rack_symbols_used / self.rack_size if self.rack_size else 0.0


@dataclass(frozen=True)
class _MoveScan:
    needed: Counter[Symbol]
    touched_existing: bool
    placed_new_symbol: bool
    spatial_result: ValidationResult
    same_axis_overlap: bool


def validate_move(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[str, ...],
    move: Move,
) -> ValidationResult:
    return validate_move_detailed(board, language, rack, move).result


def validate_move_detailed(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[str, ...],
    move: Move,
) -> MoveValidationReport:
    basic_result = _validate_basic_shape(board, language, move)
    if not basic_result.ok:
        return _report(
            basic_result,
            language,
            move,
            rack_size=len(rack),
            spatial_valid=False,
            overlap_valid=False,
            no_word_extension=False,
            cross_words_valid=False,
            rack_symbols_used=0,
        )

    coords = board.coords_for_slot(move.start, move.axis, len(move.sequence))
    scan = _scan_move(board, move, coords)
    overlap_valid = not board.has_tiles() or scan.touched_existing
    touches_neighbor = _touches_same_axis_neighbor(board, coords, move.axis)
    extends_sequence = extends_existing_sequence_in_any_axis(
        board, coords, move.axis, language
    )
    no_word_extension = (
        not scan.same_axis_overlap and not touches_neighbor and not extends_sequence
    )
    cross_words_result = _created_sequences_result(
        board,
        language,
        move,
        coords,
        scan.spatial_result.ok,
    )
    result = _first_failure(
        rack,
        scan,
        overlap_valid,
        touches_neighbor,
        extends_sequence,
        cross_words_result,
    )
    return _report(
        result,
        language,
        move,
        rack_size=len(rack),
        spatial_valid=scan.spatial_result.ok,
        overlap_valid=overlap_valid,
        no_word_extension=no_word_extension,
        cross_words_valid=cross_words_result.ok,
        rack_symbols_used=sum(scan.needed.values()),
    )


def _report(
    result: ValidationResult,
    language: StrictlyLocalLanguage,
    move: Move,
    *,
    rack_size: int,
    spatial_valid: bool,
    overlap_valid: bool,
    no_word_extension: bool,
    cross_words_valid: bool,
    rack_symbols_used: int,
) -> MoveValidationReport:
    return MoveValidationReport(
        result=result,
        sequence_valid=language.accepts(move.sequence),
        min_length_fulfilled=len(move.sequence) >= language.min_word_length,
        spatial_valid=spatial_valid,
        overlap_valid=overlap_valid,
        no_word_extension=no_word_extension,
        cross_words_valid=cross_words_valid,
        rack_symbols_used=rack_symbols_used,
        rack_size=rack_size,
    )


def _scan_move(
    board: Board,
    move: Move,
    coords: tuple[Coord, ...],
) -> _MoveScan:
    needed: Counter[Symbol] = Counter()
    touched_existing = False
    placed_new_symbol = False
    same_axis_overlap = False
    spatial_result = ValidationResult(True, None, "valid")
    for coord, symbol in zip(coords, move.sequence, strict=True):
        current = board.get(coord)
        if current is None:
            needed[symbol] += 1
            placed_new_symbol = True
            continue
        if move.axis in board.axes_at(coord):
            same_axis_overlap = True
        if current != symbol:
            if spatial_result.ok:
                spatial_result = ValidationResult(
                    False,
                    "spatial_conflict",
                    f"Board has {current} at {coord}, but move needs {symbol}.",
                )
            continue
        touched_existing = True
    return _MoveScan(
        needed=needed,
        touched_existing=touched_existing,
        placed_new_symbol=placed_new_symbol,
        spatial_result=spatial_result,
        same_axis_overlap=same_axis_overlap,
    )


def _created_sequences_result(
    board: Board,
    language: StrictlyLocalLanguage,
    move: Move,
    coords: tuple[Coord, ...],
    spatial_valid: bool,
) -> ValidationResult:
    if not spatial_valid:
        return ValidationResult(False, "spatial_conflict", "Move has spatial conflicts.")
    try:
        next_board = board.place(move)
    except ValueError as exc:
        return ValidationResult(False, "spatial_conflict", str(exc))
    return _validate_created_sequences(next_board, coords, move.axis, language)


def _first_failure(
    rack: tuple[str, ...],
    scan: _MoveScan,
    overlap_valid: bool,
    touches_neighbor: bool,
    extends_sequence: bool,
    cross_words_result: ValidationResult,
) -> ValidationResult:
    if not scan.spatial_result.ok:
        return scan.spatial_result
    if scan.same_axis_overlap:
        return ValidationResult(
            False,
            "word_extension",
            "Move overlaps an existing word on the same axis.",
        )
    if not scan.placed_new_symbol:
        return ValidationResult(False, "structural", "Move places no new symbol.")
    if not overlap_valid:
        return ValidationResult(
            False,
            "missing_overlap",
            "Move must overlap at least one existing symbol.",
        )
    if touches_neighbor:
        return ValidationResult(
            False,
            "word_extension",
            "Move extends an existing word along the same axis.",
        )
    if extends_sequence:
        return ValidationResult(
            False,
            "word_extension",
            "Move extends an already valid sequence on a touched axis.",
        )
    if not cross_words_result.ok:
        return cross_words_result

    missing = scan.needed - Counter(rack)
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


def extends_existing_axis_sequence(
    board: Board,
    coords: tuple[Coord, ...],
    axis: int,
    language: StrictlyLocalLanguage,
) -> bool:
    run: list[Symbol] = []
    line_coords: list[Coord] = list(coords)
    cursor = _advance(coords[0], axis, -1)
    while board.get(cursor) is not None:
        line_coords.insert(0, cursor)
        cursor = _advance(cursor, axis, -1)
    cursor = _advance(coords[-1], axis, 1)
    while board.get(cursor) is not None:
        line_coords.append(cursor)
        cursor = _advance(cursor, axis, 1)

    for coord in line_coords:
        symbol = board.get(coord)
        if symbol is None:
            if _is_existing_valid_sequence(run, language):
                return True
            run = []
            continue
        run.append(symbol)
    return _is_existing_valid_sequence(run, language)


def extends_existing_sequence_in_any_axis(
    board: Board,
    coords: tuple[Coord, ...],
    move_axis: int,
    language: StrictlyLocalLanguage,
) -> bool:
    if extends_existing_axis_sequence(board, coords, move_axis, language):
        return True
    return any(
        board.get(coord) is None
        and axis != move_axis
        and extends_existing_axis_sequence(board, (coord,), axis, language)
        for coord in coords
        for axis in range(board.dimensions)
    )


def _is_existing_valid_sequence(
    symbols: list[Symbol],
    language: StrictlyLocalLanguage,
) -> bool:
    return len(symbols) >= language.min_word_length and language.accepts(tuple(symbols))


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
