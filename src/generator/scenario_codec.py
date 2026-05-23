from __future__ import annotations

from typing import cast

from ..domain.board import Board
from ..domain.models import (
    Move,
    ScenarioRun,
    ScenarioTransition,
    SearchLog,
    Segment,
    SlotTemplate,
    SolverAttempt,
)


def scenario_run_to_json(scenario_run: ScenarioRun) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 1,
        "config_name": scenario_run.config_name,
        "config": scenario_run.config,
        "seed": scenario_run.seed,
        "language_id": scenario_run.language_id,
        "forbidden_snippets": [
            list(snippet) for snippet in scenario_run.forbidden_snippets
        ],
        "initial_board": board_to_json(scenario_run.initial_board),
        "transitions": [
            transition_to_json(
                transition,
                include_search_logs=bool(
                    scenario_run.config.get("include_search_logs", True)
                ),
            )
            for transition in scenario_run.transitions
        ],
    }
    return data


def scenario_run_from_json(data: dict[str, object]) -> ScenarioRun:
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported scenario schema_version.")
    return ScenarioRun(
        config_name=str(data["config_name"]),
        config=cast(dict[str, object], data["config"]),
        seed=int(data["seed"]),
        language_id=str(data["language_id"]),
        forbidden_snippets=tuple(
            tuple(str(symbol) for symbol in snippet)
            for snippet in cast(list[list[str]], data["forbidden_snippets"])
        ),
        initial_board=board_from_json(data["initial_board"]),
        transitions=tuple(
            transition_from_json(transition_data)
            for transition_data in cast(list[dict[str, object]], data["transitions"])
        ),
    )


def transition_to_json(
    transition: ScenarioTransition,
    *,
    include_search_logs: bool,
) -> dict[str, object]:
    data: dict[str, object] = {
        "rack": list(transition.rack),
        "move": move_to_compact_json(transition.move),
        "placed": cells_to_json(transition.placed),
    }
    if include_search_logs and transition.search_log is None:
        raise ValueError("Cannot include missing transition search_log.")
    if include_search_logs and transition.search_log is not None:
        data["search_log"] = transition.search_log.to_json()
    return data


def transition_from_json(data: dict[str, object]) -> ScenarioTransition:
    raw_search_log = data.get("search_log")
    return ScenarioTransition(
        rack=tuple(str(symbol) for symbol in cast(list[str], data["rack"])),
        move=move_from_compact_json(data["move"]),
        placed=cells_from_json(data["placed"]),
        search_log=None
        if raw_search_log is None
        else search_log_from_json(cast(dict[str, object], raw_search_log)),
    )


def board_to_json(board: Board) -> dict[str, object]:
    return {
        "dimensions": board.dimensions,
        "occupied": cells_to_json(board.occupied_sorted()),
        "segments": [
            {
                "start": list(segment.start),
                "axis": segment.axis,
                "sequence": list(segment.sequence),
            }
            for segment in board.segments
        ],
    }


def board_from_json(data: object) -> Board:
    if not isinstance(data, dict):
        raise ValueError("board must be an object.")
    dimensions = int(data["dimensions"])
    cells = {
        tuple(int(value) for value in coord): str(symbol)
        for coord, symbol in data["occupied"]
    }
    segments = tuple(
        Segment(
            start=coord_from_json(raw_segment["start"]),
            axis=int(raw_segment["axis"]),
            sequence=tuple(str(symbol) for symbol in raw_segment["sequence"]),
        )
        for raw_segment in data["segments"]
    )
    return Board(dimensions=dimensions, cells=cells, segments=segments)


def move_to_compact_json(move: Move) -> list[object]:
    return [list(move.start), move.axis, list(move.sequence)]


def move_from_compact_json(data: object) -> Move:
    if not isinstance(data, list) or len(data) != 3:
        raise ValueError("move must be [start, axis, sequence].")
    start, axis, sequence = data
    return Move(
        start=coord_from_json(start),
        axis=int(axis),
        sequence=tuple(str(symbol) for symbol in sequence),
    )


def search_log_from_json(data: dict[str, object]) -> SearchLog:
    return SearchLog(
        sampled_length=int(data["sampled_length"]),
        solver_attempts=tuple(
            solver_attempt_from_json(attempt_data)
            for attempt_data in cast(list[dict[str, object]], data["solver_attempts"])
        ),
    )


def solver_attempt_from_json(data: dict[str, object]) -> SolverAttempt:
    sequence = data["sequence"]
    return SolverAttempt(
        template=slot_template_from_json(cast(dict[str, object], data["template"])),
        status=str(data["status"]),
        sequence=None
        if sequence is None
        else tuple(str(symbol) for symbol in cast(list[str], sequence)),
    )


def slot_template_from_json(data: dict[str, object]) -> SlotTemplate:
    return SlotTemplate(
        anchor_coord=coord_from_json(data["anchor_coord"]),
        anchor_symbol=str(data["anchor_symbol"]),
        axis=int(data["axis"]),
        length=int(data["length"]),
        anchor_index=int(data["anchor_index"]),
        start=coord_from_json(data["start"]),
        covered_coords=tuple(
            coord_from_json(coord)
            for coord in cast(list[list[int]], data["covered_coords"])
        ),
    )


def cells_to_json(cells: tuple[tuple[tuple[int, ...], str], ...]) -> list[list[object]]:
    return [[list(coord), symbol] for coord, symbol in cells]


def cells_from_json(data: object) -> tuple[tuple[tuple[int, ...], str], ...]:
    return tuple(
        (coord_from_json(coord), str(symbol))
        for coord, symbol in cast(list[list[object]], data)
    )


def coord_from_json(data: object) -> tuple[int, ...]:
    return tuple(int(value) for value in cast(list[int], data))
