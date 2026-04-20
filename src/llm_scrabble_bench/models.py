from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DFA:
    alphabet: tuple[str, ...]
    states: tuple[str, ...]
    start_state: str
    accepting_states: frozenset[str]
    transitions: dict[str, dict[str, str]]
    grammar_hint: str

    def accepts(self, word: str) -> bool:
        state = self.start_state
        for token in word:
            if token not in self.alphabet:
                return False
            state = self.transitions[state][token]
        return state in self.accepting_states

    def describe(self) -> str:
        lines = [
            f"Alphabet: {{{', '.join(self.alphabet)}}}",
            f"Start state: {self.start_state}",
            f"Accepting states: {{{', '.join(sorted(self.accepting_states))}}}",
            f"Informal grammar: {self.grammar_hint}",
            "Transition table:",
        ]
        for state in self.states:
            transitions = ", ".join(
                f"{token}->{self.transitions[state][token]}" for token in self.alphabet
            )
            lines.append(f"- {state}: {transitions}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Board:
    cells: np.ndarray

    @property
    def dimensions(self) -> int:
        return self.cells.ndim

    @property
    def shape(self) -> tuple[int, ...]:
        return self.cells.shape

    @property
    def rows(self) -> int:
        return self.shape[0]

    @property
    def cols(self) -> int:
        return self.shape[1]

    def at(self, coordinate: tuple[int, ...]) -> str | None:
        value = self.cells[coordinate]
        if value is None:
            return None
        return str(value)

    def contains(self, coordinate: tuple[int, ...]) -> bool:
        return len(coordinate) == self.dimensions and all(
            0 <= value < size for value, size in zip(coordinate, self.shape)
        )

    def has_tiles(self) -> bool:
        return bool(np.any(self.cells != None))  # noqa: E711

    def render(self) -> str:
        if self.dimensions != 2:
            occupied = np.argwhere(self.cells != None)  # noqa: E711
            if occupied.size == 0:
                return f"{self.dimensions}D board with shape {self.shape}; no tiles."
            return "\n".join(
                f"{tuple(int(value) for value in coordinate)}: {self.at(tuple(coordinate))}"
                for coordinate in occupied
            )
        header = "    " + " ".join(str(col) for col in range(self.cols))
        lines = [header]
        for row in range(self.rows):
            rendered = " ".join(
                self.at((row, col)) if self.at((row, col)) is not None else "."
                for col in range(self.cols)
            )
            lines.append(f"{row}:  {rendered}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Move:
    start: tuple[int, ...]
    axis: int
    tokens: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    score: int
    failure_type: str | None = None
    message: str = ""


@dataclass(frozen=True)
class Scenario:
    dfa: DFA
    board: Board
    rack: tuple[str, ...]
    token_scores: dict[str, int]
    accepted_words: tuple[str, ...]
    legal_moves: tuple[Move, ...]
    reference_max_length: int
