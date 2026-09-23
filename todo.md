## 🛠️ Planned benchmark redesign

The dimensionality and board-history changes are already in place. The remaining work focuses on scoring, board geometry, and evaluation settings. The items below are plans, not descriptions of implemented benchmark behavior.

1. **Add dimension-independent score multipliers.** Define a coordinate pattern and scoring rule that work in every dimension and reward deliberate placement. Test whether nearby multipliers can combine in one move or should be spaced apart, and make the same rule visible to the model and validator.
2. **Find optimal score references for small cases.** The hidden witness currently proves that at least one move exists, but does not establish the best score. Explore an exact optimizer for tractable cases and record clearly whether a score is proven optimal, only bounded, or still unknown. Extend this after the final multiplier rule is fixed.
3. **Make generated boards grow more organically.** Inspect five boards with 100 visible sequences and identify why their geometry looks unnatural. Adjust the generation process so the board develops like a plausible human Scrabble game instead of spreading with roughly uniform sparsity.
4. **Tune reasoning settings last.** Once the new case design and scoring are stable, run a small ablation on models that previously exhausted completion budgets: compare lower reasoning effort and token caps, track truncation, valid moves, score quality, token use, and cost. The exact budgets and model selection remain open.
