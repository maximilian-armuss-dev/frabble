from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from itertools import product as iproduct

from ..domain.models import DFA


@dataclass(frozen=True)
class SLGrammar:
    alphabet: tuple[str, ...]
    k: int
    forbidden: frozenset[str]
    min_word_length: int
    seed: int

    def accepts(self, word: str) -> bool:
        if len(word) < self.min_word_length:
            return False
        alphabet_set = set(self.alphabet)
        if any(ch not in alphabet_set for ch in word):
            return False
        for i in range(len(word) - self.k + 1):
            if word[i : i + self.k] in self.forbidden:
                return False
        return True

    def to_dfa(self, minimize: bool = False) -> DFA:
        dfa = _build_dfa(self)
        if minimize:
            dfa = _minimize_dfa(dfa)
        return dfa

    def describe(self) -> str:
        return (
            f"SL_{self.k} grammar over {{{', '.join(self.alphabet)}}}, "
            f"{len(self.forbidden)} forbidden {self.k}-gram(s), "
            f"min word length {self.min_word_length}"
        )


# ---------------------------------------------------------------------------
# DFA construction
# ---------------------------------------------------------------------------

def _state_name(phase: int, history: str, min_word_length: int) -> str:
    if phase < min_word_length:
        return f"p{phase}:{history}"
    return f"r:{history}"


def _build_dfa(grammar: SLGrammar) -> DFA:
    alphabet = grammar.alphabet
    k = grammar.k
    forbidden = grammar.forbidden
    min_wl = grammar.min_word_length
    DEAD = "dead"

    transitions: dict[str, dict[str, str]] = {}
    transitions[DEAD] = {sym: DEAD for sym in alphabet}

    queue: deque[tuple[int, str]] = deque([(0, "")])
    visited: set[tuple[int, str]] = {(0, "")}

    while queue:
        phase, history = queue.popleft()
        key = _state_name(phase, history, min_wl)
        transitions.setdefault(key, {})

        for sym in alphabet:
            next_phase = min(phase + 1, min_wl)

            if phase >= k - 1:
                kgram = history + sym
                if kgram in forbidden:
                    transitions[key][sym] = DEAD
                    continue
                next_history = kgram[1:]
            else:
                next_history = history + sym

            next_key = _state_name(next_phase, next_history, min_wl)
            transitions[key][sym] = next_key

            nxt = (next_phase, next_history)
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

    all_keys: set[str] = set(transitions.keys())
    for sym_map in transitions.values():
        all_keys.update(sym_map.values())

    states = tuple(sorted(all_keys))
    accepting = frozenset(s for s in states if s.startswith("r:"))

    return DFA(
        alphabet=alphabet,
        states=states,
        start_state=_state_name(0, "", min_wl),
        accepting_states=accepting,
        transitions=transitions,
        grammar_hint=grammar.describe(),
    )


def _minimize_dfa(dfa: DFA) -> DFA:
    from automata.fa.dfa import DFA as AutomataDFA

    auto = AutomataDFA(
        states=set(dfa.states),
        input_symbols=set(dfa.alphabet),
        transitions={s: dict(t) for s, t in dfa.transitions.items()},
        initial_state=dfa.start_state,
        final_states=set(dfa.accepting_states),
    )
    minimized = auto.minify()

    def _key(s: object) -> str:
        if isinstance(s, frozenset):
            return "{" + ",".join(sorted(str(x) for x in s)) + "}"
        return str(s)

    states = tuple(sorted(_key(s) for s in minimized.states))
    transitions: dict[str, dict[str, str]] = {
        _key(s): {sym: _key(t) for sym, t in sym_map.items()}
        for s, sym_map in minimized.transitions.items()
    }
    return DFA(
        alphabet=dfa.alphabet,
        states=states,
        start_state=_key(minimized.initial_state),
        accepting_states=frozenset(_key(s) for s in minimized.final_states),
        transitions=transitions,
        grammar_hint=dfa.grammar_hint,
    )


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

class GrammarSamplingError(Exception):
    pass


def sample_sl_grammar(
    alphabet: tuple[str, ...],
    k: int,
    forbidden_fraction: float,
    min_word_length: int,
    seed: int,
) -> SLGrammar:
    rng = random.Random(seed)
    all_kgrams = ["".join(g) for g in iproduct(alphabet, repeat=k)]
    forbidden = frozenset(g for g in all_kgrams if rng.random() < forbidden_fraction)
    return SLGrammar(
        alphabet=alphabet,
        k=k,
        forbidden=forbidden,
        min_word_length=min_word_length,
        seed=seed,
    )


def sample_sl_grammar_auto(
    alphabet: tuple[str, ...],
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
) -> tuple[SLGrammar, int]:
    """Return (grammar, seed_used). Advances seed by attempt index until criteria met."""
    from .analysis import perron_eigenvalue, word_count_spectrum

    for attempt in range(max_attempts):
        attempt_seed = seed + attempt
        grammar = sample_sl_grammar(alphabet, k, forbidden_fraction, min_word_length, attempt_seed)

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
