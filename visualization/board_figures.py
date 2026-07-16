from __future__ import annotations

import base64
import html
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from src.domain.board import Board
from src.domain.models import Coord
from src.generator.reconstruction import reconstruct_boards

BASE_TILE = "#f7f8fa"
TEXT_COLOR = "#15181d"
TEXT_FONT_FAMILY = "DejaVu Sans Mono, Menlo, Consolas, monospace"
NEW_MOVE_TILE = "#bfdbfe"
MATCHING_MOVE_TILE = "#bbf7d0"
CONFLICTING_MOVE_TILE = "#fecaca"
PLOT_MARGIN = 4
PLOT_PAD_2D = 0.53
TILE_GAP = 2
CELL_SIZE_2D = 58
MIN_LETTER_SIZE_2D = 6
MIN_PLOT_SIZE_2D = 180
MAX_PLOT_SIZE_2D = 520
ANIMATION_CONTROLS_HEIGHT = 56
TRANSPARENT_COLOR = "rgba(0, 0, 0, 0)"
NODE_MARKER_TEXT_SIZE_2D = 16
NODE_MARKER_MAX_SIZE_2D = 48
NODE_MARKER_MIN_SIZE_2D = 10
LETTER_RASTER_SIZE_2D = 0.54
LETTER_RASTER_RESOLUTION_2D = 18
IMAGE_CELL_PIXELS_2D = 42
IMAGE_TILE_GAP_PIXELS_2D = 2
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_scenario_path(name_or_path: str | Path) -> Path:
    """Resolve a scenario path (relative to the project root or cwd) or a bare
    scenario name under outputs/scenarios/."""
    path = Path(name_or_path)
    candidates = [path]
    if path.suffix != ".json":
        candidates.append(path.with_suffix(".json"))
    if not path.is_absolute():
        candidates.append(PROJECT_ROOT / path)
        if path.suffix != ".json":
            candidates.append(PROJECT_ROOT / path.with_suffix(".json"))
        if path.parent == Path("."):
            candidates.append(PROJECT_ROOT / "outputs" / "scenarios" / path)
            if path.suffix != ".json":
                candidates.append(
                    PROJECT_ROOT / "outputs" / "scenarios" / path.with_suffix(".json")
                )
            candidates.append(PROJECT_ROOT / "outputs" / path)
            if path.suffix != ".json":
                candidates.append(PROJECT_ROOT / "outputs" / path.with_suffix(".json"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Scenario JSON not found: {name_or_path}")


def load_scenario_json(path: str | Path) -> dict[str, object]:
    """Load a generator scenario JSON file."""
    with resolve_scenario_path(path).open(encoding="utf-8") as file:
        return json.load(file)


def board_from_scenario_json(path: str | Path, *, step: int = -1) -> Board:
    """Load one board from a scenario JSON file.

    ``step=0`` returns the initial board; ``step=-1`` returns the final board.
    """
    boards, _ = scenario_boards_and_placements(load_scenario_json(path))
    return boards[step]


def scenario_boards_and_placements(
    scenario: Mapping[str, object],
) -> tuple[tuple[Board, ...], tuple[frozenset[Coord], ...]]:
    """Reconstruct every board and the cells newly placed at each step."""
    boards = reconstruct_boards(dict(scenario))
    placements: list[frozenset[Coord]] = [frozenset()]
    for transition in scenario.get("transitions", []):
        placed = transition["placed"]  # type: ignore[index]
        placements.append(
            frozenset(
                tuple(int(value) for value in coord)
                for coord, _symbol in placed
            )
        )
    return boards, tuple(placements)


def plot_board_2d(
    board: Board,
    *,
    tile_colors: Mapping[Coord, str] | None = None,
    title: str | None = None,
) -> object:
    """Create an interactive Plotly view of a two-dimensional board."""
    if board.dimensions != 2:
        raise ValueError("plot_board_2d requires a two-dimensional board.")
    return _plot_board_plane_2d(
        board,
        axes=(0, 1),
        plane_coords={},
        tile_colors=tile_colors,
        title=title,
    )


def plot_board_axis_pairs(
    board: Board,
    *,
    move_axis: int,
    plane_coord: Coord,
    tile_colors: Mapping[Coord, str] | None = None,
    title: str | None = None,
) -> tuple[object, ...]:
    """Plot every 2D plane pairing the move axis with another board axis."""
    if board.dimensions < 2:
        raise ValueError("Visualization requires at least two board dimensions.")
    if move_axis < 0 or move_axis >= board.dimensions:
        raise ValueError("move_axis must be a valid board dimension.")
    if len(plane_coord) != board.dimensions:
        raise ValueError("plane_coord dimensionality must match the board.")

    figures = []
    for other_axis in range(board.dimensions):
        if other_axis == move_axis:
            continue
        axes = (move_axis, other_axis)
        hidden_coords = {
            axis: plane_coord[axis]
            for axis in range(board.dimensions)
            if axis not in axes
        }
        pair_title = f"axes {move_axis}, {other_axis}"
        if title:
            pair_title = f"{title} - {pair_title}"
        figures.append(
            _plot_board_plane_2d(
                board,
                axes=axes,
                plane_coords=hidden_coords,
                tile_colors=tile_colors,
                title=pair_title,
            )
        )
    return tuple(figures)


def _plot_board_plane_2d(
    board: Board,
    *,
    axes: tuple[int, int],
    plane_coords: Mapping[int, int],
    tile_colors: Mapping[Coord, str] | None,
    title: str | None,
) -> object:
    import plotly.graph_objects as go

    _validate_plane(board, axes, plane_coords)
    extent_board = _plane_extent(board, plane_coords)
    fig = go.Figure(
        data=_board_2d_traces(
            board,
            tile_colors=tile_colors or {},
            axes=axes,
            plane_coords=plane_coords,
        )
    )
    _style_plotly_xy(fig, extent_board, axes, title)
    return fig


def animate_scenario_2d(
    scenario: Mapping[str, object],
    *,
    title: str | None = None,
) -> object:
    """Create an interactive Plotly slider for a two-dimensional scenario."""
    import plotly.graph_objects as go

    boards, placements = scenario_boards_and_placements(scenario)
    _require_2d_board(boards[0])
    axes = (0, 1)
    range_board = _union_board_extent(boards)
    base_fig = go.Figure(
        data=_board_2d_traces(
            boards[0],
            tile_colors=_placement_colors(placements[0]),
            axes=axes,
            plane_coords={},
            range_board=range_board,
        )
    )
    _style_plotly_xy(base_fig, range_board, axes, title)
    frames = []
    for index, (board, placed) in enumerate(zip(boards, placements, strict=True)):
        frames.append(
            go.Frame(
                data=_board_2d_traces(
                    board,
                    tile_colors=_placement_colors(placed),
                    axes=axes,
                    plane_coords={},
                    range_board=range_board,
                ),
                name=str(index),
            )
        )

    base_fig.frames = frames
    base_fig.update_layout(
        sliders=[
            {
                "currentvalue": {
                    "visible": True,
                    "prefix": "",
                    "xanchor": "left",
                    "font": {"color": TEXT_COLOR},
                },
                "font": {"color": TRANSPARENT_COLOR},
                "tickcolor": TRANSPARENT_COLOR,
                "pad": {"t": 6},
                "ticklen": 0,
                "steps": [
                    {
                        "label": str(index),
                        "method": "animate",
                        "args": [
                            [str(index)],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0, "redraw": True},
                            },
                        ],
                    }
                    for index in range(len(boards))
                ],
            }
        ],
        height=base_fig.layout.height + ANIMATION_CONTROLS_HEIGHT,
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": 36},
    )
    return base_fig


def animate_scenario_2d_image(
    scenario: Mapping[str, object],
    *,
    title: str | None = None,
    cell_pixels: int = IMAGE_CELL_PIXELS_2D,
) -> object:
    """Create a fast Plotly slider that swaps pre-rendered 2D PNG frames."""
    import plotly.graph_objects as go

    boards, placements = scenario_boards_and_placements(scenario)
    _require_2d_board(boards[0])
    axes = (0, 1)
    range_board = _union_board_extent(boards)
    base_source = _board_png_source_2d(
        boards[0],
        tile_colors=_placement_colors(placements[0]),
        axes=axes,
        plane_coords={},
        range_board=range_board,
        cell_pixels=cell_pixels,
    )
    base_fig = go.Figure(data=[go.Image(source=base_source, hoverinfo="skip")])
    frames = []
    for index, (board, placed) in enumerate(zip(boards, placements, strict=True)):
        frames.append(
            go.Frame(
                data=[
                    go.Image(
                        source=_board_png_source_2d(
                            board,
                            tile_colors=_placement_colors(placed),
                            axes=axes,
                            plane_coords={},
                            range_board=range_board,
                            cell_pixels=cell_pixels,
                        ),
                        hoverinfo="skip",
                    )
                ],
                name=str(index),
            )
        )

    base_fig.frames = frames
    width, height = _image_plot_size_2d(range_board, axes, cell_pixels)
    base_fig.update_layout(
        xaxis={"visible": False, "showgrid": False, "zeroline": False},
        yaxis={"visible": False, "showgrid": False, "zeroline": False},
        width=width,
        height=height + ANIMATION_CONTROLS_HEIGHT,
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": 36},
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        title=title,
        sliders=[
            {
                "currentvalue": {
                    "visible": True,
                    "prefix": "",
                    "xanchor": "left",
                    "font": {"color": TEXT_COLOR},
                },
                "font": {"color": TRANSPARENT_COLOR},
                "tickcolor": TRANSPARENT_COLOR,
                "pad": {"t": 6},
                "ticklen": 0,
                "steps": [
                    {
                        "label": str(index),
                        "method": "animate",
                        "args": [
                            [str(index)],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0, "redraw": True},
                            },
                        ],
                    }
                    for index in range(len(boards))
                ],
            }
        ],
    )
    return base_fig


def animate_scenario_2d_canvas(
    scenario: Mapping[str, object],
    *,
    title: str | None = None,
    cell_pixels: int = IMAGE_CELL_PIXELS_2D,
) -> object:
    """Create a preloaded canvas slider for smooth large 2D animations."""
    boards, placements = scenario_boards_and_placements(scenario)
    _require_2d_board(boards[0])
    axes = (0, 1)
    range_board = _union_board_extent(boards)
    frames = [
        _board_png_source_2d(
            board,
            tile_colors=_placement_colors(placed),
            axes=axes,
            plane_coords={},
            range_board=range_board,
            cell_pixels=cell_pixels,
        )
        for board, placed in zip(boards, placements, strict=True)
    ]
    width, height = _image_plot_size_2d(range_board, axes, cell_pixels)
    widget_id = f"scenario2d_{id(frames)}"
    title_html = (
        f"<div class='scenario-title'>{html.escape(title)}</div>" if title else ""
    )
    payload = json.dumps(frames)
    markup = f"""
<div id="{widget_id}" class="scenario-canvas-widget">
  {title_html}
  <canvas width="{width}" height="{height}" style="width:{width}px;height:{height}px;image-rendering:pixelated;"></canvas>
  <div style="display:flex;align-items:center;gap:8px;width:{width}px;">
    <input type="range" min="0" max="{len(frames) - 1}" value="0" step="1" style="flex:1;">
    <span style="min-width:3em;text-align:right;font:12px sans-serif;color:{TEXT_COLOR};">0</span>
  </div>
</div>
<script>
(() => {{
  const root = document.getElementById({json.dumps(widget_id)});
  const frames = {payload};
  const canvas = root.querySelector("canvas");
  const ctx = canvas.getContext("2d");
  const slider = root.querySelector("input");
  const label = root.querySelector("span");
  const images = frames.map(src => {{
    const img = new Image();
    img.src = src;
    return img;
  }});
  function draw(index) {{
    const img = images[index];
    label.textContent = String(index);
    if (img.complete) {{
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    }} else {{
      img.onload = () => draw(index);
    }}
  }}
  slider.addEventListener("input", event => draw(Number(event.target.value)));
  draw(0);
}})();
</script>
"""
    try:
        from IPython.display import HTML

        return HTML(markup)
    except ImportError:
        return markup


def _board_2d_traces(
    board: Board,
    *,
    tile_colors: Mapping[Coord, str],
    axes: tuple[int, int],
    plane_coords: Mapping[int, int],
    range_board: Board | None = None,
) -> list[object]:
    return [
        _board_marker_trace_2d(
            board,
            tile_colors=tile_colors,
            axes=axes,
            plane_coords=plane_coords,
            range_board=range_board,
        )
    ]


def _board_marker_trace_2d(
    board: Board,
    *,
    tile_colors: Mapping[Coord, str],
    axes: tuple[int, int],
    plane_coords: Mapping[int, int],
    range_board: Board | None = None,
) -> object:
    import plotly.graph_objects as go

    rows = _projected_rows(board, axes, plane_coords)
    bounds_board = range_board or board
    marker_size = _marker_size_2d(bounds_board, axes)
    text_size = _clamp(
        round(marker_size * 0.42),
        MIN_LETTER_SIZE_2D,
        NODE_MARKER_TEXT_SIZE_2D,
    )
    return go.Scatter(
        x=[row["x"] for row in rows],
        y=[row["y"] for row in rows],
        mode="markers+text",
        marker={
            "size": marker_size,
            "color": _node_colors_2d(rows, tile_colors),
            "symbol": "square",
            "line": {"color": TRANSPARENT_COLOR, "width": 0},
        },
        text=[row["symbol"] for row in rows],
        textfont={
            "color": TEXT_COLOR,
            "size": text_size,
            "family": TEXT_FONT_FAMILY,
        },
        textposition="middle center",
        customdata=[
            [
                list(row["coord"]),
                ",".join(str(axis) for axis in sorted(row["axes_at"])),
            ]
            for row in rows
        ],
        hovertemplate=(
            "coord=%{customdata[0]}<br>symbol=%{text}"
            "<br>axes=%{customdata[1]}<extra></extra>"
        ),
        showlegend=False,
    )


def _board_png_source_2d(
    board: Board,
    *,
    tile_colors: Mapping[Coord, str],
    axes: tuple[int, int],
    plane_coords: Mapping[int, int],
    range_board: Board,
    cell_pixels: int,
) -> str:
    import numpy as np
    from PIL import Image

    visible_cells = _plane_cells(board, plane_coords)
    x_values, y_values = _axis_values(range_board, axes)
    width = len(x_values) * cell_pixels
    height = len(y_values) * cell_pixels
    image = np.zeros((height, width, 4), dtype=np.uint8)
    x_index = {value: index for index, value in enumerate(x_values)}
    y_index = {value: index for index, value in enumerate(reversed(y_values))}
    gap = min(IMAGE_TILE_GAP_PIXELS_2D, max(cell_pixels // 6, 1))
    for coord, symbol in visible_cells:
        left = x_index[coord[axes[0]]] * cell_pixels + gap
        top = y_index[coord[axes[1]]] * cell_pixels + gap
        right = (x_index[coord[axes[0]]] + 1) * cell_pixels - gap
        bottom = (y_index[coord[axes[1]]] + 1) * cell_pixels - gap
        color = _color_to_rgb(tile_colors.get(coord, BASE_TILE))
        image[top:bottom, left:right, :3] = color
        image[top:bottom, left:right, 3] = 255
        mask = _letter_bitmap_mask_2d(str(symbol), cell_pixels)
        tile = image[top:bottom, left:right]
        mask = mask[gap : cell_pixels - gap, gap : cell_pixels - gap]
        tile[mask, :3] = _color_to_rgb(TEXT_COLOR)
        tile[mask, 3] = 255

    buffer = io.BytesIO()
    Image.fromarray(image, mode="RGBA").save(buffer, format="PNG", optimize=False)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=256)
def _letter_bitmap_mask_2d(symbol: str, cell_pixels: int) -> object:
    import numpy as np

    mask = np.zeros((cell_pixels, cell_pixels), dtype=bool)
    for quad in _letter_fill_quads(
        symbol,
        LETTER_RASTER_SIZE_2D,
        LETTER_RASTER_RESOLUTION_2D,
    ):
        xs = [point[0] for point in quad]
        ys = [point[1] for point in quad]
        left = max(0, int((min(xs) + 0.5) * cell_pixels))
        right = min(cell_pixels, int((max(xs) + 0.5) * cell_pixels) + 1)
        top = max(0, int((0.5 - max(ys)) * cell_pixels))
        bottom = min(cell_pixels, int((0.5 - min(ys)) * cell_pixels) + 1)
        mask[top:bottom, left:right] = True
    return mask


def _image_plot_size_2d(
    board: Board,
    axes: tuple[int, int],
    cell_pixels: int,
) -> tuple[int, int]:
    x_values, y_values = _axis_values(board, axes)
    return len(x_values) * cell_pixels, len(y_values) * cell_pixels


@lru_cache(maxsize=256)
def _letter_fill_quads(
    symbol: str,
    size: float,
    resolution: int,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    from matplotlib.textpath import TextPath

    glyph = symbol or "?"
    path = TextPath((0.0, 0.0), glyph, size=1.0)
    vertices = path.vertices
    if len(vertices) == 0:
        half = size / 2.0
        return (((-half, -half), (half, -half), (half, half), (-half, half)),)

    min_x = min(float(point[0]) for point in vertices)
    max_x = max(float(point[0]) for point in vertices)
    min_y = min(float(point[1]) for point in vertices)
    max_y = max(float(point[1]) for point in vertices)
    height = max(max_y - min_y, 1e-9)
    scale = size / max(_letter_reference_height(), height, 1e-9)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    step = size / resolution
    quads: list[tuple[tuple[float, float], ...]] = []
    for x_index in range(resolution):
        px = -size / 2.0 + step * (x_index + 0.5)
        original_x = px / scale + center_x
        for y_index in range(resolution):
            py = -size / 2.0 + step * (y_index + 0.5)
            original_y = py / scale + center_y
            if not path.contains_point((original_x, original_y)):
                continue
            left = px - step / 2.0
            right = px + step / 2.0
            bottom = py - step / 2.0
            top = py + step / 2.0
            quads.append(
                ((left, bottom), (right, bottom), (right, top), (left, top))
            )
    if not quads:
        half = size / 2.0
        return (((-half, -half), (half, -half), (half, half), (-half, half)),)
    return tuple(
        tuple((float(point[0]), float(point[1])) for point in quad)
        for quad in quads
    )


@lru_cache(maxsize=1)
def _letter_reference_height() -> float:
    from matplotlib.textpath import TextPath

    path = TextPath((0.0, 0.0), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=1.0)
    vertices = path.vertices
    if len(vertices) == 0:
        return 1.0
    return max(float(point[1]) for point in vertices) - min(
        float(point[1]) for point in vertices
    )


def _node_colors_2d(
    rows: Sequence[dict[str, object]],
    tile_colors: Mapping[Coord, str],
) -> list[str]:
    return [tile_colors.get(row["coord"], BASE_TILE) for row in rows]


def _placement_colors(coords: Iterable[Coord]) -> dict[Coord, str]:
    return {coord: NEW_MOVE_TILE for coord in coords}


def _color_to_rgb(color: str) -> tuple[int, int, int]:
    if color.startswith("#"):
        return _hex_to_rgb(color)
    if color.startswith("rgb(") and color.endswith(")"):
        return tuple(  # type: ignore[return-value]
            int(part.strip()) for part in color[4:-1].split(",")
        )
    raise ValueError(f"Unsupported color format: {color}")


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    normalized = color.removeprefix("#")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _axis_values(
    cells: Iterable[tuple[Coord, str]] | Board,
    axes: tuple[int, int],
) -> tuple[list[int], list[int]]:
    occupied = cells.occupied_sorted() if isinstance(cells, Board) else tuple(cells)
    if not occupied:
        return [0], [0]
    x_coords = [coord[axes[0]] for coord, _ in occupied]
    y_coords = [coord[axes[1]] for coord, _ in occupied]
    return (
        list(range(min(x_coords), max(x_coords) + 1)),
        list(range(min(y_coords), max(y_coords) + 1)),
    )


def _union_board_extent(boards: Sequence[Board]) -> Board:
    cells: dict[Coord, str] = {}
    for board in boards:
        cells.update(board.cells)
    dimensions = boards[0].dimensions if boards else 2
    return Board(dimensions=dimensions, cells=cells, segments=())


def _projected_rows(
    board: Board,
    axes: tuple[int, int],
    plane_coords: Mapping[int, int],
) -> list[dict[str, object]]:
    rows = []
    for coord, symbol in _plane_cells(board, plane_coords):
        rows.append(
            {
                "coord": coord,
                "symbol": symbol,
                "axes_at": board.axes_at(coord),
                "x": coord[axes[0]],
                "y": coord[axes[1]],
            }
        )
    return rows


def _validate_plane(
    board: Board,
    axes: tuple[int, int],
    plane_coords: Mapping[int, int],
) -> None:
    if axes[0] == axes[1] or any(axis < 0 or axis >= board.dimensions for axis in axes):
        raise ValueError("Plane axes must be distinct valid board dimensions.")
    hidden_axes = set(range(board.dimensions)) - set(axes)
    if set(plane_coords) != hidden_axes:
        raise ValueError("Plane coordinates must define every non-visible axis.")
    if any(not isinstance(value, int) for value in plane_coords.values()):
        raise ValueError("Plane coordinates must be integers.")


def _plane_cells(
    board: Board,
    plane_coords: Mapping[int, int],
) -> tuple[tuple[Coord, str], ...]:
    return tuple(
        (coord, symbol)
        for coord, symbol in board.occupied_sorted()
        if all(coord[axis] == value for axis, value in plane_coords.items())
    )


def _plane_extent(board: Board, plane_coords: Mapping[int, int]) -> Board:
    return Board(
        dimensions=board.dimensions,
        cells=dict(_plane_cells(board, plane_coords)),
        segments=(),
    )


def _require_2d_board(board: Board) -> None:
    if board.dimensions != 2:
        raise ValueError("Scenario animation requires a two-dimensional board.")


def _bounds(
    board: Board,
    axes: Sequence[int],
    *,
    pad: float = 0.75,
) -> tuple[float, float, float, float]:
    if not board.cells:
        return -1.0, 1.0, -1.0, 1.0
    xs = [coord[axes[0]] for coord in board.cells]
    ys = [coord[axes[1]] for coord in board.cells]
    return min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad


def _plot_size_2d(board: Board, axes: tuple[int, int]) -> tuple[int, int]:
    x_values, y_values = _axis_values(board, axes)
    width = _clamp(len(x_values) * CELL_SIZE_2D, MIN_PLOT_SIZE_2D, MAX_PLOT_SIZE_2D)
    height = _clamp(len(y_values) * CELL_SIZE_2D, MIN_PLOT_SIZE_2D, MAX_PLOT_SIZE_2D)
    return width, height


def _marker_size_2d(board: Board, axes: tuple[int, int]) -> int:
    x_values, y_values = _axis_values(board, axes)
    width, height = _plot_size_2d(board, axes)
    tile_size = min(width / len(x_values), height / len(y_values))
    return _clamp(
        round(tile_size - TILE_GAP * 2),
        NODE_MARKER_MIN_SIZE_2D,
        NODE_MARKER_MAX_SIZE_2D,
    )


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _style_plotly_xy(
    fig: object,
    board: Board,
    axes: tuple[int, int],
    title: str | None,
) -> None:
    xmin, xmax, ymin, ymax = _bounds(board, axes, pad=PLOT_PAD_2D)
    width, height = _plot_size_2d(board, axes)
    fig.update_layout(
        xaxis={
            "range": [xmin, xmax],
            "visible": False,
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "scaleanchor": "y",
            "scaleratio": 1,
        },
        yaxis={
            "range": [ymin, ymax],
            "visible": False,
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
        },
        margin={
            "l": PLOT_MARGIN,
            "r": PLOT_MARGIN,
            "t": 36 if title else PLOT_MARGIN,
            "b": PLOT_MARGIN,
        },
        width=width,
        height=height + (32 if title else 0),
        paper_bgcolor="white",
        plot_bgcolor=TRANSPARENT_COLOR,
        showlegend=False,
        dragmode="pan",
        title=title,
    )
