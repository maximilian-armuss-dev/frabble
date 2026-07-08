# Generator Algorithm

The generator builds an internally unbounded board. Every successful transition can be exported as a scenario with a witness.

## Reproducibility

Generation must be seeded. The same generator config and seed must produce the same scenarios; different seeds may produce different but still reproducible scenarios.

All random decisions use one controlled RNG or deterministically derived child seeds, including:

- the initial word,
- word length,
- symbol preferences for free slot positions in the CSP.

Sorting is stable. Score ties are resolved by fixed fields such as coordinate, axis, anchor index, and sequence.

## Flow

1. Start with an empty board.
2. Sample an initial valid word from the V1 language.
3. Place it on `axis = 0` around the origin.
4. Store the first segment.
5. Repeat until termination:
   - Select a word length from the allowed distribution, or use `fixed_final_transition_length` on the final requested transition when configured.
   - Cheaply score and sort all anchor-axis pairs.
   - Expand the next anchor batch.
   - Create slot templates for every anchor index of that length.
   - Prune impossible geometry, duplicate slots, and deterministic extensions on every touched axis.
   - Extract cross-domains and prune templates with an empty domain.
   - Score remaining templates, including domain slack.
   - Solve templates up to the cumulative top-K CSP budget.
   - If none succeeds, expand the next unseen anchor batch.
   - On success, place the word and store the segment and witness transition.
   - If the length fails, mark it consumed for this board state and continue until the length pool is exhausted.

## Feasibility-Aware Candidates

V1 does not sample one anchor symbol first. It samples a word length and then builds a global candidate pool:

```text
sample length L
score and sort all anchor-axis candidates once
for fresh batch in sorted_anchors[0:40], [40:80], ...:
    templates = expand only fresh batch for length L
    templates = geometry / duplicate / any-axis deterministic-extension prune
    templates = cross-domain extraction and empty-domain prune
    templates = rank feasible templates including domain slack
    try new templates while cumulative CSP attempts < K
    stop on first valid move
```

Central expansion remains the first preference without permanently blocking search. If a dense interior batch has no feasible templates, farther anchors are examined without repeating earlier work while CSP budget remains. Exact feasibility is evaluated at template level because only a concrete template determines its cross-word constraints.

Each length is sampled at most once per unchanged board state. If no length yields a move, generation terminates with a failure report. A successful move resets the length range for the new board state.

Recommended V1 defaults:

```text
top_anchor_count = 40
top_template_count = 120
max_anchor_count = null
```

`top_anchor_count` is a batch size, `top_template_count` limits cumulative CSP attempts per length, and `max_anchor_count` optionally caps widening.

The inclusive length range is:

```text
length_distribution.start = 3
length_distribution.end = 7
fixed_final_transition_length = 6
```

Using `start = end = 7` produces consistently wide slots and, together with centroid heuristics, may create unnaturally regular filling. `fixed_final_transition_length` only applies to the final requested witness transition; evaluation case preparation requests `board_size + 1` transitions, so this controls the move later used as ground truth.

## Crossing-Axis Logic

For each anchor, candidates are created on every axis on which the coordinate is not already part of a word.

In 2D:

- An anchor belonging to `axis = 0` creates a candidate on `axis = 1`.
- An anchor belonging to `axis = 1` creates a candidate on `axis = 0`.

In higher dimensions, one anchor may create multiple target axes. Stable sorting by score, coordinate, and axis preserves reproducibility.

## Template Pruning

Before reaching the solver, a template is removed when:

- It does not contain the anchor at `anchor_index`.
- An occupied cell conflicts with its fixed symbol.
- It extends or runs into an existing segment on the same axis.
- It lacks a consistent overlap.
- Its geometric slot duplicates one already considered.
- It deterministically extends an existing valid sequence on the placement axis or a touched cross-axis.
- At least one cross-domain is empty.

New cross-words are allowed, but existing valid words may not be extended. Extracted non-empty domains are reused by the slot CSP. Pruning reduces solver calls but does not replace final validation.

## Deterministic Candidate Selection

Anchors and templates are stable-sorted. Templates reach the slot CSP in score order, with deterministic tie resolution. Within a selected template, the slot CSP uses seeded random symbol preferences for free positions so it does not always return the alphabetically first solution while remaining reproducible.

## Logging

Each generated scenario should record:

- Generator config.
- Seed.
- Language ID and forbidden snippets.
- Word-length distribution.
- Top-M anchor coordinates and scores.
- Top-K templates and scores.
- Solver status per attempted template.
- Witness move.

## Witness

Before application, each solved move is checked by the regular validator. The run stores the initial board once and then one transition per witness:

```text
initial_board = board_after_initial_word
transition:
  rack = rack_before_move
  move = full_move
  placed = newly_occupied_cells
  search_log = solver_and_candidate_trace
```

Any board state is reconstructed from `initial_board` and preceding transitions, avoiding duplicated board snapshots in memory and JSON.
