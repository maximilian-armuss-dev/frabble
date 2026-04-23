from __future__ import annotations

from ..domain.models import DFA


def build_demo_dfa() -> DFA:
    """Language: one or more A, then exactly one B, then zero or more A, then C."""
    alphabet = ("A", "B", "C")
    states = ("q0", "q_before_b", "q_after_b", "q_accept", "q_dead")
    transitions = {
        "q0": {"A": "q_before_b", "B": "q_dead", "C": "q_dead"},
        "q_before_b": {"A": "q_before_b", "B": "q_after_b", "C": "q_dead"},
        "q_after_b": {"A": "q_after_b", "B": "q_dead", "C": "q_accept"},
        "q_accept": {"A": "q_dead", "B": "q_dead", "C": "q_dead"},
        "q_dead": {"A": "q_dead", "B": "q_dead", "C": "q_dead"},
    }
    return DFA(
        alphabet=alphabet,
        states=states,
        start_state="q0",
        accepting_states=frozenset({"q_accept"}),
        transitions=transitions,
        grammar_hint="A word is valid iff it matches A+ B A* C.",
    )


def enumerate_accepted_words(dfa: DFA, max_length: int) -> tuple[str, ...]:
    words: list[str] = []

    def visit(prefix: str) -> None:
        if prefix and dfa.accepts(prefix):
            words.append(prefix)
        if len(prefix) == max_length:
            return
        for token in dfa.alphabet:
            visit(prefix + token)

    visit("")
    return tuple(sorted(words, key=lambda word: (len(word), word)))
