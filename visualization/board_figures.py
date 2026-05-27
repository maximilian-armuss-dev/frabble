from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from src.domain.board import Board
from src.domain.models import Coord
from src.generator.reconstruction import reconstruct_boards

BASE_TILE = "#f7f8fa"
BOARD_GAP = "#d1d1d1"
TEXT_COLOR = "#15181d"
HIGHLIGHT_TILE = "#77adff"
HIGHLIGHT_EDGE = "#7f8185"
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


def load_scenario_json(path: str | Path) -> dict[str, object]:
    """Load a generator scenario JSON file."""
    with Path(path).open(encoding="utf-8") as file:
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
    fig = go.Figure()
    fig.add_trace(
        _board_heatmap_trace(
            board,
            highlight_coords=highlight_coords,
            axes=axes,
            slice_coords=resolved_slice,
            letter_size=_letter_size_2d(extent_board, axes),
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
) -> object:
    """Create an interactive Plotly 3D slice of a sparse board."""
    if board.dimensions < 3:
        raise ValueError("3D plotting requires at least three board dimensions.")
    import plotly.graph_objects as go

    resolved_slice = _resolve_slice_coords(board, axes, slice_coords)
    highlight = set(highlight_coords)
    rows = _projected_rows(board, axes, resolved_slice)
    marker_colors = [
        HIGHLIGHT_EDGE if row["coord"] in highlight else "#6b7280"
        for row in rows
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter3d(
            x=[row["x"] for row in rows],
            y=[row["y"] for row in rows],
            z=[row["z"] for row in rows],
            mode="markers+text",
            marker={"size": 8, "color": marker_colors, "opacity": 0.95},
            text=[row["symbol"] for row in rows],
            textfont={"color": TEXT_COLOR, "size": 12},
            textposition="middle center",
            customdata=[list(row["coord"]) for row in rows],
            hovertemplate="coord=%{customdata}<br>symbol=%{text}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        scene={
            "xaxis": {"visible": False, "showbackground": False, "showgrid": False, "zeroline": False},
            "yaxis": {"visible": False, "showbackground": False, "showgrid": False, "zeroline": False},
            "zaxis": {"visible": False, "showbackground": False, "showgrid": False, "zeroline": False},
            "aspectmode": "data",
            "camera": {"eye": {"x": 1.55, "y": -1.75, "z": 1.25}},
        },
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": PLOT_MARGIN},
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig


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
    letter_size = _letter_size_2d(range_board, axes)
    base_fig = go.Figure()
    base_fig.add_trace(
        _board_heatmap_trace(
            boards[0],
            highlight_coords=placements[0],
            axes=axes,
            slice_coords=resolved_slice,
            letter_size=letter_size,
        )
    )
    _style_plotly_xy(base_fig, range_board, axes, title)
    frames = []
    for index, (board, placed) in enumerate(zip(boards, placements, strict=True)):
        frames.append(
            go.Frame(
                data=[
                    _board_heatmap_trace(
                        board,
                        highlight_coords=placed,
                        axes=axes,
                        slice_coords=resolved_slice,
                        letter_size=letter_size,
                    )
                ],
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
                        "args": [[str(index)], {"mode": "immediate", "frame": {"duration": 0, "redraw": True}}],
                    }
                    for index in range(len(boards))
                ],
            }
        ],
        height=base_fig.layout.height + ANIMATION_CONTROLS_HEIGHT,
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": 36},
    )
    return base_fig


def _board_heatmap_trace(
    board: Board,
    *,
    highlight_coords: Iterable[Coord],
    axes: tuple[int, int],
    slice_coords: Mapping[int, int],
    letter_size: int,
) -> object:
    import plotly.graph_objects as go

    highlight = set(highlight_coords)
    visible_cells = _visible_cells(board, slice_coords)
    x_values, y_values = _axis_values(visible_cells, axes)
    projected_cells: dict[tuple[int, int], tuple[Coord, str]] = {}
    for coord, symbol in visible_cells:
        projected_coord = (coord[axes[0]], coord[axes[1]])
        projected_cells[projected_coord] = (coord, symbol)
    z: list[list[int | None]] = []
    text: list[list[str]] = []
    customdata: list[list[list[object] | None]] = []
    for y in y_values:
        z_row: list[int | None] = []
        text_row: list[str] = []
        custom_row: list[list[object] | None] = []
        for x in x_values:
            cell = projected_cells.get((x, y))
            if cell is None:
                z_row.append(None)
                text_row.append("")
                custom_row.append(None)
                continue
            coord, symbol = cell
            z_row.append(1 if coord in highlight else 0)
            text_row.append(symbol)
            custom_row.append(
                [
                    list(coord),
                    ",".join(str(axis) for axis in sorted(board.axes_at(coord))),
                ]
            )
        z.append(z_row)
        text.append(text_row)
        customdata.append(custom_row)

    return go.Heatmap(
        x=x_values,
        y=y_values,
        z=z,
        text=text,
        customdata=customdata,
        texttemplate="%{text}",
        textfont={"color": TEXT_COLOR, "size": letter_size},
        colorscale=[
            [0.0, BASE_TILE],
            [0.499, BASE_TILE],
            [0.5, HIGHLIGHT_TILE],
            [1.0, HIGHLIGHT_TILE],
        ],
        zmin=0,
        zmax=1,
        xgap=TILE_GAP,
        ygap=TILE_GAP,
        showscale=False,
        hoverongaps=False,
        hovertemplate="coord=%{customdata[0]}<br>symbol=%{text}<br>axes=%{customdata[1]}<extra></extra>",
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


def _bounds(board: Board, axes: Sequence[int], *, pad: float = 0.75) -> tuple[float, float, float, float]:
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
        margin={"l": PLOT_MARGIN, "r": PLOT_MARGIN, "t": PLOT_MARGIN, "b": PLOT_MARGIN},
        width=width,
        height=height,
        paper_bgcolor="white",
        plot_bgcolor=BOARD_GAP,
        showlegend=False,
        dragmode="pan",
    )
