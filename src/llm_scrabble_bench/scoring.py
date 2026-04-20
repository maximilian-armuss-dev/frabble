from __future__ import annotations

import math
from collections import Counter
from typing import Iterable

from .models import Move, Scenario


def token_frequencies(words: Iterable[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for word in words:
        counts.update(word)
    return counts


def token_scores_from_frequencies(
    frequencies: Counter[str], alphabet: Iterable[str]
) -> dict[str, int]:
    total = sum(frequencies.values())
    if total == 0:
        return {token: 1 for token in alphabet}
    scores: dict[str, int] = {}
    for token in alphabet:
        probability = frequencies[token] / total
        scores[token] = max(1, round(-math.log2(probability) * 2))
    return scores


def score_word(word: str, token_scores: dict[str, int]) -> int:
    return sum(token_scores[token] for token in word)


def optimal_move(scenario: Scenario) -> Move:
    return max(
        scenario.legal_moves,
        key=lambda move: score_word(move.tokens, scenario.token_scores),
    )


def optimal_score(scenario: Scenario) -> int:
    return score_word(optimal_move(scenario).tokens, scenario.token_scores)
