from __future__ import annotations

import random
from itertools import product as iproduct

from ...domain.models import Symbol
from ...formal.language import StrictlyLocalLanguage


class GrammarSamplingError(Exception):
    pass


def sample_sl_grammar(
    alphabet: tuple[Symbol, ...],
    k: int,
    forbidden_fraction: float,
    min_word_length: int,
    seed: int,
    language_id: str = "",
) -> StrictlyLocalLanguage:
    rng = random.Random(seed)
    forbidden_snippets = tuple(
        g for g in iproduct(alphabet, repeat=k) if rng.random() < forbidden_fraction
    )
    return StrictlyLocalLanguage(
        language_id=language_id,
        alphabet=alphabet,
        k=k,
        forbidden_snippets=forbidden_snippets,
        min_word_length=min_word_length,
        seed=seed,
    )


def sample_sl_grammar_auto(
    alphabet: tuple[Symbol, ...],
    k: int,
    forbidden_fraction: float,
    min_word_length: int,
    seed: int,
    max_attempts: int,
    perron_min: float,
    perron_max: float,
    resample_length_min: int,
    resample_length_max: int,
    min_word_count: int,
    language_id: str = "",
) -> tuple[StrictlyLocalLanguage, int]:
    """Return (grammar, seed_used). Advances seed by attempt index until criteria met."""
    from .analysis import perron_eigenvalue, word_count_spectrum

    for attempt in range(max_attempts):
        attempt_seed = seed + attempt
        grammar = sample_sl_grammar(
            alphabet, k, forbidden_fraction, min_word_length, attempt_seed, language_id
        )

        lam = perron_eigenvalue(grammar)
        if not (perron_min <= lam <= perron_max):
            continue

        spectrum = word_count_spectrum(grammar, resample_length_max)
        word_count = sum(
            cnt
            for length, cnt in spectrum.items()
            if resample_length_min <= length <= resample_length_max
        )
        if word_count < min_word_count:
            continue

        return grammar, attempt_seed

    raise GrammarSamplingError(
        f"Could not sample a valid grammar after {max_attempts} attempt(s). "
        "Try adjusting --forbidden-fraction or relaxing the Perron / word-count bounds."
    )
