from __future__ import annotations

import base64
import html
import io
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Literal, Mapping, Sequence

from src.domain.board import Board
from src.domain.models import Coord
from src.generator.reconstruction import reconstruct_boards

BASE_TILE = "#f7f8fa"
BOARD_GAP = "#d1d1d1"
TEXT_COLOR = "#15181d"
TEXT_FONT_FAMILY = "DejaVu Sans Mono, Menlo, Consolas, monospace"
HIGHLIGHT_TILE = "#ff00b8"
PLOT_MARGIN = 4
PLOT_PAD_2D = 0.53
TILE_GAP = 2
CELL_SIZE_2D = 58
MIN_LETTER_SIZE_2D = 6
MAX_LETTER_SIZE_2D = 24
LETTER_TILE_RATIO_2D = 0.46
LETTER_SCALE_FACTOR_2D = 1.75
MIN_PLOT_SIZE_2D = 180
MAX_PLOT_SIZE_2D = 520
ANIMATION_CONTROLS_HEIGHT = 56
TRANSPARENT_COLOR = "rgba(0, 0, 0, 0)"
NODE_CUBE_SIZE_3D = 0.68
NODE_OPACITY_3D = 1.0
NODE_HEATMAP_3D = (
    (0.0, "#0057d9"),
    (0.45, "#42b6a4"),
    (0.72, "#f2c94c"),
    (1.0, "#e60023"),
)
NODE_FACE_TEXT_OFFSET_3D = NODE_CUBE_SIZE_3D / 2.0 + 0.012
NODE_FACE_TEXT_SIZE_3D = NODE_CUBE_SIZE_3D * 0.55
NODE_FACE_TEXT_FILL_RESOLUTION_3D = 18
NODE_MARKER_TEXT_SIZE_3D = 12
NODE_MARKER_SIZE_3D = 8
NODE_MARKER_TEXT_SIZE_2D = 16
NODE_MARKER_MAX_SIZE_2D = 48
NODE_MARKER_MIN_SIZE_2D = 10
CAMERA_EYE_3D = (1.55, -1.75, 1.25)
CAMERA_ZOOM_3D = 2.6
LETTER_RASTER_SIZE_2D = 0.54
LETTER_RASTER_RESOLUTION_2D = 18
IMAGE_CELL_PIXELS_2D = 42
IMAGE_TILE_GAP_PIXELS_2D = 2
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_scenario_path(name_or_path: str | Path) -> Path:
    """Resolve a scenario path or bare scenario name under outputs/scenarios/."""
    path = Path(name_or_path)
    candidates = [path]
    if path.suffix != ".json":
        candidates.append(path.with_suffix(".json"))
    if not path.is_absolute() and path.parent == Path("."):
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


def default_visible_axes(dimensions: int) -> tuple[int, ...]:
    """Choose a default 2D/3D projection for a board dimension count."""
    if dimensions < 2:
        raise ValueError("Visualization requires at least two board dimensions.")
    return tuple(range(min(dimensions, 3)))


def default_slice_coords(
    dimensions: int,
    visible_axes: Sequence[int],
    overrides: Mapping[int, int] | None = None,
) -> dict[int, int]:
    """Default hidden dimensions to coordinate 0, with optional overrides."""
    hidden_axes = set(range(dimensions)) - set(visible_axes)
    resolved = {axis: 0 for axis in hidden_axes}
    resolved.update(overrides or {})
    return resolved


def plot_board_projected(
    board: Board,
    *,
    highlight_coords: Iterable[Coord] = (),
    title: str | None = None,
    visible_axes: Sequence[int] | None = None,
    slice_coords: Mapping[int, int] | None = None,
    node_shape: Literal["cube", "marker"] = "cube",
    label_mode: Literal["mesh", "billboard", "none"] = "mesh",
    camera_zoom: float = CAMERA_ZOOM_3D,
) -> object:
    """Plot a board through a 2D or 3D projection.

    Hidden dimensions default to coordinate 0 and can be overridden through
    ``slice_coords``.
    """
    axes = tuple(visible_axes or default_visible_axes(board.dimensions))
    resolved_slice = default_slice_coords(board.dimensions, axes, slice_coords)
    if len(axes) == 2:
        return plot_board_2d(
            board,
            highlight_coords=highlight_coords,
            title=title,
            axes=(axes[0], axes[1]),
            slice_coords=resolved_slice,
        )
    if len(axes) == 3:
        return plot_board_3d(
            board,
            highlight_coords=highlight_coords,
            title=title,
            axes=(axes[0], axes[1], axes[2]),
            slice_coords=resolved_slice,
            node_shape=node_shape,
            label_mode=label_mode,
            camera_zoom=camera_zoom,
        )
    raise ValueError("visible_axes must select exactly two or three axes.")


def animate_scenario_projected(
    scenario: Mapping[str, object],
    *,
    title: str | None = None,
    visible_axes: Sequence[int] | None = None,
    slice_coords: Mapping[int, int] | None = None,
    node_shape: Literal["cube", "marker"] = "marker",
    label_mode: Literal["mesh", "billboard", "none"] = "billboard",
    camera_zoom: float = CAMERA_ZOOM_3D,
) -> object:
    """Animate a scenario through a 2D or 3D projection."""
    boards, _placements = scenario_boards_and_placements(scenario)
    axes = tuple(visible_axes or default_visible_axes(boards[0].dimensions))
    resolved_slice = default_slice_coords(boards[0].dimensions, axes, slice_coords)
    if len(axes) == 2:
        return animate_scenario_2d(
            scenario,
            title=title,
            axes=(axes[0], axes[1]),
            slice_coords=resolved_slice,
        )
    if len(axes) == 3:
        return animate_scenario_3d(
            scenario,
            title=title,
            axes=(axes[0], axes[1], axes[2]),
            slice_coords=resolved_slice,
            node_shape=node_shape,
            label_mode=label_mode,
            camera_zoom=camera_zoom,
        )
    raise ValueError("visible_axes must select exactly two or three axes.")


def scenario_boards_and_placements(
    scenario: Mapping[str, object],
) -> tuple[tuple[Board, ...], tuple[frozenset[Coord], ...]]:
    """Reconstruct every board and the cells newly placed at each step."""
    boards = reconstruct_boards(dict(scenario))
    placements: list[frozenset[Coord]] = [frozenset()]
    for transition in scenario.get("transitions", []):
        placed = transition["placed"]  # type: ignore[index]
        placements.append(frozenset(tuple(int(value) for value in coord) for coord, _ in placed))
    return boards, tuple(placements)


def plot_board_2d(
    board: Board,
    *,
    highlight_coords: Iterable[Coord] = (),
    title: str | None = None,
    axes: tuple[int, int] = (0, 1),
    slice_coords: Mapping[int, int] | None = None,
) -> object:
    """Create an interactive Plotly 2D slice of a sparse board."""
    if board.dimensions < 2:
        raise ValueError("2D plotting requires at least two board dimensions.")
    import plotly.graph_objects as go

    resolved_slice = _resolve_slice_coords(board, axes, slice_coords)
    extent_board = _slice_extent(board, resolved_slice)
    fig = go.Figure(
        data=_board_2d_traces(
            board,
            highlight_coords=highlight_coords,
            axes=axes,
            slice_coords=resolved_slice,
        )
    )
    _style_plotly_xy(fig, extent_board, axes, title)
    return fig


def plot_board_3d(
    board: Board,
    *,
    highlight_coords: Iterable[Coord] = (),
    title: str | None = None,
    axes: tuple[int, int, int] = (0, 1, 2),
    slice_coords: Mapping[int, int] | None = None,
    node_shape: Literal["cube", "marker"] = "cube",
    node_opacity: float = NODE_OPACITY_3D,
    label_mode: Literal["mesh", "billboard", "none"] = "mesh",
    camera_zoom: float = CAMERA_ZOOM_3D,
) -> object:
    """Create an interactive Plotly 3D slice of a sparse board."""
    if board.dimensions < 3:
        raise ValueError("3D plotting requires at least three board dimensions.")
    import plotly.graph_objects as go

    resolved_slice = _resolve_slice_coords(board, axes, slice_coords)
    fig = go.Figure(
        data=_board_3d_traces(
            board,
            highlight_coords=highlight_coords,
            axes=axes,
            slice_coords=resolved_slice,
            node_shape=node_shape,
            node_opacity=node_opacity,
            label_mode=label_mode,
        )
    )
    _style_plotly_3d(
        fig,
        _slice_extent(board, resolved_slice),
        axes,
        title,
        camera_zoom=camera_zoom,
    )
    return fig


def animate_scenario_3d(
    scenario: Mapping[str, object],
    *,
    title: str | None = None,
    axes: tuple[int, int, int] = (0, 1, 2),
    slice_coords: Mapping[int, int] | None = None,
    node_shape: Literal["cube", "marker"] = "marker",
    node_opacity: float = NODE_OPACITY_3D,
    label_mode: Literal["mesh", "billboard", "none"] = "billboard",
    camera_zoom: float = CAMERA_ZOOM_3D,
) -> object:
    """Create an interactive Plotly slider over one 3D scenario slice."""
    import plotly.graph_objects as go

    boards, placements = scenario_boards_and_placements(scenario)
    resolved_slice = _resolve_slice_coords(boards[0], axes, slice_coords)
    range_board = _slice_extent(_union_board_extent(boards), resolved_slice)
    heat_origins = tuple(
        coord for coord, _symbol in _visible_cells(boards[0], resolved_slice)
    )
    base_fig = go.Figure(
        data=_board_3d_traces(
            boards[0],
            highlight_coords=placements[0],
            axes=axes,
            slice_coords=resolved_slice,
            node_shape=node_shape,
            node_opacity=node_opacity,
            heat_origin_coords=heat_origins,
            heat_bounds_board=range_board,
            label_mode=label_mode,
        )
    )
    _style_plotly_3d(
        base_fig,
        range_board,
        axes,
        title,
        bottom_margin=36,
        camera_zoom=camera_zoom,
    )
    frames = []
    for index, (board, placed) in enumerate(zip(boards, placements, strict=True)):
        frames.append(
            go.Frame(
                data=_board_3d_traces(
                    board,
                    highlight_coords=placed,
                    axes=axes,
                    slice_coords=resolved_slice,
                    node_shape=node_shape,
                    node_opacity=node_opacity,
                    heat_origin_coords=heat_origins,
                    heat_bounds_board=range_board,
                    label_mode=label_mode,
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
    )
    return base_fig


def animate_scenario_2d(
    scenario: Mapping[str, object],
    *,
    title: str | None = None,
    axes: tuple[int, int] = (0, 1),
    slice_coords: Mapping[int, int] | None = None,
) -> object:
    """Create an interactive Plotly slider over one 2D scenario slice."""
    import plotly.graph_objects as go

    boards, placements = scenario_boards_and_placements(scenario)
    resolved_slice = _resolve_slice_coords(boards[0], axes, slice_coords)
    range_board = _slice_extent(_union_board_extent(boards), resolved_slice)
    base_fig = go.Figure(
        data=_board_2d_traces(
            boards[0],
            highlight_coords=placements[0],
            axes=axes,
            slice_coords=resolved_slice,
            heat_bounds_board=range_board,
        )
    )
    _style_plotly_xy(base_fig, range_board, axes, title)
    frames = []
    for index, (board, placed) in enumerate(zip(boards, placements, strict=True)):
        frames.append(
            go.Frame(
                data=_board_2d_traces(
                    board,
                    highlight_coords=placed,
                    axes=axes,
                    slice_coords=resolved_slice,
                    heat_bounds_board=range_board,
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
    axes: tuple[int, int] = (0, 1),
    slice_coords: Mapping[int, int] | None = None,
    cell_pixels: int = IMAGE_CELL_PIXELS_2D,
) -> object:
    """Create a fast Plotly slider that swaps pre-rendered 2D PNG frames."""
    import plotly.graph_objects as go

    boards, placements = scenario_boards_and_placements(scenario)
    resolved_slice = _resolve_slice_coords(boards[0], axes, slice_coords)
    range_board = _slice_extent(_union_board_extent(boards), resolved_slice)
    base_source = _board_png_source_2d(
        boards[0],
        highlight_coords=placements[0],
        axes=axes,
        slice_coords=resolved_slice,
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
                            highlight_coords=placed,
                            axes=axes,
                            slice_coords=resolved_slice,
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
    axes: tuple[int, int] = (0, 1),
    slice_coords: Mapping[int, int] | None = None,
    cell_pixels: int = IMAGE_CELL_PIXELS_2D,
) -> object:
    """Create a preloaded canvas slider for smooth large 2D animations."""
    boards, placements = scenario_boards_and_placements(scenario)
    resolved_slice = _resolve_slice_coords(boards[0], axes, slice_coords)
    range_board = _slice_extent(_union_board_extent(boards), resolved_slice)
    frames = [
        _board_png_source_2d(
            board,
            highlight_coords=placed,
            axes=axes,
            slice_coords=resolved_slice,
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
    highlight_coords: Iterable[Coord],
    axes: tuple[int, int],
    slice_coords: Mapping[int, int],
    heat_bounds_board: Board | None = None,
) -> list[object]:
    return [
        _board_marker_trace_2d(
            board,
            highlight_coords=highlight_coords,
            axes=axes,
            slice_coords=slice_coords,
            heat_bounds_board=heat_bounds_board,
        )
    ]


def _board_marker_trace_2d(
    board: Board,
    *,
    highlight_coords: Iterable[Coord],
    axes: tuple[int, int],
    slice_coords: Mapping[int, int],
    heat_bounds_board: Board | None = None,
) -> object:
    import plotly.graph_objects as go

    rows = _projected_rows(board, axes, slice_coords)
    highlight = set(highlight_coords)
    bounds_board = heat_bounds_board or board
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
            "color": _node_colors_2d(rows, highlight),
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


def _letter_raster_trace_2d(
    board: Board,
    *,
    axes: tuple[int, int],
    slice_coords: Mapping[int, int],
) -> object:
    import plotly.graph_objects as go

    x: list[float | None] = []
    y: list[float | None] = []
    for coord, symbol in _visible_cells(board, slice_coords):
        cell_x, cell_y = _letter_raster_points_2d(coord, symbol, axes)
        x.extend(cell_x)
        y.extend(cell_y)

    return go.Scatter(
        x=x,
        y=y,
        mode="lines",
        fill="toself",
        fillcolor=TEXT_COLOR,
        line={"color": TEXT_COLOR, "width": 0},
        hoverinfo="skip",
        showlegend=False,
    )


def _letter_raster_trace_for_cell_2d(
    coord: Coord,
    symbol: str,
    *,
    axes: tuple[int, int],
    visible: bool,
) -> object:
    import plotly.graph_objects as go

    x, y = _letter_raster_points_2d(coord, symbol, axes)
    return go.Scatter(
        x=x,
        y=y,
        mode="lines",
        fill="toself",
        fillcolor=TEXT_COLOR,
        line={"color": TEXT_COLOR, "width": 0},
        hoverinfo="skip",
        showlegend=False,
        visible=visible,
    )


def _letter_raster_points_2d(
    coord: Coord,
    symbol: str,
    axes: tuple[int, int],
) -> tuple[list[float | None], list[float | None]]:
    x: list[float | None] = []
    y: list[float | None] = []
    center_x = float(coord[axes[0]])
    center_y = float(coord[axes[1]])
    for quad in _letter_fill_quads(
        str(symbol),
        LETTER_RASTER_SIZE_2D,
        LETTER_RASTER_RESOLUTION_2D,
    ):
        for px, py in (*quad, quad[0]):
            x.append(center_x + px)
            y.append(center_y + py)
        x.append(None)
        y.append(None)
    return x, y


def _board_png_source_2d(
    board: Board,
    *,
    highlight_coords: Iterable[Coord],
    axes: tuple[int, int],
    slice_coords: Mapping[int, int],
    range_board: Board,
    cell_pixels: int,
) -> str:
    import numpy as np
    from PIL import Image

    visible_cells = _visible_cells(board, slice_coords)
    x_values, y_values = _axis_values(range_board, axes)
    width = len(x_values) * cell_pixels
    height = len(y_values) * cell_pixels
    image = np.zeros((height, width, 4), dtype=np.uint8)
    x_index = {value: index for index, value in enumerate(x_values)}
    y_index = {value: index for index, value in enumerate(reversed(y_values))}
    highlight = set(highlight_coords)
    gap = min(IMAGE_TILE_GAP_PIXELS_2D, max(cell_pixels // 6, 1))
    for coord, symbol in visible_cells:
        left = x_index[coord[axes[0]]] * cell_pixels + gap
        top = y_index[coord[axes[1]]] * cell_pixels + gap
        right = (x_index[coord[axes[0]]] + 1) * cell_pixels - gap
        bottom = (y_index[coord[axes[1]]] + 1) * cell_pixels - gap
        color = _color_to_rgb(HIGHLIGHT_TILE if coord in highlight else BASE_TILE)
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


def _board_3d_traces(
    board: Board,
    *,
    highlight_coords: Iterable[Coord],
    axes: tuple[int, int, int],
    slice_coords: Mapping[int, int],
    node_shape: Literal["cube", "marker"],
    node_opacity: float,
    heat_origin_coords: Sequence[Coord] = (),
    heat_bounds_board: Board | None = None,
    label_mode: Literal["mesh", "billboard", "none"] = "mesh",
) -> list[object]:
    import plotly.graph_objects as go

    rows = _projected_rows(board, axes, slice_coords)
    highlight = set(highlight_coords)
    node_opacity = _clamp_float(node_opacity, 0.0, 1.0)
    heat_values = _generation_heat_values_3d(
        rows,
        origins=heat_origin_coords,
        bounds_board=heat_bounds_board or board,
        axes=axes,
    )
    node_colors = _node_colors_3d(rows, heat_values, highlight)
    if node_shape == "cube":
        traces = [_cube_mesh_trace_3d(rows, node_colors, node_opacity)]
        if label_mode == "mesh":
            traces.append(_node_face_letter_mesh_trace_3d(rows))
        elif label_mode == "billboard":
            traces.append(_node_billboard_text_trace_3d(rows))
        elif label_mode != "none":
            raise ValueError("label_mode must be 'mesh', 'billboard', or 'none'.")
        traces.append(_node_hover_trace_3d(rows))
        return traces
    if node_shape == "marker":
        return [
            go.Scatter3d(
                x=[row["x"] for row in rows],
                y=[row["y"] for row in rows],
                z=[row["z"] for row in rows],
                mode="markers+text",
                marker={
                    "size": NODE_MARKER_SIZE_3D,
                    "color": node_colors,
                    "opacity": node_opacity,
                    "symbol": "square",
                },
                text=[row["symbol"] for row in rows],
                textfont={
                    "color": TEXT_COLOR,
                    "size": NODE_MARKER_TEXT_SIZE_3D,
                    "family": TEXT_FONT_FAMILY,
                },
                textposition="middle center",
                customdata=[list(row["coord"]) for row in rows],
                hovertemplate="coord=%{customdata}<br>symbol=%{text}<extra></extra>",
                showlegend=False,
            )
        ]
    raise ValueError("node_shape must be either 'cube' or 'marker'.")


def _cube_mesh_trace_3d(
    rows: Sequence[dict[str, object]],
    colors: Sequence[str],
    opacity: float,
) -> object:
    import plotly.graph_objects as go

    x: list[float] = []
    y: list[float] = []
    z: list[float] = []
    i: list[int] = []
    j: list[int] = []
    k: list[int] = []
    facecolor: list[str] = []
    half = NODE_CUBE_SIZE_3D / 2.0

    vertex_offsets = (
        (-half, -half, -half),
        (half, -half, -half),
        (half, half, -half),
        (-half, half, -half),
        (-half, -half, half),
        (half, -half, half),
        (half, half, half),
        (-half, half, half),
    )
    triangles = (
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (1, 5, 6),
        (1, 6, 2),
        (2, 6, 7),
        (2, 7, 3),
        (3, 7, 4),
        (3, 4, 0),
    )

    for row, color in zip(rows, colors, strict=True):
        base = len(x)
        cx = float(row["x"])
        cy = float(row["y"])
        cz = float(row["z"])
        for dx, dy, dz in vertex_offsets:
            x.append(cx + dx)
            y.append(cy + dy)
            z.append(cz + dz)
        for a, b, c in triangles:
            i.append(base + a)
            j.append(base + b)
            k.append(base + c)
            facecolor.append(color)

    return go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        facecolor=facecolor,
        opacity=opacity,
        flatshading=True,
        lighting={
            "ambient": 0.72,
            "diffuse": 0.55,
            "specular": 0.08,
            "roughness": 0.85,
        },
        hoverinfo="skip",
        showscale=False,
        showlegend=False,
    )


def _node_face_letter_mesh_trace_3d(rows: Sequence[dict[str, object]]) -> object:
    import plotly.graph_objects as go

    x: list[float] = []
    y: list[float] = []
    z: list[float] = []
    i: list[int] = []
    j: list[int] = []
    k: list[int] = []
    face_bases = (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
    )
    for row in rows:
        center = (float(row["x"]), float(row["y"]), float(row["z"]))
        quads = _letter_fill_quads(
            str(row["symbol"]),
            NODE_FACE_TEXT_SIZE_3D,
            NODE_FACE_TEXT_FILL_RESOLUTION_3D,
        )
        for normal, u_axis, v_axis in face_bases:
            face_center = _add_3d(center, _scale_3d(normal, NODE_FACE_TEXT_OFFSET_3D))
            for quad in quads:
                base = len(x)
                for px, py in quad:
                    point = _add_3d(
                        face_center,
                        _add_3d(_scale_3d(u_axis, px), _scale_3d(v_axis, py)),
                    )
                    x.append(point[0])
                    y.append(point[1])
                    z.append(point[2])
                i.extend((base, base, base + 2, base + 3))
                j.extend((base + 1, base + 2, base + 1, base + 2))
                k.extend((base + 2, base + 3, base, base))

    return go.Mesh3d(
        x=x,
        y=y,
        z=z,
        i=i,
        j=j,
        k=k,
        color=TEXT_COLOR,
        opacity=1.0,
        flatshading=True,
        hoverinfo="skip",
        showscale=False,
        showlegend=False,
    )


def _node_billboard_text_trace_3d(rows: Sequence[dict[str, object]]) -> object:
    import plotly.graph_objects as go

    return go.Scatter3d(
        x=[row["x"] for row in rows],
        y=[row["y"] for row in rows],
        z=[row["z"] for row in rows],
        mode="text",
        text=[row["symbol"] for row in rows],
        textfont={
            "color": TEXT_COLOR,
            "size": NODE_MARKER_TEXT_SIZE_3D,
            "family": TEXT_FONT_FAMILY,
        },
        textposition="middle center",
        hoverinfo="skip",
        showlegend=False,
    )


def _node_hover_trace_3d(rows: Sequence[dict[str, object]]) -> object:
    import plotly.graph_objects as go

    return go.Scatter3d(
        x=[row["x"] for row in rows],
        y=[row["y"] for row in rows],
        z=[row["z"] for row in rows],
        mode="markers",
        marker={"size": 12, "color": TRANSPARENT_COLOR, "opacity": 0.0},
        text=[row["symbol"] for row in rows],
        customdata=[list(row["coord"]) for row in rows],
        hovertemplate="coord=%{customdata}<br>symbol=%{text}<extra></extra>",
        showlegend=False,
    )


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


def _add_3d(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        first[0] + second[0],
        first[1] + second[1],
        first[2] + second[2],
    )


def _scale_3d(
    vector: tuple[float, float, float],
    scale: float,
) -> tuple[float, float, float]:
    return (vector[0] * scale, vector[1] * scale, vector[2] * scale)


def _node_colors_3d(
    rows: Sequence[dict[str, object]],
    heat_values: Sequence[float],
    highlight: set[Coord],
) -> list[str]:
    return [
        HIGHLIGHT_TILE if row["coord"] in highlight else _heatmap_color_3d(value)
        for row, value in zip(rows, heat_values, strict=True)
    ]


def _node_colors_2d(
    rows: Sequence[dict[str, object]],
    highlight: set[Coord],
) -> list[str]:
    return [
        HIGHLIGHT_TILE if row["coord"] in highlight else BASE_TILE
        for row in rows
    ]


def _generation_heat_values_3d(
    rows: Sequence[dict[str, object]],
    *,
    origins: Sequence[Coord],
    bounds_board: Board,
    axes: tuple[int, int, int],
) -> list[float]:
    if not origins:
        return _center_heat_values_3d(rows)
    bounds = _bounds_3d(bounds_board, axes, pad=0.0)
    projected_origins = [
        (float(coord[axes[0]]), float(coord[axes[1]]), float(coord[axes[2]]))
        for coord in origins
    ]
    return [
        _edge_weighted_heat(
            (float(row["x"]), float(row["y"]), float(row["z"])),
            projected_origins,
            ((bounds[0], bounds[1]), (bounds[2], bounds[3]), (bounds[4], bounds[5])),
        )
        for row in rows
    ]


def _edge_weighted_heat(
    point: tuple[float, ...],
    origins: Sequence[tuple[float, ...]],
    bounds: Sequence[tuple[float, float]],
) -> float:
    origin = min(
        origins,
        key=lambda candidate: sum(
            (point[index] - candidate[index]) ** 2 for index in range(len(point))
        ),
    )
    vector = tuple(point[index] - origin[index] for index in range(len(point)))
    distance = sum(component**2 for component in vector) ** 0.5
    if distance == 0:
        return 1.0
    direction = tuple(component / distance for component in vector)
    edge_distance = min(
        (
            ((upper - origin[index]) / direction[index])
            if direction[index] > 0
            else ((lower - origin[index]) / direction[index])
        )
        for index, (lower, upper) in enumerate(bounds)
        if direction[index] != 0
    )
    if edge_distance <= 0:
        return 0.0
    return _clamp_float(1.0 - distance / edge_distance, 0.0, 1.0)


def _center_heat_values_3d(rows: Sequence[dict[str, object]]) -> list[float]:
    if not rows:
        return []
    xs = [float(row["x"]) for row in rows]
    ys = [float(row["y"]) for row in rows]
    zs = [float(row["z"]) for row in rows]
    center = (
        (min(xs) + max(xs)) / 2.0,
        (min(ys) + max(ys)) / 2.0,
        (min(zs) + max(zs)) / 2.0,
    )
    distances = [
        (
            (float(row["x"]) - center[0]) ** 2
            + (float(row["y"]) - center[1]) ** 2
            + (float(row["z"]) - center[2]) ** 2
        )
        ** 0.5
        for row in rows
    ]
    max_distance = max(distances)
    if max_distance == 0:
        return [1.0 for _ in rows]
    return [1.0 - distance / max_distance for distance in distances]


def _heatmap_color_3d(value: float) -> str:
    value = _clamp_float(value, 0.0, 1.0)
    for index, (stop, color) in enumerate(NODE_HEATMAP_3D):
        if value <= stop:
            if index == 0 or abs(value - stop) < 1e-9:
                return color
            prev_stop, prev_color = NODE_HEATMAP_3D[index - 1]
            local = (value - prev_stop) / (stop - prev_stop)
            return _interpolate_hex_color(prev_color, color, local)
    return NODE_HEATMAP_3D[-1][1]


def _interpolate_hex_color(start: str, end: str, value: float) -> str:
    start_rgb = _hex_to_rgb(start)
    end_rgb = _hex_to_rgb(end)
    rgb = _interpolate_rgb(start_rgb, end_rgb, value)
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"


def _interpolate_rgb(
    start_rgb: tuple[int, int, int],
    end_rgb: tuple[int, int, int],
    value: float,
) -> tuple[int, int, int]:
    return tuple(
        round(start_part + (end_part - start_part) * value)
        for start_part, end_part in zip(start_rgb, end_rgb, strict=True)
    )


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
    axes: Sequence[int],
    slice_coords: Mapping[int, int],
) -> list[dict[str, object]]:
    rows = []
    for coord, symbol in _visible_cells(board, slice_coords):
        row = {
            "coord": coord,
            "symbol": symbol,
            "axes_at": board.axes_at(coord),
            "x": coord[axes[0]],
            "y": coord[axes[1]],
        }
        if len(axes) == 3:
            row["z"] = coord[axes[2]]
        rows.append(row)
    return rows


def _resolve_slice_coords(
    board: Board,
    axes: Sequence[int],
    slice_coords: Mapping[int, int] | None,
) -> dict[int, int]:
    if len(set(axes)) != len(axes) or any(
        axis < 0 or axis >= board.dimensions for axis in axes
    ):
        raise ValueError("Visible axes must be distinct valid board dimensions.")
    hidden_axes = set(range(board.dimensions)) - set(axes)
    resolved = dict(slice_coords or {})
    unknown_axes = set(resolved) - hidden_axes
    if unknown_axes:
        raise ValueError(
            f"slice_coords may contain only hidden axes; got {sorted(unknown_axes)}."
        )
    missing_axes = hidden_axes - set(resolved)
    if missing_axes:
        raise ValueError(
            "Visualization requires slice_coords for every hidden axis; "
            f"missing {sorted(missing_axes)}."
        )
    if any(not isinstance(value, int) for value in resolved.values()):
        raise ValueError("slice_coords values must be integer coordinates.")
    return resolved


def _visible_cells(
    board: Board,
    slice_coords: Mapping[int, int],
) -> tuple[tuple[Coord, str], ...]:
    return tuple(
        (coord, symbol)
        for coord, symbol in board.occupied_sorted()
        if all(coord[axis] == value for axis, value in slice_coords.items())
    )


def _slice_extent(board: Board, slice_coords: Mapping[int, int]) -> Board:
    return Board(
        dimensions=board.dimensions,
        cells=dict(_visible_cells(board, slice_coords)),
        segments=(),
    )


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


def _bounds_3d(
    board: Board,
    axes: tuple[int, int, int],
    *,
    pad: float = 1.0,
) -> tuple[float, float, float, float, float, float]:
    if not board.cells:
        return -1.0, 1.0, -1.0, 1.0, -1.0, 1.0
    xs = [coord[axes[0]] for coord in board.cells]
    ys = [coord[axes[1]] for coord in board.cells]
    zs = [coord[axes[2]] for coord in board.cells]
    return (
        min(xs) - pad,
        max(xs) + pad,
        min(ys) - pad,
        max(ys) + pad,
        min(zs) - pad,
        max(zs) + pad,
    )


def _aspectratio_3d(
    bounds: tuple[float, float, float, float, float, float],
) -> dict[str, float]:
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    return {
        "x": max(xmax - xmin, 1.0),
        "y": max(ymax - ymin, 1.0),
        "z": max(zmax - zmin, 1.0),
    }


def _plot_size_2d(board: Board, axes: tuple[int, int]) -> tuple[int, int]:
    x_values, y_values = _axis_values(board, axes)
    width = _clamp(len(x_values) * CELL_SIZE_2D, MIN_PLOT_SIZE_2D, MAX_PLOT_SIZE_2D)
    height = _clamp(len(y_values) * CELL_SIZE_2D, MIN_PLOT_SIZE_2D, MAX_PLOT_SIZE_2D)
    return width, height


def _letter_size_2d(board: Board, axes: tuple[int, int]) -> int:
    x_values, y_values = _axis_values(board, axes)
    width, height = _plot_size_2d(board, axes)
    tile_size = min(width / len(x_values), height / len(y_values))
    usable_tile_size = max(tile_size - TILE_GAP, 1)
    return _clamp(
        round(usable_tile_size * LETTER_TILE_RATIO_2D * LETTER_SCALE_FACTOR_2D),
        MIN_LETTER_SIZE_2D,
        MAX_LETTER_SIZE_2D,
    )


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


def _clamp_float(value: float, lower: float, upper: float) -> float:
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
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": PLOT_MARGIN},
        width=width,
        height=height,
        paper_bgcolor="white",
        plot_bgcolor=TRANSPARENT_COLOR,
        showlegend=False,
        dragmode="pan",
    )


def _style_plotly_3d(
    fig: object,
    board: Board,
    axes: tuple[int, int, int],
    title: str | None,
    *,
    bottom_margin: int = PLOT_MARGIN,
    camera_zoom: float = CAMERA_ZOOM_3D,
) -> None:
    bounds = _bounds_3d(board, axes)
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    fig.update_layout(
        scene={
            "xaxis": {
                "range": [xmin, xmax],
                "visible": False,
                "showbackground": False,
                "showgrid": False,
                "zeroline": False,
            },
            "yaxis": {
                "range": [ymin, ymax],
                "visible": False,
                "showbackground": False,
                "showgrid": False,
                "zeroline": False,
            },
            "zaxis": {
                "range": [zmin, zmax],
                "visible": False,
                "showbackground": False,
                "showgrid": False,
                "zeroline": False,
            },
            "aspectmode": "manual",
            "aspectratio": _aspectratio_3d(bounds),
            "camera": {"eye": _camera_eye_3d(camera_zoom)},
        },
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": bottom_margin},
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        title=title,
    )


def _camera_eye_3d(camera_zoom: float) -> dict[str, float]:
    zoom = _clamp_float(camera_zoom, 0.2, 10.0)
    return {
        "x": CAMERA_EYE_3D[0] * zoom,
        "y": CAMERA_EYE_3D[1] * zoom,
        "z": CAMERA_EYE_3D[2] * zoom,
    }
