from __future__ import annotations

import math

from ..domain.board import Board
from ..domain.models import Coord


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
    def distance_to_centroid(board: Board, coord: Coord) -> float:
        centroid = BoardScoring.centroid(board)
        return math.sqrt(
            sum((value - centroid[dim]) ** 2 for dim, value in enumerate(coord))
        )

    @staticmethod
    def free_cross_axis_span(
        board: Board,
        anchor: Coord,
        axis: int,
        length: int,
    ) -> int:
        usable_templates = 0
        for anchor_index in range(length):
            start = tuple(
                value - (anchor_index if dim == axis else 0)
                for dim, value in enumerate(anchor)
            )
            coords = board.coords_for_slot(start, axis, length)
            if any(axis in board.axes_at(coord) for coord in coords):
                continue
            before = _advance(coords[0], axis, -1)
            after = _advance(coords[-1], axis, 1)
            if axis in board.axes_at(before) or axis in board.axes_at(after):
                continue
            usable_templates += 1
        return usable_templates

    @staticmethod
    def mean_distance_to_centroid(board: Board, coords: tuple[Coord, ...]) -> float:
        if not coords:
            return 0.0
        return sum(BoardScoring.distance_to_centroid(board, coord) for coord in coords) / len(coords)

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
