# Future Work

A later benchmark version may combine move production with an explicit solvability decision.

## Balanced Solvability

One possible design uses approximately:

- 50% solvable scenarios,
- 50% unsolvable scenarios.

For unsolvable scenarios, the output schema would permit the model to report that no legal move exists.

This condition would measure both constructive search and reliable rejection. It requires a generator and solver capable of certifying solvability or unsolvability; heuristic failure to find a move is not sufficient.
