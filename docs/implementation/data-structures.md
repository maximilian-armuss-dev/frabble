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
dimensions = 2
Coord = tuple[int, int]
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
