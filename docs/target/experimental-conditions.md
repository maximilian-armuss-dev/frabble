# Experimental Conditions

V1 implements only a small full-puzzle core with board dimensionality \(d \ge 2\). The following conditions describe the broader target experiment.

## E1: Membership

The model classifies whether a supplied sequence belongs to the language.

The language may be communicated through:

- an explicit grammar or automaton description,
- positive and negative examples.

## E2.1: Generation from Examples

The model receives examples and must generate a new valid sequence. This condition combines language induction with constrained generation.

## E2.2: Generation from an Explicit Grammar

The model receives the formal rule directly and must generate a valid sequence.

The difference between E2.1 and E2.2 estimates the cost of inducing the language rather than merely following it.

## E3: Placement with Oracle Words

The model receives one or more sequences known to be valid and must place one legally on the board using the available rack.

This isolates spatial and tile constraints from language generation.

## E4: Full Puzzle

The model receives the language specification, board, rack, and output schema, then must produce one complete legal move.

This is the headline condition because it combines:

- formal-language understanding,
- candidate generation,
- rack accounting,
- spatial placement,
- cross-word validation,
- structured output.
