# Datenstrukturen

## Board

Das Board wird sparse repräsentiert. Ein Tensor oder dichtes Array ist für unbounded Generation ungeeignet, weil der Raum sehr dünn belegt ist und negative Koordinaten möglich bleiben sollen.

```python
Coord = tuple[int, ...]
Symbol = str

cells: dict[Coord, Symbol]
```

Für V1 gilt:

```python
dimensions in {2, 3}
Coord = tuple[int, ...]
```

## Segmente

Neben `cells` wird eine Segmentliste geführt. Ein Segment entspricht einem gelegten Wort.

```python
Segment:
    start: Coord
    axis: int
    sequence: tuple[Symbol, ...]
```

Segmente werden benötigt, um schnell zu bestimmen:

- auf welcher Achse eine Koordinate bereits Teil eines Wortes ist.
- welche Zielachse für ein neues Crossing erlaubt ist.
- ob eine Platzierung ein bestehendes Wort entlang derselben Achse verlängern würde.

## Indizes

Für effiziente Generierung werden aus `cells` und `segments` Indizes abgeleitet.

```python
symbol_index: dict[Symbol, set[Coord]]
coord_axes: dict[Coord, set[int]]
coord_segments: dict[Coord, set[SegmentId]]
```

`symbol_index` dient dem Anchor-Sampling. `coord_axes` dient der Criss-Cross-Achsenwahl. `coord_segments` dient Debugging, Validierung und späterer Analyse.

## Board-API

`Board` bleibt schlank. Es hält Zustand und bietet nur die geometrischen Operationen an, die Generator und Validator direkt brauchen.

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

`place()` arbeitet nicht in-place, sondern gibt eine neue Board-Instanz zurück. Dadurch bleiben Witness-States, Reproduzierbarkeit und Debugging sauber.

## SlotAnalysis

`analyze_slot()` fasst die geometrische Analyse eines Templates zusammen.

```python
SlotAnalysis:
    valid_geometry: bool
    fixed_symbols: dict[int, Symbol]
    has_overlap: bool
    extends_existing_word: bool
    conflicts: tuple[Coord, ...]
```

Der Generator verwendet `SlotAnalysis`, um Domains für das lokale Slot-CSP zu bauen. Der Solver muss keine Boardgeometrie kennen.

## Move

Ein Move beschreibt ein neu gelegtes Wort.

```python
Move:
    start: Coord
    axis: int
    sequence: tuple[Symbol, ...]
```

`sequence` enthält die vollständige Wortsequenz, inklusive Symbolen, die bereits auf dem Board liegen und konsistent überlappt werden.

## SlotTemplate

Ein SlotTemplate ist ein geometrischer Rahmen, bevor das konkrete Wort gelöst wurde.

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

Für ein Template gilt:

```text
start = anchor_coord - anchor_index * unit(axis)
coord(i) = start + i * unit(axis)
```

## Scoring Helper

Scoring gehört nicht direkt in `Board`. Es wird als eigene Helper-Schicht modelliert, damit Boardlogik und Heuristiken austauschbar bleiben.

```python
class BoardScoring:
    def centroid(board: Board) -> tuple[float, ...]: ...
    def distance_to_centroid(board: Board, coord: Coord) -> float: ...
    def free_cross_axis_span(board: Board, anchor: Coord, axis: int) -> int: ...
    def mean_distance_to_centroid(board: Board, coords: tuple[Coord, ...]) -> float: ...
    def local_adjacent_density(board: Board, coords: tuple[Coord, ...]) -> int: ...
```

`BoardScoring` liefert die Features für Anchor- und Template-Ranking. Der Generator kombiniert diese Features zu Scores.
