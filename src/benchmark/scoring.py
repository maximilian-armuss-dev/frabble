from __future__ import annotations

from typing import Mapping

from ..domain.board import Board
from ..domain.models import Coord, Move, Symbol


MULTIPLIER_SPACING = 10
MULTIPLIER_OFFSET = 2
MULTIPLIER_CYCLE = (4, 2, 3, 2)


def tile_multiplier(coord: Coord) -> int:
    """Periodic bonus planes with a repeating value pattern inside each plane."""
    if (sum(coord) - MULTIPLIER_OFFSET) % MULTIPLIER_SPACING:
        return 1
    phase = sum((axis - 1) * value for axis, value in enumerate(coord))
    return MULTIPLIER_CYCLE[phase % len(MULTIPLIER_CYCLE)]


def score_move(board: Board, move: Move, letter_scores: Mapping[Symbol, int]) -> int:
    """Score a valid move; premiums apply only to newly occupied cells."""
    return sum(
        letter_scores.get(symbol, 0)
        * (tile_multiplier(coord) if board.get(coord) is None else 1)
        for coord, symbol in zip(move.coords(), move.sequence, strict=True)
    )


class BoardScoring:
    @staticmethod
    def centroid(board: Board) -> tuple[float, ...]:
        if not board.cells:
            raise ValueError("Cannot compute centroid for an empty board.")
        return tuple(
            sum(coord[dim] for coord in board.cells) / len(board.cells)
            for dim in range(board.dimensions)
        )

    @staticmethod
    def distance_to_centroid(coord: Coord, centroid: tuple[float, ...]) -> float:
        return max(abs(value - centroid[dim]) for dim, value in enumerate(coord))

    @staticmethod
    def mean_distance_to_centroid(
        coords: tuple[Coord, ...],
        centroid: tuple[float, ...],
    ) -> float:
        if not coords:
            return 0.0
        return sum(BoardScoring.distance_to_centroid(coord, centroid) for coord in coords) / len(coords)

    @staticmethod
    def local_adjacent_density(board: Board, coords: tuple[Coord, ...]) -> int:
        density = 0
        coord_set = set(coords)
        for coord in coords:
            for axis in range(board.dimensions):
                for offset in (-1, 1):
                    neighbor = _advance(coord, axis, offset)
                    if neighbor in coord_set:
                        continue
                    if board.get(neighbor) is not None:
                        density += 1
        return density


def _advance(coord: Coord, axis: int, offset: int) -> Coord:
    return tuple(value + (offset if dim == axis else 0) for dim, value in enumerate(coord))
