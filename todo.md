# 🛠️ Planned benchmark redesign

The dimensionality and board-history changes are already in place. Item 1 is implemented; the remaining items are plans.

1. **Done: Add dimension-independent score multipliers.** Bonus hyperplanes occur at coordinate sums `2 + 10k`. Within each plane, the coordinate phase `Σ(i − 1) × coordinate[i]` cycles cells through `x4, x2, x3, x2`. The planes are ten cells apart along every axis; only newly placed symbols receive a bonus, and bonuses on different symbols add rather than compound. The model prompt and evaluator use the same rule.
2. **Find optimal score references for small cases.** The hidden witness currently proves that at least one move exists, but does not establish the best score. Explore an exact optimizer for tractable cases and record clearly whether a score is proven optimal, only bounded, or still unknown. Extend this after the final multiplier rule is fixed.
3. **Make generated boards grow more organically.** Inspect five boards with 100 visible sequences and identify why their geometry looks unnatural. Adjust the generation process so the board develops like a plausible human Scrabble game instead of spreading with roughly uniform sparsity.
4. **Tune reasoning settings last.** Once the new case design and scoring are stable, run a small ablation on models that previously exhausted completion budgets: compare lower reasoning effort and token caps, track truncation, valid moves, score quality, token use, and cost. The exact budgets and model selection remain open.
