# Anchor and Template Scoring

Scoring should grow the board radially and compactly without forcing search into overcrowded regions.

Scoring is implemented in a separate helper layer such as `BoardScoring`, not as methods on `Board`. `Board` provides state and geometric analysis; `BoardScoring` derives heuristic features.

Weights live under `scoring` in the generator YAML so heuristics can be tuned without code changes. Higher values strengthen the corresponding effect; all values must be non-negative.

Raw features are min-max normalized to `[0, 1]` within each candidate pool before weighting. Anchor features are normalized across the current anchor pool and template features across the current template pool. A constant feature is assigned `0.0` for every candidate. YAML values therefore act as relative weights rather than scale corrections.

```yaml
scoring:
  anchor_centroid_weight: 1.0
  anchor_free_span_weight: 1.0
  template_centroid_weight: 1.0
  template_new_cell_bonus_weight: 1.5
  template_local_density_penalty_weight: 1.0
  template_domain_slack_weight: 1.0
```

## Candidate Order

1. Sample a word length.
2. Cheaply score every valid anchor-axis pair.
3. Stable-sort anchors once.
4. Expand the next unexamined anchor batch.
5. Remove templates with deterministic extensions on touched axes or empty cross-domains.
6. Score feasible templates, including domain slack.
7. Try the best templates up to the global CSP budget; open another anchor batch when necessary.

Word length therefore influences anchor evaluation without requiring complex joint sampling over length and coordinate.

## Anchor Score

```text
anchor_score =
  - anchor_centroid_weight  * norm(distance_to_centroid)
  + anchor_free_span_weight * norm(free_cross_axis_span)
```

`distance_to_centroid` is the anchor's distance from the current board centroid. A higher weight pulls search inward; a lower weight allows more frontier growth.

`free_cross_axis_span` approximates the amount of geometrically usable space along the target axis around the anchor. A higher weight favors anchors with room for the sampled length and may reduce dead ends.

No exact feasibility count is computed for anchor scoring. Precise feasibility is determined when the anchor batch is expanded into templates.

`top_anchor_count` is the batch size. For example, anchors `1..40` are expanded first, followed by `41..80` only when needed. An anchor is not expanded twice for the same board state and word length. `max_anchor_count` may impose a hard upper bound; otherwise widening may continue while CSP budget remains.

## Template Score

```text
template_score =
  - template_centroid_weight              * norm(distance_of_new_cells_to_centroid)
  + template_new_cell_bonus_weight        * norm(new_cell_count)
  - template_local_density_penalty_weight * norm(local_adjacent_density)
  + template_domain_slack_weight          * norm(domain_slack)
```

- `distance_of_new_cells_to_centroid`: Mean distance of new cells from the centroid. Higher weight fills inward.
- `new_cell_count`: Number of newly occupied cells. Higher weight discourages one-symbol additions and hole filling.
- `local_adjacent_density`: Existing orthogonal neighbors around new template cells, excluding diagonals and cells within the template. Higher weight avoids dense interiors.
- `domain_slack`: Sum of symbols still allowed by cross-word constraints across all new cells. Empty domains are removed before ranking; higher weight favors linguistically flexible placements.

Ties are resolved deterministically by stable template order; no extra template sampling is used.

`top_template_count` is the cumulative CSP-attempt budget per word length and board state across all opened anchor batches. Geometrically invalid templates, deterministic extensions, duplicate slots, and empty-domain templates do not consume this budget.

A real length range is needed to prevent overly regular shapes. V1 samples inclusively from `start = 3` through `end = 7`; `start = end = 7` is useful only for debugging.

Practical tuning:

- Increase `template_domain_slack_weight` when fragile interior templates dominate.
- Increase `template_local_density_penalty_weight` or reduce `template_centroid_weight` when shapes become too dense.
- Increase `template_new_cell_bonus_weight` when one-symbol additions become too frequent.
