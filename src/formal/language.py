from __future__ import annotations

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
                f"Language ID: {self.language_id}",
                f"Alphabet: {{{', '.join(self.alphabet)}}}",
                f"k: {self.k}",
                f"Minimum word length: {self.min_word_length}",
                f"Forbidden snippets: {{{snippets}}}",
                "A sequence is valid iff it has the minimum length and contains no forbidden snippet.",
            ]
        )

    def to_dfa(self) -> DFA:
        states, transitions = self._automaton_parts()
        state_names = tuple(self._state_name(state) for state in states)
        named_transitions = {
            self._state_name(state): {
                symbol: self._state_name(target)
                for symbol, target in transitions[state].items()
            }
            for state in states
        }
        return DFA(
            alphabet=self.alphabet,
            states=state_names,
            start_state=self._state_name(()),
            accepting_states=frozenset(state_names),
            transitions=named_transitions,
            grammar_hint=self.describe(),
        )

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
