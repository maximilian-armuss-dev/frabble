from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Sequence

from ..domain.models import DFA, Symbol


@dataclass(frozen=True)
class StrictlyLocalLanguage:
    language_id: str
    alphabet: tuple[Symbol, ...]
    k: int
    forbidden_snippets: tuple[tuple[Symbol, ...], ...]
    min_word_length: int
    letter_scores: tuple[tuple[Symbol, int], ...]
    seed: int | None = None

    def accepts(self, sequence: Sequence[Symbol]) -> bool:
        symbols = tuple(sequence)
        if len(symbols) < self.min_word_length:
            return False
        if any(symbol not in self.alphabet for symbol in symbols):
            return False
        for snippet in self.forbidden_snippets:
            width = len(snippet)
            for start in range(0, len(symbols) - width + 1):
                if symbols[start : start + width] == snippet:
                    return False
        return True

    def describe(self) -> str:
        snippets = ", ".join(" ".join(snippet) for snippet in self.forbidden_snippets)
        return "\n".join(
            [
                f"Alphabet: {{{', '.join(self.alphabet)}}}",
                f"k: {self.k}",
                f"Minimum word length: {self.min_word_length}",
                f"Forbidden snippets: {{{snippets}}}",
                f"A sequence is valid iff it has the minimum length of {self.min_word_length} and contains no forbidden snippet.",
            ]
        )

    def letter_score_map(self) -> dict[Symbol, int]:
        return dict(self.letter_scores)

    def describe_letter_scores(self) -> str:
        lines = [f"  {symbol}: {score}" for symbol, score in self.letter_scores]
        return "\n".join(["Letter scores:"] + lines)

    def to_dfa(self) -> DFA:
        return _build_phase_dfa(self)

    def ortools_automaton(self) -> tuple[int, list[int], list[tuple[int, int, int]], dict[Symbol, int]]:
        states, transitions = self._automaton_parts()
        state_ids = {state: index for index, state in enumerate(states)}
        symbol_ids = {symbol: index for index, symbol in enumerate(self.alphabet)}
        arcs = [
            (state_ids[state], symbol_ids[symbol], state_ids[target])
            for state in states
            for symbol, target in transitions[state].items()
        ]
        return state_ids[()], list(state_ids.values()), arcs, symbol_ids

    def _automaton_parts(
        self,
    ) -> tuple[tuple[tuple[Symbol, ...], ...], dict[tuple[Symbol, ...], dict[Symbol, tuple[Symbol, ...]]]]:
        suffixes = self._suffix_states()
        transitions: dict[tuple[Symbol, ...], dict[Symbol, tuple[Symbol, ...]]] = {}
        for state in suffixes:
            transitions[state] = {}
            for symbol in self.alphabet:
                window = state + (symbol,)
                if self._ends_with_forbidden_snippet(window):
                    continue
                transitions[state][symbol] = window[-(self.k - 1) :] if self.k > 1 else ()
        return suffixes, transitions

    def _suffix_states(self) -> tuple[tuple[Symbol, ...], ...]:
        states: list[tuple[Symbol, ...]] = [()]
        for width in range(1, self.k):
            states.extend(self._valid_suffixes(width))
        return tuple(states)

    def _valid_suffixes(self, width: int) -> list[tuple[Symbol, ...]]:
        suffixes: list[tuple[Symbol, ...]] = [()]
        for _ in range(width):
            suffixes = [
                suffix + (symbol,)
                for suffix in suffixes
                for symbol in self.alphabet
                if not self._ends_with_forbidden_snippet(suffix + (symbol,))
            ]
        return sorted(suffixes)

    def _ends_with_forbidden_snippet(self, sequence: tuple[Symbol, ...]) -> bool:
        return any(
            len(snippet) <= len(sequence) and sequence[-len(snippet) :] == snippet
            for snippet in self.forbidden_snippets
        )

    @staticmethod
    def _state_name(state: tuple[Symbol, ...]) -> str:
        return "START" if not state else "S_" + "_".join(state)


def _phase_state_name(phase: int, history: str, min_word_length: int) -> str:
    if phase < min_word_length:
        return f"p{phase}:{history}"
    return f"r:{history}"


def _build_phase_dfa(language: StrictlyLocalLanguage) -> DFA:
    alphabet = language.alphabet
    k = language.k
    min_wl = language.min_word_length
    forbidden = frozenset(
        "".join(s) for s in language.forbidden_snippets if len(s) == k
    )
    DEAD = "dead"

    transitions: dict[str, dict[str, str]] = {}
    transitions[DEAD] = {sym: DEAD for sym in alphabet}

    queue: deque[tuple[int, str]] = deque([(0, "")])
    visited: set[tuple[int, str]] = {(0, "")}

    while queue:
        phase, history = queue.popleft()
        key = _phase_state_name(phase, history, min_wl)
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

            next_key = _phase_state_name(next_phase, next_history, min_wl)
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
        start_state=_phase_state_name(0, "", min_wl),
        accepting_states=accepting,
        transitions=transitions,
        grammar_hint=language.describe(),
    )
