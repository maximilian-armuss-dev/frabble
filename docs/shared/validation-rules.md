# Validation Rules

A move is valid when all of the following hold:

- Output matches the expected JSON schema.
- `sequence` is valid in the formal language.
- Placement lies fully within the board when bounds are defined.
- New symbols do not conflict with occupied cells.
- At least one new symbol is placed.
- The move connects through at least one consistent overlap.
- It does not extend an existing valid word on any touched axis.
- Every sequence created by the move on every relevant axis is valid.
- Newly placed symbols can be paid from the rack.
- Words shorter than `3` are invalid.

V1 accepts overlap connections only. Pure adjacency without overlap is invalid even when it would create valid cross-words, simplifying prototype generation and validation.

## Word Extension

A move may not extend an existing valid word either along its placement axis or along a cross-axis touched by new tiles. Extension occurs when the move attaches to or overlaps an existing valid sequence and adds symbols to create a longer contiguous sequence.

This also applies when the existing sequence is implicit rather than stored as its own segment. The pre-move board geometry is decisive: if a touched axis already contains at least three contiguous symbols forming a valid word, the move may not extend it.

Existing symbols from other words may still be used as crossings when they do not yet form a valid contiguous sequence on that axis. A move may therefore fill gaps and create a valid word for the first time.

## Validation Order

1. Parse and normalize JSON.
2. Validate `sequence` against the language.
3. Compute coordinates from `start`, `axis`, and sequence length.
4. Check bounds when applicable.
5. Check overlaps and spatial conflicts.
6. Require at least one new symbol.
7. Require a consistent overlap with the existing board.
8. Reject extension of an existing valid word on the placement or touched cross-axes.
9. Simulate the resulting board.
10. Extract relevant sequences created along all axes.
11. Require every sequence of length at least `3` to be valid.
12. Remove consistently overlapped board symbols from `sequence` and verify that the remaining multiset is available in the rack.
13. Return binary validity and record the failure class.

## Failure Classes

- Schema error.
- Invalid sequence.
- Out-of-bounds placement.
- Spatial conflict.
- Missing overlap.
- Forbidden word extension.
- Invalid main word.
- Invalid cross-word.
- Rack error.
