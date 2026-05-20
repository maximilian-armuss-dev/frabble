from __future__ import annotations

from ..benchmark.scoring import BoardScoring
from ..domain.board import Board
from ..domain.models import AnchorCandidate, Coord, SlotTemplate, TemplateCandidate

NEW_CELL_BONUS_WEIGHT = 1.5
LOCAL_DENSITY_PENALTY_WEIGHT = 1.0


def top_anchors(
    board: Board,
    length: int,
    limit: int,
) -> tuple[AnchorCandidate, ...]:
    candidates: list[AnchorCandidate] = []
    for coord, symbol in board.occupied_sorted():
        axis = _cross_axis(board, coord)
        if axis is None:
            continue
        coords = _slot_coords_around_anchor(board, coord, axis, length)
        bbox_increase = BoardScoring.bbox_area_increase(board, coords)
        distance = BoardScoring.distance_to_centroid(board, coord)
        free_span = BoardScoring.free_cross_axis_span(board, coord, axis, length)
        score = -bbox_increase - distance + free_span
        candidates.append(
            AnchorCandidate(
                coord=coord,
                symbol=symbol,
                axis=axis,
                score=score,
                bbox_area_increase=bbox_increase,
                distance_to_centroid=distance,
                free_cross_axis_span=free_span,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.coord,
                candidate.axis,
                candidate.symbol,
            ),
        )[:limit]
    )


def top_templates(
    board: Board,
    anchors: tuple[AnchorCandidate, ...],
    length: int,
    limit: int,
) -> tuple[TemplateCandidate, ...]:
    candidates: list[TemplateCandidate] = []
    for anchor in anchors:
        for anchor_index in range(length):
            start = tuple(
                value - (anchor_index if dim == anchor.axis else 0)
                for dim, value in enumerate(anchor.coord)
            )
            template = SlotTemplate(
                anchor_coord=anchor.coord,
                anchor_symbol=anchor.symbol,
                axis=anchor.axis,
                length=length,
                anchor_index=anchor_index,
                start=start,
                covered_coords=board.coords_for_slot(start, anchor.axis, length),
            )
            analysis = board.analyze_slot(template)
            if not analysis.valid_geometry:
                continue
            new_coords = tuple(
                coord for coord in template.covered_coords if board.get(coord) is None
            )
            if not new_coords:
                continue
            bbox_increase = BoardScoring.bbox_area_increase(board, template.covered_coords)
            distance = BoardScoring.mean_distance_to_centroid(board, new_coords)
            local_density = BoardScoring.local_adjacent_density(board, new_coords)
            score = (
                -bbox_increase
                - distance
                + NEW_CELL_BONUS_WEIGHT * len(new_coords)
                - LOCAL_DENSITY_PENALTY_WEIGHT * local_density
            )
            candidates.append(
                TemplateCandidate(
                    template=template,
                    score=score,
                    bbox_area_increase=bbox_increase,
                    distance_to_centroid=distance,
                )
            )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.template.anchor_coord,
                candidate.template.axis,
                candidate.template.anchor_index,
                candidate.template.start,
            ),
        )[:limit]
    )


def _cross_axis(board: Board, coord: Coord) -> int | None:
    axes = board.axes_at(coord)
    if axes == {0}:
        return 1
    if axes == {1}:
        return 0
    return None


def _slot_coords_around_anchor(
    board: Board,
    anchor: Coord,
    axis: int,
    length: int,
) -> tuple[Coord, ...]:
    coords: list[Coord] = []
    for anchor_index in range(length):
        start = tuple(
            value - (anchor_index if dim == axis else 0)
            for dim, value in enumerate(anchor)
        )
        coords.extend(board.coords_for_slot(start, axis, length))
    return tuple(coords)
