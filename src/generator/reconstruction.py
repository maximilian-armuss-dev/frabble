from __future__ import annotations

from typing import cast

from ..domain.board import Board
from ..domain.models import Move, ScenarioRun, ScenarioTransition, Segment
from .scenario_codec import board_from_json, cells_from_json, move_from_compact_json

ScenarioSource = ScenarioRun | dict[str, object]


def reconstruct_boards(source: ScenarioSource) -> tuple[Board, ...]:
    if isinstance(source, ScenarioRun):
        return _reconstruct_run_boards(source)
    return _reconstruct_json_boards(source)


def board_before_transition(source: ScenarioSource, transition_index: int) -> Board:
    if transition_index < 0:
        raise ValueError("transition_index must not be negative.")
    boards = reconstruct_boards(source)
    if transition_index >= len(boards) - 1:
        raise IndexError("transition_index is outside the transition range.")
    return boards[transition_index]


def _reconstruct_run_boards(scenario_run: ScenarioRun) -> tuple[Board, ...]:
    boards = [scenario_run.initial_board]
    board = scenario_run.initial_board
    for transition in scenario_run.transitions:
        board = _place_transition(board, transition)
        boards.append(board)
    return tuple(boards)


def _reconstruct_json_boards(data: dict[str, object]) -> tuple[Board, ...]:
    initial_board = board_from_json(data["initial_board"])
    boards = [initial_board]
    board = initial_board
    transitions = cast(list[dict[str, object]], data["transitions"])
    for transition_data in transitions:
        move = move_from_compact_json(transition_data["move"])
        board = _place_from_json_transition(board, move, transition_data["placed"])
        boards.append(board)
    return tuple(boards)


def _place_transition(board: Board, transition: ScenarioTransition) -> Board:
    return _place_incremental(
        board,
        transition.move,
        transition.placed,
    )


def _place_from_json_transition(
    board: Board,
    move: Move,
    placed_data: object,
) -> Board:
    if not isinstance(placed_data, list):
        raise ValueError("transition placed must be a list.")
    return _place_incremental(
        board,
        move,
        cells_from_json(placed_data),
    )


def _place_incremental(
    board: Board,
    move: Move,
    placed: tuple[tuple[tuple[int, ...], str], ...],
) -> Board:
    next_cells = dict(board.cells)
    expected = dict(zip(move.coords(), move.sequence, strict=True))
    placed_coords: set[tuple[int, ...]] = set()
    for coord, symbol in placed:
        if coord not in expected:
            raise ValueError("Transition placed cell is outside the move.")
        if expected[coord] != symbol:
            raise ValueError("Transition placed cell does not match move sequence.")
        if board.get(coord) is not None:
            raise ValueError("Transition placed cell is already occupied.")
        next_cells[coord] = symbol
        placed_coords.add(coord)

    missing = [
        coord
        for coord, _symbol in expected.items()
        if board.get(coord) is None and coord not in placed_coords
    ]
    if missing:
        raise ValueError("Transition omits newly occupied cells.")

    for coord, symbol in expected.items():
        if next_cells.get(coord) != symbol:
            raise ValueError("Transition move is inconsistent with the board.")

    segment = Segment(start=move.start, axis=move.axis, sequence=move.sequence)
    return Board(
        dimensions=board.dimensions,
        cells=next_cells,
        segments=board.segments + (segment,),
    )
