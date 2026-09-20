from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from ..domain.board import Board
from ..domain.models import Symbol
from ..formal.language import StrictlyLocalLanguage


class LanguageRepresenter(Protocol):
    @property
    def name(self) -> str: ...

    def represent(self, language: StrictlyLocalLanguage) -> str: ...


class BoardRepresenter(Protocol):
    @property
    def name(self) -> str: ...

    def represent(self, board: Board) -> str: ...


class RackRepresenter(Protocol):
    @property
    def name(self) -> str: ...

    def represent(self, rack: tuple[Symbol, ...]) -> str: ...


class ForbiddenSnippetsLanguageRepresenter:
    @property
    def name(self) -> str:
        return "forbidden-snippets"

    def represent(self, language: StrictlyLocalLanguage) -> str:
        snippets = ", ".join(
            " ".join(snippet) for snippet in language.forbidden_snippets
        )
        return "\n".join(
            [
                f"Alphabet: {{{', '.join(language.alphabet)}}}",
                "Acceptance: use only alphabet symbols, have length "
                f">= {language.min_word_length}, and contain none of these "
                "contiguous snippets:",
                f"{{{snippets}}}",
            ]
        )


class ForbiddenSnippetsProductionRulesLanguageRepresenter:
    @property
    def name(self) -> str:
        return "forbidden-snippets-production-rules"

    def represent(self, language: StrictlyLocalLanguage) -> str:
        _, transitions = language._automaton_parts()
        steady_length = language.k - 1

        lines = [
            f"Language ID: {language.language_id}",
            f"Alphabet: {{{', '.join(language.alphabet)}}}",
            f"k: {language.k}, minimum word length: {language.min_word_length}",
            "",
            "Production rules (context → allowed next symbols):",
        ]

        if steady_length == 0:
            # k=1: single symbols can themselves be forbidden
            allowed = sorted(transitions.get((), {}).keys())
            lines.append(f"  [any position] → {' | '.join(allowed)}")
        else:
            if steady_length > 1:
                lines.append(
                    f"  (first {steady_length} symbols are unconstrained — any from alphabet)"
                )
            for state in sorted(transitions, key=lambda s: (len(s), s)):
                if len(state) != steady_length:
                    continue
                allowed = sorted(transitions[state])
                if not allowed:
                    continue
                lines.append(f"  {' '.join(state)} → {' | '.join(allowed)}")

        lines += [
            "",
            f"A sequence is accepted iff it has length ≥ {language.min_word_length}"
            " and every symbol follows the rule for its context.",
        ]

        return "\n".join(lines)


class GenericProductionRulesLanguageRepresenter:
    @property
    def name(self) -> str:
        return "generic-production-rules"

    def represent(self, language: StrictlyLocalLanguage) -> str:
        dfa = language.to_dfa()

        # BFS from start state to assign readable labels Q0, Q1, Q2, ...
        # Dead/sink states (no accepting state reachable) are excluded.
        labels: dict[str, str] = {}
        queue: deque[str] = deque([dfa.start_state])
        visited: set[str] = {dfa.start_state}
        while queue:
            state = queue.popleft()
            labels[state] = f"Q{len(labels)}"
            for symbol in sorted(dfa.alphabet):
                nxt = dfa.transitions.get(state, {}).get(symbol)
                if nxt and nxt not in visited and nxt in dfa.states:
                    # Only follow transitions that lead somewhere reachable
                    # and are not the dead state (sink with no accepting successor)
                    if _can_reach_accepting(nxt, dfa):
                        visited.add(nxt)
                        queue.append(nxt)

        lines = [
            f"Language ID: {language.language_id}",
            f"Alphabet: {{{', '.join(dfa.alphabet)}}}",
            f"Start: {labels[dfa.start_state]}",
            "",
            "Productions:",
        ]

        for state, label in labels.items():
            parts: list[str] = []
            for symbol in sorted(dfa.alphabet):
                nxt = dfa.transitions.get(state, {}).get(symbol)
                if nxt and nxt in labels:
                    parts.append(f"{symbol} {labels[nxt]}")
            if state in dfa.accepting_states:
                parts.append("ε")
            if parts:
                lines.append(f"  {label} → {' | '.join(parts)}")

        lines += [
            "",
            "ε means the sequence may end at that state.",
        ]

        return "\n".join(lines)


def _can_reach_accepting(start: str, dfa) -> bool:
    visited: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        state = queue.popleft()
        if state in dfa.accepting_states:
            return True
        if state in visited:
            continue
        visited.add(state)
        for nxt in dfa.transitions.get(state, {}).values():
            if nxt not in visited:
                queue.append(nxt)
    return False


class CoordinatesJsonBoardRepresenter:
    @property
    def name(self) -> str:
        return "coordinates-json"

    def represent(self, board: Board) -> str:
        data = {
            "dimensions": board.dimensions,
            "occupied": [
                {"coord": list(coord), "symbol": symbol}
                for coord, symbol in board.occupied_sorted()
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


class SequencesJsonBoardRepresenter:
    @property
    def name(self) -> str:
        return "sequences-json"

    def represent(self, board: Board) -> str:
        covered = {
            coord
            for segment in board.segments
            for coord in board.coords_for_slot(
                segment.start, segment.axis, len(segment.sequence)
            )
        }
        unrepresented = set(board.cells) - covered
        if unrepresented:
            raise ValueError(
                "Cannot represent board as sequences: "
                f"{len(unrepresented)} occupied cells belong to no segment."
            )

        segments = sorted(
            board.segments,
            key=lambda segment: (segment.axis, segment.start, segment.sequence),
        )
        sequences = [
            {
                "start": list(segment.start),
                "axis": segment.axis,
                "sequence": list(segment.sequence),
            }
            for segment in segments
        ]
        if not sequences:
            return "[]"
        rendered = [
            json.dumps(sequence, ensure_ascii=False)
            for sequence in sequences
        ]
        return "[\n  " + ",\n  ".join(rendered) + "\n]"


class SymbolJsonRackRepresenter:
    @property
    def name(self) -> str:
        return "symbol-json"

    def represent(self, rack: tuple[Symbol, ...]) -> str:
        return json.dumps(list(rack), ensure_ascii=False)


@dataclass(frozen=True)
class RepresenterConfig:
    language: LanguageRepresenter = field(default_factory=ForbiddenSnippetsLanguageRepresenter)
    board: BoardRepresenter = field(default_factory=SequencesJsonBoardRepresenter)
    rack: RackRepresenter = field(default_factory=SymbolJsonRackRepresenter)


LANGUAGE_REPRESENTERS: dict[str, LanguageRepresenter] = {
    r.name: r for r in [
        ForbiddenSnippetsLanguageRepresenter(),
        ForbiddenSnippetsProductionRulesLanguageRepresenter(),
        GenericProductionRulesLanguageRepresenter(),
    ]
}

BOARD_REPRESENTERS: dict[str, BoardRepresenter] = {
    r.name: r
    for r in [
        SequencesJsonBoardRepresenter(),
        CoordinatesJsonBoardRepresenter(),
    ]
}

RACK_REPRESENTERS: dict[str, RackRepresenter] = {
    r.name: r for r in [SymbolJsonRackRepresenter()]
}
