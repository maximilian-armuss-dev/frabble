from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .models import BoardConfiguration, Coord, Move, Segment, SegmentId, SlotAnalysis, SlotTemplate, Symbol


def _advance(coord: Coord, axis: int, offset: int) -> Coord:
    return tuple(value + (offset if dim == axis else 0) for dim, value in enumerate(coord))


@dataclass(frozen=True)
class Board:
    dimensions: int
    cells: Mapping[Coord, Symbol]
    segments: tuple[Segment, ...]

    def __post_init__(self) -> None:
        normalized_cells = dict(self.cells)
        for coord, symbol in normalized_cells.items():
            if len(coord) != self.dimensions:
                raise ValueError("Cell coordinate dimension does not match board dimensions.")
            if not symbol:
                raise ValueError("Board symbols must be non-empty strings.")

        normalized_segments = tuple(self.segments)
        symbol_index: dict[Symbol, set[Coord]] = {}
        coord_axes: dict[Coord, set[int]] = {}
        coord_segments: dict[Coord, set[SegmentId]] = {}

        for segment_id, segment in enumerate(normalized_segments):
            self._validate_segment(segment)
            for coord in self.coords_for_slot(segment.start, segment.axis, len(segment.sequence)):
                symbol_index.setdefault(normalized_cells[coord], set()).add(coord)
                coord_axes.setdefault(coord, set()).add(segment.axis)
                coord_segments.setdefault(coord, set()).add(segment_id)

        for coord, symbol in normalized_cells.items():
            symbol_index.setdefault(symbol, set()).add(coord)
            coord_axes.setdefault(coord, set())
            coord_segments.setdefault(coord, set())

        object.__setattr__(self, "cells", MappingProxyType(normalized_cells))
        object.__setattr__(self, "segments", normalized_segments)
        object.__setattr__(
            self,
            "symbol_index",
            MappingProxyType({symbol: frozenset(coords) for symbol, coords in symbol_index.items()}),
        )
        object.__setattr__(
            self,
            "coord_axes",
            MappingProxyType({coord: frozenset(axes) for coord, axes in coord_axes.items()}),
        )
        object.__setattr__(
            self,
            "coord_segments",
            MappingProxyType(
                {coord: frozenset(ids) for coord, ids in coord_segments.items()}
            ),
        )

    @classmethod
    def empty(cls, dimensions: int) -> "Board":
        return cls(dimensions=dimensions, cells={}, segments=())

    def _validate_segment(self, segment: Segment) -> None:
        if len(segment.start) != self.dimensions:
            raise ValueError("Segment start dimension does not match board dimensions.")
        if segment.axis < 0 or segment.axis >= self.dimensions:
            raise ValueError("Segment axis is outside board dimensions.")
        if not segment.sequence:
            raise ValueError("Segment sequence must not be empty.")
        for coord, symbol in zip(
            self.coords_for_slot(segment.start, segment.axis, len(segment.sequence)),
            segment.sequence,
            strict=True,
        ):
            if self.cells.get(coord) != symbol:
                raise ValueError("Segment sequence does not match board cells.")

    def get(self, coord: Coord) -> Symbol | None:
        return self.cells.get(coord)

    def has_tiles(self) -> bool:
        return bool(self.cells)

    def coords_for_slot(self, start: Coord, axis: int, length: int) -> tuple[Coord, ...]:
        if len(start) != self.dimensions:
            raise ValueError("Slot start dimension does not match board dimensions.")
        if axis < 0 or axis >= self.dimensions:
            raise ValueError("Slot axis is outside board dimensions.")
        if length < 1:
            raise ValueError("Slot length must be positive.")
        return tuple(_advance(start, axis, offset) for offset in range(length))

    def axes_at(self, coord: Coord) -> set[int]:
        return set(self.coord_axes.get(coord, frozenset()))

    def analyze_slot(self, template: SlotTemplate) -> SlotAnalysis:
        conflicts: list[Coord] = []
        fixed_symbols: dict[int, Symbol] = {}
        valid_shape = (
            len(template.start) == self.dimensions
            and len(template.anchor_coord) == self.dimensions
            and 0 <= template.axis < self.dimensions
            and 0 <= template.anchor_index < template.length
            and len(template.covered_coords) == template.length
            and template.covered_coords == self.coords_for_slot(
                template.start, template.axis, template.length
            )
            and template.covered_coords[template.anchor_index] == template.anchor_coord
        )
        if not valid_shape:
            conflicts.append(template.anchor_coord)

        has_overlap = False
        same_axis_overlap = False
        for index, coord in enumerate(template.covered_coords):
            current = self.get(coord)
            if current is None:
                continue
            has_overlap = True
            fixed_symbols[index] = current
            if coord == template.anchor_coord and current != template.anchor_symbol:
                conflicts.append(coord)
            if template.axis in self.axes_at(coord):
                same_axis_overlap = True

        previous_coord = _advance(template.start, template.axis, -1)
        next_coord = _advance(template.covered_coords[-1], template.axis, 1)
        touches_same_axis_neighbor = (
            template.axis in self.axes_at(previous_coord)
            or template.axis in self.axes_at(next_coord)
        )
        extends_existing_word = same_axis_overlap or touches_same_axis_neighbor
        valid_geometry = (
            valid_shape
            and has_overlap
            and not extends_existing_word
            and not conflicts
        )
        return SlotAnalysis(
            valid_geometry=valid_geometry,
            fixed_symbols=fixed_symbols,
            has_overlap=has_overlap,
            extends_existing_word=extends_existing_word,
            conflicts=tuple(conflicts),
        )

    def place(self, move: Move) -> "Board":
        if len(move.start) != self.dimensions:
            raise ValueError("Move start dimension does not match board dimensions.")
        if move.axis < 0 or move.axis >= self.dimensions:
            raise ValueError("Move axis is outside board dimensions.")
        if not move.sequence:
            raise ValueError("Move sequence must not be empty.")

        next_cells = dict(self.cells)
        coords = self.coords_for_slot(move.start, move.axis, len(move.sequence))
        for coord, symbol in zip(coords, move.sequence, strict=True):
            current = next_cells.get(coord)
            if current is not None and current != symbol:
                raise ValueError("Move conflicts with an existing board cell.")
            next_cells[coord] = symbol

        segment = Segment(start=move.start, axis=move.axis, sequence=move.sequence)
        return Board(
            dimensions=self.dimensions,
            cells=next_cells,
            segments=self.segments + (segment,),
        )

    def occupied_sorted(self) -> tuple[tuple[Coord, Symbol], ...]:
        return tuple(sorted(self.cells.items(), key=lambda item: item[0]))

    def to_configuration(self, rack: tuple[Symbol, ...]) -> BoardConfiguration:
        return BoardConfiguration(
            dimensions=self.dimensions,
            occupied=self.occupied_sorted(),
            rack=rack,
        )

    def render(self) -> str:
        rows = [
            f"{list(coord)}: {symbol}"
            for coord, symbol in self.occupied_sorted()
        ]
        if not rows:
            return f"{self.dimensions}D sparse board; no tiles."
        return "\n".join(rows)

