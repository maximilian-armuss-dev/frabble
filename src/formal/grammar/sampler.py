from __future__ import annotations

import random
from itertools import product as iproduct

from ...domain.models import Symbol
from ...formal.language import StrictlyLocalLanguage
from .config import GrammarConfig


class GrammarSamplingError(Exception):
    pass


LETTER_SCORE_VALUES: tuple[int, ...] = (1, 2, 3, 4, 5)
LETTER_SCORE_WEIGHTS: tuple[int, ...] = (16, 8, 4, 2, 1)


def sample_letter_scores(
    alphabet: tuple[Symbol, ...], rng: random.Random
) -> tuple[tuple[Symbol, int], ...]:
    scores = rng.choices(LETTER_SCORE_VALUES, weights=LETTER_SCORE_WEIGHTS, k=len(alphabet))
    return tuple(sorted(zip(alphabet, scores)))


def sample_grammar_from_config(
    config: GrammarConfig,
    *,
    language_id: str | None = None,
) -> tuple[StrictlyLocalLanguage, int]:
    from .alphabet import ChineseAlphabetSampler, LetterAlphabetSampler

    if config.alphabet_type == "chinese":
        sampler = ChineseAlphabetSampler()
    else:
        sampler = LetterAlphabetSampler(case=config.alphabet_case)
    alphabet = sampler.sample(config.alphabet_size, config.seed)
    resolved_id = language_id or config.config_name
    if config.auto_resample.enabled:
        return sample_sl_grammar_auto(
            alphabet=alphabet,
            k=config.k,
            forbidden_fraction=config.forbidden_fraction,
            min_word_length=config.resolved_min_word_length,
            seed=config.seed,
            max_attempts=config.auto_resample.max_attempts,
            perron_min=config.auto_resample.perron_min,
            perron_max=config.auto_resample.perron_max,
            resample_length_min=config.auto_resample.resample_length_min,
            resample_length_max=config.auto_resample.resample_length_max,
            min_word_count=config.auto_resample.min_word_count,
            language_id=resolved_id,
        )
    grammar = sample_sl_grammar(
        alphabet=alphabet,
        k=config.k,
        forbidden_fraction=config.forbidden_fraction,
        min_word_length=config.resolved_min_word_length,
        seed=config.seed,
        language_id=resolved_id,
    )
    return grammar, config.seed


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
    letter_scores = sample_letter_scores(alphabet, rng)
    return StrictlyLocalLanguage(
        language_id=language_id,
        alphabet=alphabet,
        k=k,
        forbidden_snippets=forbidden_snippets,
        min_word_length=min_word_length,
        letter_scores=letter_scores,
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
