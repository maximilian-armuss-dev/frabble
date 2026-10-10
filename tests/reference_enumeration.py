"""Frozen pre-cache enumeration for regression tests and offline benchmarks.

Captured before implementation, Python 3.12.3 / OR-Tools 9.15.6755.
Keep independent of the new validation context.
"""
from collections import Counter
from src.domain.board import Board
from src.domain.models import Coord, SlotTemplate, Symbol
from src.formal.language import StrictlyLocalLanguage
from src.formal.validation import extends_existing_axis_sequence
from src.benchmark.scoring import tile_multiplier
from src.benchmark.optimality import _Slot, _empty_board_slots, _side_offsets, _advance, _cross_words_accept

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

