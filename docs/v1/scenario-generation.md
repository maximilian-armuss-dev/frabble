# V1 Scenario Generation

V1 creates one deterministic witness scenario from a YAML configuration.

## Board Model

The board uses unbounded sparse integer coordinates. Only occupied cells are stored.

## Word Lengths

Generated words have lengths from three through seven. Using only length seven would make the benchmark unnecessarily degenerate and reduce structural variation.

## Construction

The generator:

1. places an initial valid word,
2. selects an existing tile as an anchor,
3. chooses a placement axis,
4. searches for a valid word that overlaps the anchor,
5. validates the complete placement,
6. repeats until the configured target is reached or the budget is exhausted.

## Anchor Heuristic

Candidate anchors are scored to favor placements that:

- extend the occupied structure,
- create useful cross-word interactions,
- avoid repeatedly growing only one straight line.

## Deterministic Search

Search is performed in deterministic batches. For each candidate slot, the generator derives:

- fixed positions from existing board tiles,
- domains for unconstrained positions,
- cross-word constraints,
- rack or extension requirements.

The slot CSP then enumerates valid assignments in a stable order.

## Domain Slack and Widening

Initial domains may be restricted to keep search inexpensive. If no candidate is found, the generator widens them in controlled steps. This provides predictable behavior without permanently excluding less obvious solutions.
