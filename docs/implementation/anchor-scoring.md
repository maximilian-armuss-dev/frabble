# Anchor and Template Scoring

Scoring should grow the board compactly without forcing search into overcrowded regions. The centroid distance uses a square Chebyshev/L-infinity metric so the search fills toward square level sets rather than circular ones.

Scoring is implemented in a separate helper layer such as `BoardScoring`, not as methods on `Board`. `Board` provides state and geometric analysis; `BoardScoring` derives heuristic features.

Weights live under `scoring` in the generator YAML so heuristics can be tuned without code changes. Higher values strengthen the corresponding effect; all values must be non-negative.

Raw features are min-max normalized to `[0, 1]` within each candidate pool before weighting. Anchor features are normalized across the current anchor pool and template features across the current template pool. A constant feature is assigned `0.0` for every candidate. YAML values therefore act as relative weights rather than scale corrections.

```yaml
scoring:
  anchor_centroid_weight: 0.8
  template_centroid_weight: 1.2
  template_local_density_penalty_weight: 0.6
```

## Candidate Order

1. Sample a word length.
2. Cheaply score every valid anchor-axis pair.
3. Stable-sort anchors once.
4. Expand the next unexamined anchor batch.
5. Remove templates with deterministic extensions on touched axes or empty cross-domains.
6. Score feasible templates.
7. Try the best templates up to the global CSP budget; open another anchor batch when necessary.

Word length therefore influences anchor evaluation without requiring complex joint sampling over length and coordinate.

## Anchor Score

```text
anchor_score =
  - anchor_centroid_weight * norm(distance_to_centroid)
```

`distance_to_centroid` is the anchor's Chebyshev distance from the current board centroid. A higher weight pulls search inward along square level sets; a lower weight allows more frontier growth.

No exact feasibility count is computed for anchor scoring. Precise feasibility is determined when the anchor batch is expanded into templates.

`top_anchor_count` is the batch size. For example, anchors `1..40` are expanded first, followed by `41..80` only when needed. An anchor is not expanded twice for the same board state and word length. `max_anchor_count` may impose a hard upper bound; otherwise widening may continue while CSP budget remains.

## Template Score

```text
template_score =
  - template_centroid_weight * norm(distance_of_new_cells_to_centroid)
  - template_local_density_penalty_weight * norm(local_adjacent_density)
```

- `distance_of_new_cells_to_centroid`: Mean Chebyshev distance of new cells from the centroid. Higher weight fills inward along square level sets.
- `local_adjacent_density`: Existing orthogonal neighbors around new template cells, excluding diagonals and cells within the template. Higher weight avoids dense interiors.

Ties are resolved deterministically by stable template order; no extra template sampling is used.

`top_template_count` is the cumulative CSP-attempt budget per word length and board state across all opened anchor batches. Geometrically invalid templates, deterministic extensions, duplicate slots, and empty-domain templates do not consume this budget.

A real length range is needed to prevent overly regular shapes. V1 samples inclusively across the configured range; `start = end` is useful only for debugging. The evaluation baseline uses `3..6` so normal board-building words do not create longer spikes than the fixed final transition.

Practical tuning:

- Increase `template_local_density_penalty_weight` or reduce `template_centroid_weight` when shapes become too dense.
- Increase `template_centroid_weight` or `anchor_centroid_weight` when early boards drift into long branches.
- Reduce `template_local_density_penalty_weight` when edge sparsity becomes too high.
