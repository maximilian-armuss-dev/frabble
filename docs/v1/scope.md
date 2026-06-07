# V1 Scope

V1 is a feasibility test for the complete benchmark pipeline.

## Included

- board dimensionality of two or three, configured through YAML,
- one placeholder alphabet with six symbols,
- one strictly local language,
- minimum word length three,
- overlap-only connected placements,
- binary move validity,
- one full move-generation task,
- independent scenarios with fresh boards and racks.

The model receives:

- the language rule,
- the current board,
- the rack,
- the output schema.

It must place one complete valid sequence.

## Excluded

V1 does not include:

- Scrabble-style point scoring,
- optimization over valid moves,
- exhaustive solution-space analysis,
- explicit solvable-versus-unsolvable classification,
- tokenizer-level alphabet experiments,
- multiple language families,
- adjacency-only placements.

These exclusions keep the first implementation focused on validating generation, prompting, parsing, and deterministic evaluation.
