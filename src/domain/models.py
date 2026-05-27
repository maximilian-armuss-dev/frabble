from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

Coord = tuple[int, ...]
Symbol = str
SegmentId = int


@dataclass(frozen=True)
class DFA:
    alphabet: tuple[Symbol, ...]
    states: tuple[str, ...]
    start_state: str
    accepting_states: frozenset[str]
    transitions: Mapping[str, Mapping[Symbol, str]]
    grammar_hint: str

    def accepts(self, symbols: Sequence[Symbol] | str) -> bool:
        sequence = tuple(symbols) if not isinstance(symbols, str) else tuple(symbols)
        state = self.start_state
        for symbol in sequence:
            if symbol not in self.alphabet:
                return False
            target = self.transitions[state].get(symbol)
            if target is None:
                return False
            state = target
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
                f"{symbol}->{self.transitions[state][symbol]}"
                for symbol in self.alphabet
                if symbol in self.transitions[state]
            )
            lines.append(f"- {state}: {transitions}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Segment:
    start: Coord
    axis: int
    sequence: tuple[Symbol, ...]


@dataclass(frozen=True)
class SlotTemplate:
    anchor_coord: Coord
    anchor_symbol: Symbol
    axis: int
    length: int
    anchor_index: int
    start: Coord
    covered_coords: tuple[Coord, ...]


@dataclass(frozen=True)
class SlotAnalysis:
    valid_geometry: bool
    fixed_symbols: Mapping[int, Symbol]
    has_overlap: bool
    extends_existing_word: bool
    conflicts: tuple[Coord, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixed_symbols", MappingProxyType(dict(self.fixed_symbols)))


@dataclass(frozen=True)
class Move:
    start: Coord
    axis: int
    sequence: tuple[Symbol, ...]

    def coords(self) -> tuple[Coord, ...]:
        return tuple(
            tuple(
                value + (offset if dim == self.axis else 0)
                for dim, value in enumerate(self.start)
            )
            for offset in range(len(self.sequence))
        )

    def to_json(self) -> dict[str, object]:
        return {
            "start": list(self.start),
            "axis": self.axis,
            "sequence": list(self.sequence),
        }


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    failure_type: str | None = None
    message: str = ""


@dataclass(frozen=True)
class AnchorCandidate:
    coord: Coord
    symbol: Symbol
    axis: int
    score: float
    distance_to_centroid: float
    free_cross_axis_span: int

    def to_json(self) -> dict[str, object]:
        return {
            "coord": list(self.coord),
            "symbol": self.symbol,
            "axis": self.axis,
            "score": self.score,
            "distance_to_centroid": self.distance_to_centroid,
            "free_cross_axis_span": self.free_cross_axis_span,
        }


@dataclass(frozen=True)
class TemplateCandidate:
    template: SlotTemplate
    score: float
    distance_to_centroid: float
    domains: tuple[frozenset[Symbol], ...] = ()
    domain_slack: int = 0

    def to_json(self) -> dict[str, object]:
        return {
            "template": {
                "anchor_coord": list(self.template.anchor_coord),
                "anchor_symbol": self.template.anchor_symbol,
                "axis": self.template.axis,
                "length": self.template.length,
                "anchor_index": self.template.anchor_index,
                "start": list(self.template.start),
                "covered_coords": [list(coord) for coord in self.template.covered_coords],
            },
            "score": self.score,
            "distance_to_centroid": self.distance_to_centroid,
            "domain_slack": self.domain_slack,
        }


@dataclass(frozen=True)
class SolverAttempt:
    template: SlotTemplate
    status: str
    sequence: tuple[Symbol, ...] | None

    def to_json(self) -> dict[str, object]:
        return {
            "template": TemplateCandidate(self.template, 0.0, 0.0).to_json()["template"],
            "status": self.status,
            "sequence": list(self.sequence) if self.sequence is not None else None,
        }


@dataclass(frozen=True)
class SearchLog:
    sampled_length: int
    solver_attempts: tuple[SolverAttempt, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "sampled_length": self.sampled_length,
            "solver_attempts": [attempt.to_json() for attempt in self.solver_attempts],
        }


@dataclass(frozen=True)
class ScenarioTransition:
    rack: tuple[Symbol, ...]
    move: Move
    placed: tuple[tuple[Coord, Symbol], ...]
    search_log: SearchLog | None


@dataclass(frozen=True)
class ScenarioRun:
    config_name: str
    config: Mapping[str, object]
    seed: int
    grammar_name: str
    forbidden_snippets: tuple[tuple[Symbol, ...], ...]
    initial_board: "Board" #TODO is this intended?
    transitions: tuple[ScenarioTransition, ...]


@dataclass(frozen=True)
class BoardConfiguration:
    dimensions: int
    occupied: tuple[tuple[Coord, Symbol], ...]
    rack: tuple[Symbol, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "dimensions": self.dimensions,
            "occupied": [
                {"coord": list(coord), "symbol": symbol}
                for coord, symbol in self.occupied
            ],
            "rack": list(self.rack),
        }
