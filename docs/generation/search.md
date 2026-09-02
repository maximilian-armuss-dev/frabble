# Candidate Search

One board can offer many geometrically plausible placements. Candidate search orders and bounds this work so scenario generation remains reproducible and operationally finite without confusing explored possibilities with the full legal move space.

## Search shape

```mermaid
flowchart TD
    Board --> Lengths["Candidate lengths"]
    Lengths --> Anchors["Ranked anchor-axis pairs"]
    Anchors --> Templates["Feasible slot templates"]
    Templates --> Solver["Slot attempts"]
    Solver -->|success| NextBoard
    Solver -->|budget remains| Templates
    Templates -->|batch exhausted| Anchors
    Anchors -->|length exhausted| Lengths
    Lengths -->|exhausted| Failure
```

For an unchanged board, each configured word length is considered at most once. Occupied coordinates paired with unused crossing axes form anchors. Anchors are expanded in batches into concrete slots, allowing the generator to widen from central candidates toward more distant parts of the board without reconsidering previous work.

Templates are removed before solving when their geometry conflicts with the board, they repeat a known slot, they would deterministically extend an existing word, or cross-word analysis leaves an empty symbol domain. The surviving templates share a cumulative solver-attempt budget for the current length.

## Ranking

Anchor ranking uses distance from the current board centroid as an inexpensive early signal. Once a complete template exists, ranking can also consider the mean distance of its new cells and their local occupied density. Features are normalized within the current candidate pool before configured weights are applied.

These scores express a preference for compact growth and manageable local interaction. They do not predict legality: a highly ranked template may have no language solution, while a later candidate may validate successfully.

Feature calculation and stable ordering live in [`src/generator/candidates.py`](../../src/generator/candidates.py), with geometric measurements in [`src/benchmark/scoring.py`](../../src/benchmark/scoring.py). Weights and search bounds belong to [`src/generator/config.py`](../../src/generator/config.py) and the checked-in generation recipes.

## Failure semantics

Terminal errors distinguish broad exhaustion points such as missing anchors, no feasible templates, no local solver solution, or validator rejection. These categories describe the path actually searched and help identify restrictive configs or broken invariants.

An exhausted search is not a proof that the board has no legal move. It only means that the configured lengths, anchor range, template budget, and solver attempts did not produce another witness. A scenario is considered successful only after reaching its requested witness count; incomplete growth is not persisted as a completed result.

The search loop and failure accounting live in [`src/generator/engine.py`](../../src/generator/engine.py). The distinction between a local solver result and full move validity is explained in [Local Slot Solver](slot-solver.md).
