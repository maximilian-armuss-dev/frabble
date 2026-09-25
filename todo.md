# 🛠️ Planned benchmark redesign

The dimensionality, board-history, and score-multiplier changes are already in place. The remaining items are plans.

1. **Find optimal score references for small cases.** The hidden witness currently proves that at least one move exists, but does not establish the best score. Explore an exact optimizer for tractable cases and record clearly whether a score is proven optimal, only bounded, or still unknown.
2. **Review organic board growth.** The generator supports recency and seeded variety among similarly ranked placements. The evaluation-base recipe now penalizes incidental contacts with existing cells instead of explicitly detecting filled 2×2 and 3×3 regions. Compare the rendered alternatives and adjust the look after visual feedback.
3. **Tune reasoning settings last.** Once the new case design and scoring are stable, run a small ablation on models that previously exhausted completion budgets: compare lower reasoning effort and token caps, track truncation, valid moves, score quality, token use, and cost. The exact budgets and model selection remain open.
