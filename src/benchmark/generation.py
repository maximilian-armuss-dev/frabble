from __future__ import annotations

import random
from collections import Counter

from ..domain.board import build_demo_board
from ..domain.models import Scenario
from ..formal.automata import build_demo_dfa, enumerate_accepted_words
from ..formal.validation import enumerate_legal_moves
from .scoring import token_frequencies, token_scores_from_frequencies


def sample_rack(
    alphabet: tuple[str, ...],
    frequencies: Counter[str],
    rack_size: int,
    rng: random.Random,
) -> tuple[str, ...]:
    weights = [max(1, frequencies[token]) for token in alphabet]
    return tuple(sorted(rng.choices(alphabet, weights=weights, k=rack_size)))


def generate_scenario(
    seed: int = 7,
    rack_size: int = 4,
    reference_max_length: int | None = None,
    grammar_path: str | None = None,
) -> Scenario:
    rng = random.Random(seed)

    if grammar_path is not None:
        from ..grammar.serialization import load_grammar
        grammar, config, _ = load_grammar(grammar_path)
        dfa = grammar.to_dfa(minimize=config.minimize_dfa)
    else:
        dfa = build_demo_dfa()

    board = build_demo_board()
    if reference_max_length is None:
        reference_max_length = max(board.shape)
    if reference_max_length < 1:
        raise ValueError("reference_max_length must be at least 1.")

    accepted_words = enumerate_accepted_words(dfa, max_length=reference_max_length)
    frequencies = token_frequencies(accepted_words)
    token_scores = token_scores_from_frequencies(frequencies, dfa.alphabet)

    for _ in range(500):
        rack = sample_rack(dfa.alphabet, frequencies, rack_size, rng)
        legal_moves = enumerate_legal_moves(board, dfa, rack, token_scores, accepted_words)
        if legal_moves:
            return Scenario(
                dfa=dfa,
                board=board,
                rack=rack,
                token_scores=token_scores,
                accepted_words=accepted_words,
                legal_moves=legal_moves,
                reference_max_length=reference_max_length,
            )

    rack = ("A", "A", "B", "C")
    legal_moves = enumerate_legal_moves(board, dfa, rack, token_scores, accepted_words)
    return Scenario(
        dfa=dfa,
        board=board,
        rack=rack,
        token_scores=token_scores,
        accepted_words=accepted_words,
        legal_moves=legal_moves,
        reference_max_length=reference_max_length,
    )
