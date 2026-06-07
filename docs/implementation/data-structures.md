# Data Structures

## Board

The board uses a sparse representation. A tensor or dense array is unsuitable for unbounded generation because occupancy is sparse and coordinates may be negative.

```python
Coord = tuple[int, ...]
Symbol = str

cells: dict[Coord, Symbol]
```

V1 requires `dimensions >= 2`.

## Segments

In addition to `cells`, the board stores segments. A segment corresponds to one placed word.

```python
Segment:
    start: Coord
    axis: int
    sequence: tuple[Symbol, ...]
```

Segments support efficient checks for:

- axes on which a coordinate already belongs to a word,
- target axes allowed for a new crossing,
- placements that would extend an existing word on the same axis.

## Indices

Derived indices support efficient generation:

```python
symbol_index: dict[Symbol, set[Coord]]
coord_axes: dict[Coord, set[int]]
coord_segments: dict[Coord, set[SegmentId]]
```

`symbol_index` supports anchor sampling, `coord_axes` crossing-axis selection, and `coord_segments` debugging, validation, and later analysis.

## Board API

`Board` remains small and provides only state and geometric operations needed by the generator and validator.

```python
class Board:
    dimensions: int
    cells: dict[Coord, Symbol]
    segments: tuple[Segment, ...]

    def get(self, coord: Coord) -> Symbol | None: ...
    def coords_for_slot(self, start: Coord, axis: int, length: int) -> tuple[Coord, ...]: ...
    def axes_at(self, coord: Coord) -> set[int]: ...
    def analyze_slot(self, template: "SlotTemplate") -> "SlotAnalysis": ...
    def place(self, move: "Move") -> "Board": ...
```

`place()` returns a new board rather than mutating in place, preserving witness states, reproducibility, and debuggability.

## SlotAnalysis

```python
SlotAnalysis:
    valid_geometry: bool
    fixed_symbols: dict[int, Symbol]
    has_overlap: bool
    extends_existing_word: bool
    conflicts: tuple[Coord, ...]
```

The generator uses `SlotAnalysis` to build domains for the local slot CSP. The solver does not need to know board geometry.

## Move

```python
Move:
    start: Coord
    axis: int
    sequence: tuple[Symbol, ...]
```

`sequence` contains the full word, including existing symbols that are reused consistently.

## SlotTemplate

```python
SlotTemplate:
    anchor_coord: Coord
    anchor_symbol: Symbol
    axis: int
    length: int
    anchor_index: int
    start: Coord
    covered_coords: tuple[Coord, ...]
```

```text
start = anchor_coord - anchor_index * unit(axis)
coord(i) = start + i * unit(axis)
```

## Scoring Helper

Scoring is separated from `Board` so geometry and heuristics remain independently replaceable.

```python
class BoardScoring:
    def centroid(board: Board) -> tuple[float, ...]: ...
    def distance_to_centroid(coord: Coord, centroid: tuple[float, ...]) -> float: ...
    def free_cross_axis_span(board: Board, anchor: Coord, axis: int) -> int: ...
    def mean_distance_to_centroid(coords: tuple[Coord, ...], centroid: tuple[float, ...]) -> float: ...
    def local_adjacent_density(board: Board, coords: tuple[Coord, ...]) -> int: ...
```

The generator computes the centroid once per unchanged board state and passes it to distance features. `TemplateCandidate` may also carry extracted non-empty cross-domains and `domain_slack`, avoiding repeated extraction before the slot CSP.
