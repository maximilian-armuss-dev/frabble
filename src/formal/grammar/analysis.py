from __future__ import annotations

from collections import defaultdict
from itertools import product as iproduct

import numpy as np

from ...domain.models import Symbol
from ...formal.language import StrictlyLocalLanguage


def perron_eigenvalue(grammar: StrictlyLocalLanguage) -> float:
    """Largest real eigenvalue of the SL_k de Bruijn transition graph.

    λ > 1 means the language grows exponentially with word length — desirable
    for puzzle generation.  λ ≤ 1 indicates a finite or very sparse language.
    """
    k = grammar.k
    alphabet = grammar.alphabet
    forbidden = frozenset(
        "".join(s) for s in grammar.forbidden_snippets if len(s) == k
    )

    if k == 1:
        valid = sum(1 for sym in alphabet if (sym,) not in grammar.forbidden_snippets)
        return float(valid)

    nodes = ["".join(g) for g in iproduct(alphabet, repeat=k - 1)]
    n = len(nodes)
    idx = {node: i for i, node in enumerate(nodes)}
    mat = np.zeros((n, n))

    for u in nodes:
        for sym in alphabet:
            kgram = u + sym
            if kgram not in forbidden:
                v = kgram[1:]
                mat[idx[u]][idx[v]] = 1.0

    eigenvalues = np.linalg.eigvals(mat)
    return float(np.max(eigenvalues.real))


def word_count_spectrum(grammar: StrictlyLocalLanguage, max_length: int) -> dict[int, int]:
    """Count accepted words of each length from 1 to max_length."""
    k = grammar.k
    min_wl = grammar.min_word_length
    forbidden = frozenset(
        "".join(s) for s in grammar.forbidden_snippets if len(s) == k
    )
    alphabet = grammar.alphabet

    current: dict[tuple[int, str], int] = {(0, ""): 1}
    counts: dict[int, int] = {}

    for step in range(1, max_length + 1):
        next_states: dict[tuple[int, str], int] = defaultdict(int)

        for (phase, history), cnt in current.items():
            for sym in alphabet:
                next_phase = min(phase + 1, min_wl)

                if phase >= k - 1:
                    kgram = history + sym
                    if kgram in forbidden:
                        continue
                    next_history = kgram[1:]
                else:
                    next_history = history + sym

                next_states[(next_phase, next_history)] += cnt

        counts[step] = sum(
            cnt for (phase, _), cnt in next_states.items() if phase == min_wl
        )
        current = dict(next_states)

    return counts


def count_words(grammar: StrictlyLocalLanguage, length: int) -> int:
    return word_count_spectrum(grammar, length).get(length, 0)
