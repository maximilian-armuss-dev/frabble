from __future__ import annotations

import random
from pathlib import Path

from ..domain.board import Board
from ..domain.models import (
    Coord,
    Move,
    ScenarioRun,
    ScenarioTransition,
    SearchLog,
    SlotTemplate,
    SolverAttempt,
    Symbol,
    TemplateCandidate,
)
from ..formal.automata import enumerate_accepted_sequences
from ..formal.language import StrictlyLocalLanguage
from ..formal.slot_csp import SlotCSP
from ..formal.validation import validate_move
from .candidates import top_anchors, top_templates
from .config import GeneratorConfig, PROJECT_ROOT
from .scenario_io import write_scenario_run


class GenerationError(RuntimeError):
    pass


class ScenarioGenerator:
    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self.language = StrictlyLocalLanguage(
            language_id=config.language.language_id,
            alphabet=config.language.alphabet,
            k=config.language.k,
            forbidden_snippets=config.language.forbidden_snippets,
            min_word_length=config.language.min_word_length,
        )
        self.solver = SlotCSP(self.language)

    def generate(self) -> ScenarioRun:
        initial_board = self._initial_board()
        board = initial_board
        transitions: list[ScenarioTransition] = []
        failed_searches = 0

        while (
            len(transitions) < self.config.target_witness_count
            and failed_searches < self.config.failure_budget
        ):
            sampled_length = self._sample_length()
            top_anchor_candidates = top_anchors(
                board,
                sampled_length,
                self.config.top_anchor_count,
            )
            top_template_candidates = top_templates(
                board,
                top_anchor_candidates,
                sampled_length,
                self.config.top_template_count,
            )
            board, transition, solved = self._try_templates(
                board,
                sampled_length,
                top_template_candidates,
            )
            if solved:
                transitions.append(transition)
                failed_searches = 0
            else:
                failed_searches += 1

        if not transitions:
            raise GenerationError(
                "Generator did not produce any witness before budget exhaustion."
            )

        return ScenarioRun(
            config_name=self.config.config_name,
            config=self.config.model_dump(mode="json"),
            seed=self.config.seed,
            language_id=self.language.language_id,
            forbidden_snippets=self.language.forbidden_snippets,
            initial_board=initial_board,
            transitions=tuple(transitions),
        )

    def write(self, scenario_run: ScenarioRun) -> Path:
        output = Path(self.config.output_path)
        if not output.is_absolute():
            output = PROJECT_ROOT / output
        return write_scenario_run(output, scenario_run)

    def _initial_board(self) -> Board:
        sequences = enumerate_accepted_sequences(self.language, self.config.initial_word_length)
        if not sequences:
            raise GenerationError("Configured initial_word_length has no accepted sequence.")
        sequence = self.rng.choice(sequences)
        start = tuple(
            -(self.config.initial_word_length // 2) if dim == self.config.initial_word_axis else 0
            for dim in range(self.config.dimensions)
        )
        move = Move(start=start, axis=self.config.initial_word_axis, sequence=sequence)
        return Board.empty(self.config.dimensions).place(move)

    def _sample_length(self) -> int:
        entries = self.config.length_distribution
        total_weight = sum(entry.weight for entry in entries)
        threshold = self.rng.randrange(total_weight)
        running = 0
        for entry in entries:
            running += entry.weight
            if threshold < running:
                return entry.length
        raise GenerationError("Length sampling failed despite a non-empty distribution.")

    def _try_templates(
        self,
        board: Board,
        sampled_length: int,
        top_templates: tuple[TemplateCandidate, ...],
    ) -> tuple[Board, ScenarioTransition, bool]:
        attempts: list[SolverAttempt] = []
        for candidate in top_templates:
            domains = self._domains_for_template(board, candidate.template)
            sequence = self.solver.solve(domains)
            if sequence is None:
                attempts.append(SolverAttempt(candidate.template, "no_solution", None))
                continue

            move = Move(
                start=candidate.template.start,
                axis=candidate.template.axis,
                sequence=sequence,
            )
            rack = self._rack_for_move(board, move)
            result = validate_move(board, self.language, rack, move)
            if not result.ok:
                attempts.append(SolverAttempt(candidate.template, "validator_failed", sequence))
                raise GenerationError(f"Generated move failed validation: {result}")

            next_board = board.place(move)
            attempts.append(SolverAttempt(candidate.template, "solved", sequence))
            placed = _placed_cells(board, move)
            search_log = SearchLog(
                sampled_length=sampled_length,
                solver_attempts=tuple(attempts),
            )
            return (
                next_board,
                ScenarioTransition(
                    rack=rack,
                    move=move,
                    placed=placed,
                    search_log=search_log,
                ),
                True,
            )

        search_log = SearchLog(
            sampled_length=sampled_length,
            solver_attempts=tuple(attempts),
        )
        empty_move = Move(start=(0, 0), axis=0, sequence=())
        empty_transition = ScenarioTransition((), empty_move, (), search_log)
        return board, empty_transition, False

    def _domains_for_template(
        self,
        board: Board,
        template: SlotTemplate,
    ) -> list[set[Symbol]]:
        analysis = board.analyze_slot(template)
        if not analysis.valid_geometry:
            raise GenerationError("Template reached solver despite invalid geometry.")
        domains = [set(self.language.alphabet) for _ in range(template.length)]
        for index, symbol in analysis.fixed_symbols.items():
            domains[index] = {symbol}
        domains[template.anchor_index] = {template.anchor_symbol}
        for index, coord in enumerate(template.covered_coords):
            if board.get(coord) is not None:
                continue
            domains[index] = self._restrict_domain_by_cross_words(
                board,
                coord,
                template.axis,
                domains[index],
            )
        return domains

    def _restrict_domain_by_cross_words(
        self,
        board: Board,
        coord: Coord,
        slot_axis: int,
        domain: set[Symbol],
    ) -> set[Symbol]:
        restricted = set(domain)
        for axis in range(board.dimensions):
            if axis == slot_axis:
                continue
            prefix, suffix = _cross_context(board, coord, axis)
            if not prefix and not suffix:
                continue
            restricted = {
                symbol
                for symbol in restricted
                if self.language.accepts(prefix + (symbol,) + suffix)
            }
        return restricted

    def _rack_for_move(self, board: Board, move: Move) -> tuple[Symbol, ...]:
        needed = [
            symbol
            for coord, symbol in zip(move.coords(), move.sequence, strict=True)
            if board.get(coord) is None
        ]
        fillers = [
            self.rng.choice(self.language.alphabet)
            for _ in range(self.config.additional_rack_noise)
        ]
        return tuple(sorted(needed + fillers))


def _cross_context(
    board: Board,
    coord: Coord,
    axis: int,
) -> tuple[tuple[Symbol, ...], tuple[Symbol, ...]]:
    prefix: list[Symbol] = []
    cursor = _advance(coord, axis, -1)
    while board.get(cursor) is not None:
        prefix.append(str(board.get(cursor)))
        cursor = _advance(cursor, axis, -1)
    prefix.reverse()

    suffix: list[Symbol] = []
    cursor = _advance(coord, axis, 1)
    while board.get(cursor) is not None:
        suffix.append(str(board.get(cursor)))
        cursor = _advance(cursor, axis, 1)
    return tuple(prefix), tuple(suffix)


def _advance(coord: Coord, axis: int, offset: int) -> Coord:
    return tuple(value + (offset if dim == axis else 0) for dim, value in enumerate(coord))


def _placed_cells(board: Board, move: Move) -> tuple[tuple[Coord, Symbol], ...]:
    return tuple(
        (coord, symbol)
        for coord, symbol in zip(move.coords(), move.sequence, strict=True)
        if board.get(coord) is None
    )
