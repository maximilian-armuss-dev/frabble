"""Exact single-move score references for sparse boards.

Enumerate every geometrically possible slot, then optimize its letters with CP-SAT.
An interrupted search retains an admissible upper bound for unfinished slots.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..domain.board import Board
from ..domain.models import Coord, Move, SlotTemplate, Symbol
from ..formal.language import StrictlyLocalLanguage
from ..formal.validation import extends_existing_sequence_in_any_axis, validate_move
from .scoring import score_move, tile_multiplier

Automaton = tuple[int, list[int], list[tuple[int, int, int]], dict[Symbol, int]]


@dataclass(frozen=True)
class OptimalityResult:
    status: str  # optimal, bounded, or no_move
    move: Move | None
    score: int | None
    upper_bound: int | None
    slots_considered: int
    slots_solved: int


@dataclass(frozen=True)
class _Slot:
    start: Coord
    axis: int
    coords: tuple[Coord, ...]
    domains: tuple[frozenset[Symbol], ...]
    upper_bound: int


def optimize_move(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[Symbol, ...],
    *,
    time_limit_seconds: float | None = None,
    incumbent: Move | None = None,
) -> OptimalityResult:
    """Optimize one move over the full unbounded lattice.

    ``optimal`` certifies the best score. ``bounded`` reports a valid lower
    bound (if a move was found) and an admissible upper bound. Board history
    matters: the same occupied cells can have different legal moves when their
    segment axes differ. Slot enumeration always completes so its running time
    may exceed ``time_limit_seconds``; the deadline limits CP-SAT search.
    """
    if board.dimensions < 2:
        raise ValueError("Optimality requires at least two board dimensions.")
    if time_limit_seconds is not None and time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be positive.")
    if any(symbol not in language.alphabet for symbol in rack):
        raise ValueError("Rack contains symbols outside the language alphabet.")

    best_move: Move | None = None
    best_score: int | None = None
    scores = language.letter_score_map()
    if incumbent is not None:
        result = validate_move(board, language, rack, incumbent)
        if not result.ok:
            raise ValueError(f"Incumbent move is invalid: {result.message}")
        best_move = incumbent
        best_score = score_move(board, incumbent, scores)

    deadline = (
        None if time_limit_seconds is None else time.monotonic() + time_limit_seconds
    )
    slots = _enumerate_slots(board, language, rack, scores)
    unresolved_bounds: list[int] = []
    solved = 0
    automaton: Automaton | None = None
    for index, slot in enumerate(slots):
        if best_score is not None and slot.upper_bound <= best_score:
            break
        if deadline is not None and time.monotonic() >= deadline:
            unresolved_bounds.extend(other.upper_bound for other in slots[index:])
            break
        if automaton is None:
            automaton = language.ortools_automaton()
        move, score, bound, complete = _solve_slot(
            board, language, rack, scores, slot, automaton, deadline
        )
        if move is not None and (best_score is None or score > best_score):
            best_move, best_score = move, score
        if complete:
            solved += 1
        else:
            unresolved_bounds.append(bound)

    upper_bound = max((best_score or 0, *unresolved_bounds))
    if best_score is not None and upper_bound == best_score:
        return OptimalityResult(
            "optimal", best_move, best_score, best_score, len(slots), solved
        )
    if best_score is None and not unresolved_bounds:
        return OptimalityResult("no_move", None, None, None, len(slots), solved)
    return OptimalityResult(
        "bounded", best_move, best_score, upper_bound, len(slots), solved
    )


def _enumerate_slots(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[Symbol, ...],
    scores: dict[Symbol, int],
) -> list[_Slot]:
    if not board.has_tiles():
        return _empty_board_slots(board, language, rack, scores)
    rack_counts = Counter(rack)
    rack_scores = sorted((scores.get(symbol, 0) for symbol in rack), reverse=True)
    seen: set[tuple[Coord, int, int]] = set()
    slots: list[_Slot] = []
    for anchor, anchor_symbol in board.occupied_sorted():
        for axis in range(board.dimensions):
            if axis in board.axes_at(anchor):
                continue
            left_offsets = _side_offsets(board, anchor, axis, -1, len(rack))
            right_offsets = _side_offsets(board, anchor, axis, 1, len(rack))
            for left, left_new in left_offsets:
                for right, right_new in right_offsets:
                    length = left + right + 1
                    if (
                        length < language.min_word_length
                        or not 0 < left_new + right_new <= len(rack)
                    ):
                        continue
                    start = _advance(anchor, axis, -left)
                    key = (start, axis, length)
                    if key in seen:
                        continue
                    seen.add(key)
                    coords = board.coords_for_slot(start, axis, length)
                    template = SlotTemplate(
                        anchor, anchor_symbol, axis, length, left, start, coords
                    )
                    if not board.analyze_slot(template).valid_geometry:
                        continue
                    new_coords = [coord for coord in coords if board.get(coord) is None]
                    if not new_coords or len(new_coords) > len(rack):
                        continue
                    if extends_existing_sequence_in_any_axis(
                        board, coords, axis, language
                    ):
                        continue
                    domains: list[frozenset[Symbol]] = []
                    for coord in coords:
                        fixed = board.get(coord)
                        if fixed is not None:
                            domains.append(frozenset((fixed,)))
                            continue
                        allowed = {
                            symbol for symbol in rack_counts
                            if _cross_words_accept(board, language, coord, axis, symbol)
                        }
                        if not allowed:
                            break
                        domains.append(frozenset(allowed))
                    if len(domains) != length:
                        continue
                    base = sum(
                        scores.get(board.get(coord), 0)
                        for coord in coords
                        if board.get(coord) is not None
                    )
                    premiums = sorted(
                        (tile_multiplier(coord) for coord in new_coords),
                        reverse=True,
                    )
                    upper = base + sum(
                        value * multiplier
                        for value, multiplier in zip(rack_scores, premiums)
                    )
                    slots.append(_Slot(start, axis, coords, tuple(domains), upper))
    slots.sort(
        key=lambda slot: (-slot.upper_bound, slot.start, slot.axis, len(slot.coords))
    )
    return slots


def _empty_board_slots(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[Symbol, ...],
    scores: dict[Symbol, int],
) -> list[_Slot]:
    # The premium pattern depends only on coordinate sum modulo 10 and a
    # weighted coordinate sum modulo 4. Axis 0 controls the latter; axis 1
    # independently sets the former, so these 40 starts cover every translate.
    rack_scores = sorted((scores.get(symbol, 0) for symbol in rack), reverse=True)
    slots: list[_Slot] = []
    for phase in range(4):
        for total in range(10):
            start = (phase, (total - phase) % 10) + (0,) * (board.dimensions - 2)
            for axis in range(board.dimensions):
                for length in range(language.min_word_length, len(rack) + 1):
                    coords = board.coords_for_slot(start, axis, length)
                    premiums = sorted(
                        (tile_multiplier(coord) for coord in coords), reverse=True
                    )
                    upper = sum(
                        value * multiplier
                        for value, multiplier in zip(rack_scores, premiums)
                    )
                    slots.append(
                        _Slot(
                            start,
                            axis,
                            coords,
                            tuple(frozenset(rack) for _ in coords),
                            upper,
                        )
                    )
    slots.sort(
        key=lambda slot: (-slot.upper_bound, slot.start, slot.axis, len(slot.coords))
    )
    return slots


def _side_offsets(
    board: Board,
    anchor: Coord,
    axis: int,
    direction: int,
    rack_size: int,
) -> list[tuple[int, int]]:
    offsets = [(0, 0)]
    new_count = 0
    distance = 0
    while True:
        distance += 1
        coord = _advance(anchor, axis, direction * distance)
        if axis in board.axes_at(coord):
            break
        if board.get(coord) is None:
            new_count += 1
            if new_count > rack_size:
                break
        offsets.append((distance, new_count))
    return offsets


def _cross_words_accept(
    board: Board,
    language: StrictlyLocalLanguage,
    coord: Coord,
    move_axis: int,
    symbol: Symbol,
) -> bool:
    for axis in range(board.dimensions):
        if axis == move_axis:
            continue
        before: list[Symbol] = []
        cursor = _advance(coord, axis, -1)
        while (existing := board.get(cursor)) is not None:
            before.append(existing)
            cursor = _advance(cursor, axis, -1)
        after: list[Symbol] = []
        cursor = _advance(coord, axis, 1)
        while (existing := board.get(cursor)) is not None:
            after.append(existing)
            cursor = _advance(cursor, axis, 1)
        if (before or after) and not language.accepts((*reversed(before), symbol, *after)):
            return False
    return True


def _solve_slot(
    board: Board,
    language: StrictlyLocalLanguage,
    rack: tuple[Symbol, ...],
    scores: dict[Symbol, int],
    slot: _Slot,
    automaton: Automaton,
    deadline: float | None,
) -> tuple[Move | None, int, int, bool]:
    model = cp_model.CpModel()
    symbol_ids = {symbol: index for index, symbol in enumerate(language.alphabet)}
    id_symbols = {index: symbol for symbol, index in symbol_ids.items()}
    variables = [
        model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(sorted(symbol_ids[symbol] for symbol in domain)),
            f"letter_{index}",
        )
        for index, domain in enumerate(slot.domains)
    ]
    start_state, final_states, arcs, _ = automaton
    model.AddAutomaton(variables, start_state, final_states, arcs)
    new_indices = [
        index for index, coord in enumerate(slot.coords) if board.get(coord) is None
    ]
    objective_terms = []
    for symbol, available in Counter(rack).items():
        used = []
        for index in new_indices:
            if symbol not in slot.domains[index]:
                continue
            selected = model.NewBoolVar(f"use_{index}_{symbol}")
            model.Add(variables[index] == symbol_ids[symbol]).OnlyEnforceIf(selected)
            model.Add(variables[index] != symbol_ids[symbol]).OnlyEnforceIf(selected.Not())
            used.append(selected)
            objective_terms.append(
                scores.get(symbol, 0) * tile_multiplier(slot.coords[index]) * selected
            )
        model.Add(sum(used) <= available)
    objective = sum(objective_terms)
    model.Maximize(objective)

    best_move: Move | None = None
    best_score = 0
    while True:
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return best_move, best_score, slot.upper_bound, False
            solver.parameters.max_time_in_seconds = remaining
        status = solver.Solve(model)
        if status == cp_model.INFEASIBLE:
            return best_move, best_score, best_score, True
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return best_move, best_score, slot.upper_bound, False
        sequence = tuple(id_symbols[solver.Value(variable)] for variable in variables)
        move = Move(slot.start, slot.axis, sequence)
        if validate_move(board, language, rack, move).ok:
            score = score_move(board, move, scores)
            base = sum(
                scores.get(board.get(coord), 0)
                for coord in slot.coords
                if board.get(coord) is not None
            )
            bound = min(
                slot.upper_bound, math.ceil(solver.BestObjectiveBound()) + base
            )
            return move, score, bound, status == cp_model.OPTIMAL
        # The validator is the final authority for unusual board histories.
        model.AddForbiddenAssignments(variables, [[solver.Value(v) for v in variables]])


def _advance(coord: Coord, axis: int, offset: int) -> Coord:
    return tuple(value + (offset if dim == axis else 0) for dim, value in enumerate(coord))


def main() -> None:
    """Print a score reference for one prepared evaluation case."""
    from ..evaluation.models import EvaluationCase

    parser = argparse.ArgumentParser(description="Certify a single-move score reference.")
    parser.add_argument("case", help="Prepared evaluation case JSON")
    parser.add_argument(
        "--seconds",
        type=float,
        default=30.0,
        help="Search deadline in seconds; slot enumeration may overrun it",
    )
    parser.add_argument(
        "--no-reference",
        action="store_true",
        help="Do not seed the search with the saved reference move",
    )
    args = parser.parse_args()
    with open(args.case, encoding="utf-8") as handle:
        case = EvaluationCase.model_validate(json.load(handle))
    result = optimize_move(
        case.to_board(),
        case.to_language(),
        case.rack,
        time_limit_seconds=args.seconds,
        incumbent=None if args.no_reference else case.to_reference_move(),
    )
    print(
        json.dumps(
            {
                "case_id": case.case_id,
                "status": result.status,
                "score": result.score,
                "upper_bound": result.upper_bound,
                "move": result.move.to_json() if result.move is not None else None,
                "slots_considered": result.slots_considered,
                "slots_solved": result.slots_solved,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
