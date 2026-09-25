# 🛠️ Planned benchmark redesign

Dimensionality, board history, score multipliers, and certified optimal moves are in place. The remaining item is a plan.

1. **Tune reasoning settings last.** Once the new case design and scoring are stable, run a small ablation on models that previously exhausted completion budgets: compare lower reasoning effort and token caps, track truncation, valid moves, score quality, token use, and cost. The exact budgets and model selection remain open.
