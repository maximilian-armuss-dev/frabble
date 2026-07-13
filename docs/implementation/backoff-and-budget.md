# Backoff and Search Budget

The generator does not need to prove that no further move exists. It only needs to produce valid witness transitions efficiently and terminate with a clear explanation when the configured search space is exhausted.

## Search Space per Board State

For each board state, the configured length set is searched once without replacement. Normal board-building transitions use `length_distribution`; when `fixed_final_transition_length` is set, the last requested witness transition uses that single configured length.

1. Select an unused word length from the configured length set.
2. Sort all anchor-axis pairs once by the cheap anchor score.
3. Expand the next non-overlapping batch of size `top_anchor_count`.
4. Remove deterministic word extensions and templates with empty cross-domains.
5. Try feasible templates in score order; `top_template_count` limits cumulative CSP calls across batches.
6. If none succeeds, expand only the next anchor batch if permitted by `max_anchor_count` and the anchor list.
7. On success, place the move and restart with a fresh length range for the new board state.
8. After exhaustive failure for one length, mark it consumed and sample another unused length.

The same anchor batch is not checked twice for an unchanged board state and length. Geometrically identical slots are processed once even if multiple overlap anchors can generate them. Work is repeated only after a successful move changes board geometry and candidate scores.

## Failure Modes

When every length is exhausted, the run fails with per-length reasons:

- `no_anchor_candidates`: No occupied coordinate had a valid crossing axis.
- `no_template_candidates`: Anchors existed, but every examined template was pruned by geometry, deterministic extension, or empty domains.
- `no_solver_solution`: Templates reached the slot CSP, but no sequence was found.
- `validator_rejected_all`: The slot CSP found sequences, but the validator rejected all with tolerated failure types.
- `templates_exhausted`: Mixed template failures without a successful placement.

The terminal message also reports counts for expanded anchors, feasible templates sent to the solver, and solver attempts, followed by likely configuration controls: `top_anchor_count`, `max_anchor_count`, `top_template_count`, `length_distribution`, scoring, or language constraints.

## No Solvability Claim

An exhausted candidate pool does not prove that the board is unsolvable. It only means that the config-bounded search did not find another witness move.

A generation run succeeds only when `target_witness_count` is reached. If the search space is exhausted first, generation fails and does not write a new scenario as a successful run.

## Validator as an Assertion

```text
generated_move -> validator -> must be valid
```

A hard validator failure indicates a bug in template generation, constraint extraction, the solver adapter, or language compilation. Known soft failures such as `word_extension` and `invalid_main_word` are treated as template failures and move search to the next template.
