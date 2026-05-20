from __future__ import annotations

from collections.abc import Iterable

from ..benchmark.scoring import BoardScoring
from ..domain.board import Board
from ..domain.models import AnchorCandidate, Coord, SlotTemplate, TemplateCandidate
from .config import ScoringConfig


def top_anchors(
    board: Board,
    length: int,
    limit: int,
    scoring: ScoringConfig,
) -> tuple[AnchorCandidate, ...]:
    raw_candidates: list[tuple[Coord, str, int, float, float, int]] = []
    for coord, symbol in board.occupied_sorted():
        axis = _cross_axis(board, coord)
        if axis is None:
            continue
        coords = _slot_coords_around_anchor(board, coord, axis, length)
        bbox_increase = BoardScoring.bbox_area_increase(board, coords)
        distance = BoardScoring.distance_to_centroid(board, coord)
        free_span = BoardScoring.free_cross_axis_span(board, coord, axis, length)
        raw_candidates.append((coord, symbol, axis, bbox_increase, distance, free_span))

    normalized_distance = _normalize_feature(item[4] for item in raw_candidates)
    normalized_free_span = _normalize_feature(item[5] for item in raw_candidates)

    candidates: list[AnchorCandidate] = []
    for index, (coord, symbol, axis, bbox_increase, distance, free_span) in enumerate(
        raw_candidates
    ):
        score = (
            -scoring.anchor_centroid_weight * normalized_distance[index]
            + scoring.anchor_free_span_weight * normalized_free_span[index]
        )
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
    scoring: ScoringConfig,
) -> tuple[TemplateCandidate, ...]:
    raw_candidates: list[tuple[SlotTemplate, float, float, int, int]] = []
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
            raw_candidates.append(
                (template, bbox_increase, distance, len(new_coords), local_density)
            )

    normalized_bbox = _normalize_feature(item[1] for item in raw_candidates)
    normalized_distance = _normalize_feature(item[2] for item in raw_candidates)
    normalized_new_cell_count = _normalize_feature(item[3] for item in raw_candidates)
    normalized_local_density = _normalize_feature(item[4] for item in raw_candidates)

    candidates: list[TemplateCandidate] = []
    for index, (template, bbox_increase, distance, _, _) in enumerate(raw_candidates):
        score = (
            -scoring.template_bbox_weight * normalized_bbox[index]
            - scoring.template_centroid_weight * normalized_distance[index]
            + scoring.template_new_cell_bonus_weight * normalized_new_cell_count[index]
            - scoring.template_local_density_penalty_weight
            * normalized_local_density[index]
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


def _normalize_feature(values: Iterable[float]) -> tuple[float, ...]:
    typed_values = tuple(float(value) for value in values)
    if not typed_values:
        return ()
    minimum = min(typed_values)
    maximum = max(typed_values)
    if minimum == maximum:
        return tuple(0.0 for _ in typed_values)
    span = maximum - minimum
    return tuple((value - minimum) / span for value in typed_values)


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
