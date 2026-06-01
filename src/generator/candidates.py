from __future__ import annotations

from collections.abc import Callable, Iterable

from ..benchmark.scoring import BoardScoring
from ..domain.board import Board
from ..domain.models import AnchorCandidate, Coord, SlotTemplate, TemplateCandidate
from .config import ScoringConfig


def top_anchors(
    board: Board,
    length: int,
    limit: int | None,
    scoring: ScoringConfig,
    centroid: tuple[float, ...] | None = None,
) -> tuple[AnchorCandidate, ...]:
    if centroid is None:
        centroid = BoardScoring.centroid(board)
    raw_candidates: list[tuple[Coord, str, int, float, int]] = []
    for coord, symbol in board.occupied_sorted():
        for axis in _cross_axes(board, coord):
            distance = BoardScoring.distance_to_centroid(coord, centroid)
            free_span = BoardScoring.free_cross_axis_span(board, coord, axis, length)
            raw_candidates.append((coord, symbol, axis, distance, free_span))

    normalized_distance = _normalize_feature(item[3] for item in raw_candidates)
    normalized_free_span = _normalize_feature(item[4] for item in raw_candidates)

    candidates: list[AnchorCandidate] = []
    for index, (coord, symbol, axis, distance, free_span) in enumerate(raw_candidates):
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
                distance_to_centroid=distance,
                free_cross_axis_span=free_span,
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
        tuple[SlotTemplate, float, int, int, int, tuple[frozenset[str], ...]]
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
            domain_slack = 0
            if domains_for_template is not None:
                domains = domains_for_template(template)
                if any(not domain for domain in domains):
                    continue
                typed_domains = tuple(frozenset(domain) for domain in domains)
                domain_slack = sum(
                    len(domains[index])
                    for index, coord in enumerate(template.covered_coords)
                    if board.get(coord) is None
                )
            distance = BoardScoring.mean_distance_to_centroid(new_coords, centroid)
            local_density = BoardScoring.local_adjacent_density(board, new_coords)
            raw_candidates.append(
                (
                    template,
                    distance,
                    len(new_coords),
                    local_density,
                    domain_slack,
                    typed_domains,
                )
            )

    normalized_distance = _normalize_feature(item[1] for item in raw_candidates)
    normalized_new_cell_count = _normalize_feature(item[2] for item in raw_candidates)
    normalized_local_density = _normalize_feature(item[3] for item in raw_candidates)
    normalized_domain_slack = _normalize_feature(item[4] for item in raw_candidates)

    candidates: list[TemplateCandidate] = []
    for index, (template, distance, _, _, domain_slack, domains) in enumerate(raw_candidates):
        score = (
            -scoring.template_centroid_weight * normalized_distance[index]
            + scoring.template_new_cell_bonus_weight * normalized_new_cell_count[index]
            - scoring.template_local_density_penalty_weight
            * normalized_local_density[index]
            + scoring.template_domain_slack_weight * normalized_domain_slack[index]
        )
        candidates.append(
            TemplateCandidate(
                template=template,
                score=score,
                distance_to_centroid=distance,
                domains=domains,
                domain_slack=domain_slack,
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
