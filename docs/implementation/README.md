# V1 Implementation

This directory contains the implementation-oriented specification for the V1 puzzle generator. These files are intended as a direct basis for code. General motivation, the paper's target design, and later extensions remain outside this directory.

## Files

- [data-structures.md](data-structures.md): Data models and indices.
- [generator-algorithm.md](generator-algorithm.md): Puzzle-generation flow.
- [slot-csp.md](slot-csp.md): Local CSP for individual word slots.
- [anchor-scoring.md](anchor-scoring.md): Anchor and template heuristics.
- [backoff-and-budget.md](backoff-and-budget.md): Backoff model and termination logic.

## V1 Decisions

- Board generation is unbounded.
- Exported scenarios may later receive a region of interest or bounding box.
- V1 supports sparse boards with `dimensions >= 2`.
- V1 uses `k = 2`.
- V1 uses a simple Strictly Local language defined by forbidden snippets.
- Words of length `1` and `2` are invalid.
- V1 uses local slot CSPs rather than one global board CSP.
- V1 does not jointly sample word length and a concrete anchor coordinate.
- For each sampled length, V1 uses feasibility-aware candidates: anchors are cheaply pre-scored and expanded in non-overlapping batches. Only templates without deterministic word extensions on touched axes and without empty cross-domains reach the slot CSP.
- Generation is seeded and reproducible: the same config and seed produce the same scenarios.

## Responsibilities

- `Board`: State and geometric analysis.
- `BoardScoring`: Derived heuristic features for anchor and template ranking.
- `ScenarioGenerator`: Orchestration of length, candidate pool, scoring, slot CSP, and witness storage.
- `SlotCSP`: Local solving of individual word slots.
- `Validator`: Assertions and later evaluation of LLM outputs.
