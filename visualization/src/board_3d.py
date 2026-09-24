"""Interactive 3D board view with cell-level multiplier geometry."""

from __future__ import annotations

from collections import Counter
from math import ceil, cos, floor, pi, sin, sqrt
from pathlib import Path
from typing import Mapping

from src.benchmark.scoring import tile_multiplier
from src.domain.board import Board
from src.domain.models import Coord

from .board_palette import BONUS_COLORS, LATEST_COLOR, PLANE_COLOR, REGULAR_COLOR
FIGURE_CONFIG = {
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["orbitRotation", "pan3d", "zoom3d", "tableRotation"],
    "toImageButtonOptions": {"format": "png", "width": 1800, "height": 1350, "scale": 2},
}

# Plotly's turntable fixes the upright axis. Correct the elevation once a
# drag ends, so the guard does not fight Plotly's camera during rotation.
CAMERA_GUARD_SCRIPT = """
(function () {
  const graph = document.getElementById('{plot_id}');
  const minAngle = 12 * Math.PI / 180;
  const maxAngle = 78 * Math.PI / 180;
  let pending = false;
  function constrain(update) {
    const camera = update['scene.camera'] ||
      (update.scene && update.scene.camera) ||
      graph._fullLayout.scene.camera;
    if (!camera || !camera.eye || pending) return;
    const eye = camera.eye;
    const radius = Math.hypot(eye.x, eye.y, eye.z);
    if (!(radius > 0)) return;
    const angle = Math.asin(Math.max(-1, Math.min(1, eye.z / radius)));
    const up = camera.up || {x: 0, y: 0, z: 1};
    if (angle >= minAngle && angle <= maxAngle && up.z > 0.999) return;
    const safeAngle = Math.max(minAngle, Math.min(maxAngle, angle));
    const azimuth = Math.atan2(eye.y, eye.x);
    const horizontal = radius * Math.cos(safeAngle);
    pending = true;
    requestAnimationFrame(function () {
      Promise.resolve(Plotly.relayout(graph, {
        'scene.camera.eye': {
          x: horizontal * Math.cos(azimuth),
          y: horizontal * Math.sin(azimuth),
          z: radius * Math.sin(safeAngle)
        },
        'scene.camera.up': {x: 0, y: 0, z: 1}
      })).finally(function () { pending = false; });
    });
  }
  graph.on('plotly_relayout', constrain);
})();
"""


def plot_board_3d(
    board: Board,
    *,
    latest: frozenset[Coord] = frozenset(),
    move_status: Mapping[Coord, str] | None = None,
    letter_scores: Mapping[str, int] | None = None,
    title: str = "3D board · multiplier planes",
) -> object:
    """Rotate a board and select one cell-colored bonus plane at a time."""
    import plotly.graph_objects as go

    if board.dimensions != 3:
        raise ValueError("The 3D preview requires a three-dimensional board.")
    if not board.cells:
        raise ValueError("The 3D preview requires at least one tile.")

    scores = letter_scores or {}
    bounds = tuple(
        (min(coord[axis] for coord in board.cells),
         max(coord[axis] for coord in board.cells))
        for axis in range(3)
    )
    fig = go.Figure()

    # A quiet xy floor anchors the up direction without Plotly's three
    # background walls, which obscure a large board in a paper screenshot.
    floor_z = bounds[2][0] - 1.4
    floor_x = (bounds[0][0] - 1.2, bounds[0][1] + 1.2)
    floor_y = (bounds[1][0] - 1.2, bounds[1][1] + 1.2)
    fig.add_trace(go.Mesh3d(
        x=[floor_x[0], floor_x[1], floor_x[1], floor_x[0]],
        y=[floor_y[0], floor_y[0], floor_y[1], floor_y[1]],
        z=[floor_z] * 4,
        i=[0, 0], j=[1, 2], k=[2, 3],
        color="#dbe6ed", opacity=0.16,
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter3d(
        x=[floor_x[0], floor_x[1], floor_x[1], floor_x[0], floor_x[0]],
        y=[floor_y[0], floor_y[0], floor_y[1], floor_y[1], floor_y[0]],
        z=[floor_z] * 5,
        mode="lines", line={"color": "#b8cbd6", "width": 2},
        hoverinfo="skip", showlegend=False,
    ))

    # Thin neutral connectors make the word directions apparent without
    # turning the occupied cells into a solid block.
    lines = [[], [], []]
    for segment in board.segments:
        end = list(segment.start)
        end[segment.axis] += len(segment.sequence) - 1
        for axis in range(3):
            lines[axis].extend((segment.start[axis], end[axis], None))
    if board.segments:
        fig.add_trace(go.Scatter3d(
            x=lines[0], y=lines[1], z=lines[2],
            mode="lines", line={"color": "#afbfcd", "width": 3},
            hoverinfo="skip", showlegend=False,
        ))

    categories = (
        ("Regular", 1, REGULAR_COLOR),
        ("Latest move", 0, LATEST_COLOR),
        ("×2", 2, BONUS_COLORS[2]),
        ("×3", 3, BONUS_COLORS[3]),
        ("×4", 4, BONUS_COLORS[4]),
    )
    for label, multiplier, color in categories:
        coords = [
            coord for coord in sorted(board.cells)
            if (tile_multiplier(coord) == multiplier if multiplier > 1
                else tile_multiplier(coord) == 1 and (coord in latest) == (multiplier == 0))
        ]
        if not coords:
            continue
        fig.add_trace(go.Scatter3d(
            x=[coord[0] for coord in coords],
            y=[coord[1] for coord in coords],
            z=[coord[2] for coord in coords],
            mode="markers",
            marker={
                "size": 10 if multiplier > 1 else 5,
                "color": color,
                "symbol": "diamond" if multiplier > 1 else "circle",
                "opacity": 0.98 if multiplier > 1 else 0.72,
                "line": {"color": "#ffffff", "width": 1},
            },
            customdata=[
                [board.cells[coord], scores.get(board.cells[coord], 0),
                 tile_multiplier(coord), "yes" if coord in latest else "no"]
                for coord in coords
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b> · (%{x}, %{y}, %{z})"
                "<br>Letter value %{customdata[1]} · cell bonus ×%{customdata[2]}"
                " (new tiles only)"
                "<br>Latest move: %{customdata[3]}<extra></extra>"
            ),
            name=label,
        ))

    status_by_coord = move_status or {}
    for status, label, color in (
        ("new", "New tile", LATEST_COLOR),
        ("matched", "Reused tile", "#39956c"),
        ("conflict", "Conflict", "#b84747"),
    ):
        coords = [
            coord for coord in sorted(status_by_coord)
            if status_by_coord[coord] == status and coord in board.cells
        ]
        if coords:
            fig.add_trace(go.Scatter3d(
                x=[coord[0] for coord in coords],
                y=[coord[1] for coord in coords],
                z=[coord[2] for coord in coords],
                mode="markers",
                marker={"size": 15, "symbol": "diamond-open", "color": color,
                        "line": {"color": color, "width": 2}},
                hoverinfo="skip", name=label,
            ))

    sum_min = min(sum(coord) for coord in board.cells)
    sum_max = max(sum(coord) for coord in board.cells)
    planes = [
        2 + 10 * k
        for k in range(ceil((sum_min - 2) / 10), floor((sum_max - 2) / 10) + 1)
    ]
    counts = Counter(sum(coord) for coord in board.cells)
    selected = max(planes, key=lambda value: (counts[value], -abs(value - 2))) if planes else None
    board_center = tuple(
        sum(coord[axis] for coord in board.cells) / len(board.cells)
        for axis in range(3)
    )
    radius = 0.68 * max(high - low for low, high in bounds)
    plane_indices: dict[int, tuple[int, ...]] = {}
    plane_vertices: dict[int, list[tuple[float, float, float]]] = {}
    for plane_sum in planes:
        vertices = _plane_hexagon(plane_sum, board_center, radius)
        plane_vertices[plane_sum] = vertices
        shown = plane_sum == selected
        trace_indices = []
        trace_indices.append(len(fig.data))
        fig.add_trace(go.Mesh3d(
            x=[vertex[0] for vertex in vertices],
            y=[vertex[1] for vertex in vertices],
            z=[vertex[2] for vertex in vertices],
            i=[0, 0, 0, 0], j=[1, 2, 3, 4], k=[2, 3, 4, 5],
            color="#d2e0e9", opacity=0.11, flatshading=True,
            hoverinfo="skip", showlegend=False, visible=shown,
        ))
        trace_indices.append(len(fig.data))
        ring = vertices + vertices[:1]
        fig.add_trace(go.Scatter3d(
            x=[point[0] for point in ring],
            y=[point[1] for point in ring],
            z=[point[2] for point in ring],
            mode="lines", line={"color": PLANE_COLOR, "width": 6},
            hoverinfo="skip", showlegend=False, visible=shown,
        ))
        trace_indices.append(len(fig.data))
        guide = [vertices[0], vertices[3], None, vertices[1], vertices[4], None,
                 vertices[2], vertices[5], None]
        fig.add_trace(go.Scatter3d(
            x=[point[0] if point else None for point in guide],
            y=[point[1] if point else None for point in guide],
            z=[point[2] if point else None for point in guide],
            mode="lines", line={"color": PLANE_COLOR, "width": 2}, opacity=0.3,
            hoverinfo="skip", showlegend=False, visible=shown,
        ))
        lattice = _plane_lattice_coords(plane_sum, board_center, radius)
        for multiplier, color in BONUS_COLORS.items():
            coords = [coord for coord in lattice if tile_multiplier(coord) == multiplier]
            trace_indices.append(len(fig.data))
            fig.add_trace(go.Scatter3d(
                x=[coord[0] for coord in coords],
                y=[coord[1] for coord in coords],
                z=[coord[2] for coord in coords],
                mode="markers",
                marker={"size": 4, "color": color, "symbol": "circle", "opacity": 0.7},
                hovertemplate=(
                    f"Available ×{multiplier} cell · (%{{x}}, %{{y}}, %{{z}})"
                    "<extra></extra>"
                ),
                name=f"Available ×{multiplier}", showlegend=False, visible=shown,
            ))
        plane_indices[plane_sum] = tuple(trace_indices)

    def view_ranges(plane_sum: int | None) -> tuple[tuple[float, float], ...]:
        points = list(board.cells) + plane_vertices.get(plane_sum, []) + [
            (floor_x[0], floor_y[0], floor_z),
            (floor_x[1], floor_y[1], floor_z),
        ]
        return tuple(
            (min(point[axis] for point in points) - 0.7,
             max(point[axis] for point in points) + 0.7)
            for axis in range(3)
        )

    if plane_indices:
        base_count = min(index for pair in plane_indices.values() for index in pair)
        buttons = []
        for plane_sum in plane_indices:
            visible = [True] * base_count + [False] * (len(fig.data) - base_count)
            for index in plane_indices[plane_sum]:
                visible[index] = True
            ranges = view_ranges(plane_sum)
            buttons.append({
                "label": f"Σ={plane_sum}",
                "method": "update", "args": [
                    {"visible": visible},
                    {f"scene.{name}axis.range": ranges[index]
                     for index, name in enumerate("xyz")},
                ],
            })
        fig.update_layout(updatemenus=[{
            "buttons": buttons,
            "direction": "down", "x": 0.98, "y": 1.05,
            "xanchor": "right", "yanchor": "top",
            "bgcolor": "#ffffff", "bordercolor": "#b9c8d3",
        }])

    scene_ranges = view_ranges(selected)
    fig.update_layout(
        title={"text": title + "<br><sup>Small dots: bonus sites · Large diamonds: occupied bonus tiles</sup>", "x": 0.02, "y": 0.98,
               "font": {"size": 21, "color": "#24384b"}},
        autosize=True, height=500,
        paper_bgcolor="#ffffff",
        font={"family": "Arial, sans-serif", "color": "#334b60", "size": 13},
        margin={"l": 8, "r": 8, "t": 76, "b": 40},
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "y": 0.01,
                "bgcolor": "rgba(255,255,255,0.9)", "font": {"size": 12}},
        scene={
            "xaxis": {"title": "axis 0", "showbackground": False,
                      "gridcolor": "#e2eaf0", "zerolinecolor": "#c8d5de", "range": scene_ranges[0]},
            "yaxis": {"title": "axis 1", "showbackground": False,
                      "gridcolor": "#e2eaf0", "zerolinecolor": "#c8d5de", "range": scene_ranges[1]},
            "zaxis": {"title": "axis 2 · up", "showbackground": False,
                      "gridcolor": "#e2eaf0", "zerolinecolor": "#c8d5de", "range": scene_ranges[2]},
            "aspectmode": "data",
            "camera": {
                "up": {"x": 0, "y": 0, "z": 1},
                "eye": {"x": 1.6, "y": 1.35, "z": 1.25},
                "projection": {"type": "orthographic"},
            },
            "dragmode": "turntable",
        },
    )
    return fig


def _plane_hexagon(
    plane_sum: int,
    board_center: tuple[float, float, float],
    radius: float,
) -> list[tuple[float, float, float]]:
    """A free-standing regular hexagon on x0+x1+x2=plane_sum."""
    shift = (plane_sum - sum(board_center)) / 3
    center = tuple(value + shift for value in board_center)
    u = (1 / sqrt(2), -1 / sqrt(2), 0)
    v = (1 / sqrt(6), 1 / sqrt(6), -2 / sqrt(6))
    return [
        tuple(
            center[axis]
            + radius * (cos(index * pi / 3) * u[axis] + sin(index * pi / 3) * v[axis])
            for axis in range(3)
        )
        for index in range(6)
    ]


def _plane_lattice_coords(
    plane_sum: int,
    board_center: tuple[float, float, float],
    radius: float,
) -> list[Coord]:
    """Integer bonus sites in the central part of a displayed hexagonal plane."""
    shift = (plane_sum - sum(board_center)) / 3
    center = tuple(value + shift for value in board_center)
    lattice_radius = radius * 0.76
    u = (1 / sqrt(2), -1 / sqrt(2), 0)
    v = (1 / sqrt(6), 1 / sqrt(6), -2 / sqrt(6))
    vertices = _plane_hexagon(plane_sum, board_center, lattice_radius)
    coords: list[Coord] = []
    for x in range(floor(min(point[0] for point in vertices)),
                   ceil(max(point[0] for point in vertices)) + 1):
        for y in range(floor(min(point[1] for point in vertices)),
                       ceil(max(point[1] for point in vertices)) + 1):
            coord = (x, y, plane_sum - x - y)
            delta = tuple(coord[axis] - center[axis] for axis in range(3))
            a = sum(delta[axis] * u[axis] for axis in range(3))
            b = sum(delta[axis] * v[axis] for axis in range(3))
            if (abs(b) <= sqrt(3) * lattice_radius / 2
                    and abs(a + b / sqrt(3)) <= lattice_radius
                    and abs(a - b / sqrt(3)) <= lattice_radius):
                coords.append(coord)
    return coords


def write_grounded_html(figure: object, path: str | Path) -> Path:
    """Save the interactive preview with the upper-hemisphere camera guard."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(
        target,
        include_plotlyjs="cdn",
        full_html=True,
        post_script=CAMERA_GUARD_SCRIPT,
        config=FIGURE_CONFIG,
    )
    return target


def display_grounded_3d(figure: object) -> None:
    """Display the same guarded view inside a trusted Jupyter notebook."""
    from IPython.display import HTML, display

    plot = figure.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        post_script=CAMERA_GUARD_SCRIPT,
        config=FIGURE_CONFIG,
    )
    display(HTML(f'<div style="width:100%;max-width:760px">{plot}</div>'))
