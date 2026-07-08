from __future__ import annotations

from collections.abc import Callable, Iterable

from ..benchmark.scoring import BoardScoring
from ..domain.board import Board
from ..domain.models import AnchorCandidate, Coord, SlotTemplate, TemplateCandidate
from .config import ScoringConfig


def top_anchors(
    board: Board,
    limit: int | None,
    scoring: ScoringConfig,
    centroid: tuple[float, ...] | None = None,
) -> tuple[AnchorCandidate, ...]:
    if centroid is None:
        centroid = BoardScoring.centroid(board)
    raw_candidates: list[tuple[Coord, str, int, float]] = []
    for coord, symbol in board.occupied_sorted():
        for axis in _cross_axes(board, coord):
            distance = BoardScoring.distance_to_centroid(coord, centroid)
            raw_candidates.append((coord, symbol, axis, distance))

    normalized_distance = _normalize_feature(item[3] for item in raw_candidates)

    candidates: list[AnchorCandidate] = []
    for index, (coord, symbol, axis, distance) in enumerate(raw_candidates):
        score = -scoring.anchor_centroid_weight * normalized_distance[index]
        candidates.append(
            AnchorCandidate(
                coord=coord,
                symbol=symbol,
                axis=axis,
                score=score,
                distance_to_centroid=distance,
            )
        )
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.coord,
            candidate.axis,
            candidate.symbol,
        ),
    )
    return tuple(ranked if limit is None else ranked[:limit])


def top_templates(
    board: Board,
    anchors: tuple[AnchorCandidate, ...],
    length: int,
    limit: int,
    scoring: ScoringConfig,
    *,
    prune: Callable[[SlotTemplate], bool] | None = None,
    domains_for_template: Callable[[SlotTemplate], list[set[str]]] | None = None,
    seen_slots: set[tuple[Coord, int, int]] | None = None,
    centroid: tuple[float, ...] | None = None,
) -> tuple[TemplateCandidate, ...]:
    if centroid is None:
        centroid = BoardScoring.centroid(board)
    raw_candidates: list[
        tuple[
            SlotTemplate,
            float,
            int,
            tuple[frozenset[str], ...],
        ]
    ] = []
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
            slot_key = (template.start, template.axis, template.length)
            if seen_slots is not None:
                if slot_key in seen_slots:
                    continue
                seen_slots.add(slot_key)
            analysis = board.analyze_slot(template)
            if not analysis.valid_geometry:
                continue
            if prune is not None and prune(template):
                continue
            new_coords = tuple(
                coord for coord in template.covered_coords if board.get(coord) is None
            )
            if not new_coords:
                continue
            typed_domains: tuple[frozenset[str], ...] = ()
            if domains_for_template is not None:
                domains = domains_for_template(template)
                if any(not domain for domain in domains):
                    continue
                typed_domains = tuple(frozenset(domain) for domain in domains)
            distance = BoardScoring.mean_distance_to_centroid(new_coords, centroid)
            local_density = BoardScoring.local_adjacent_density(board, new_coords)
            raw_candidates.append(
                (
                    template,
                    distance,
                    local_density,
                    typed_domains,
                )
            )

    normalized_distance = _normalize_feature(item[1] for item in raw_candidates)
    normalized_local_density = _normalize_feature(item[2] for item in raw_candidates)

    candidates: list[TemplateCandidate] = []
    for index, (template, distance, _, domains) in enumerate(raw_candidates):
        score = (
            -scoring.template_centroid_weight * normalized_distance[index]
            - scoring.template_local_density_penalty_weight
            * normalized_local_density[index]
        )
        candidates.append(
            TemplateCandidate(
                template=template,
                score=score,
                distance_to_centroid=distance,
                domains=domains,
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


def _cross_axes(board: Board, coord: Coord) -> tuple[int, ...]:
    axes = board.axes_at(coord)
    if not axes:
        return ()
    return tuple(axis for axis in range(board.dimensions) if axis not in axes)
