from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import random

from pathlib import Path

from ..benchmark.scoring import BoardScoring
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
from ..formal.grammar.serialization import load_grammar
from ..formal.slot_csp import SlotCSP
from ..formal.validation import extends_existing_sequence_in_any_axis, validate_move_detailed
from .candidates import top_anchors, top_templates
from .config import GeneratorConfig, PROJECT_ROOT
from .scenario_io import write_scenario_run


class GenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LengthFailure:
    length: int
    reason: str
    anchor_count: int
    template_count: int
    solver_attempt_count: int
    attempt_statuses: tuple[str, ...]


@dataclass(frozen=True)
class TemplateSearchResult:
    board: Board
    transition: ScenarioTransition | None
    solved: bool
    reason: str
    solver_attempts: tuple[SolverAttempt, ...]


class ScenarioGenerator:
    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        grammar_path = Path(config.grammar_path)
        if not grammar_path.is_absolute():
            grammar_path = PROJECT_ROOT / grammar_path
        self.language, _cfg, self.grammar_name = load_grammar(grammar_path)
        self.solver = SlotCSP(self.language, rng=self.rng)

    def generate(
        self,
        progress_callback: Callable[[int], None] | None = None,
    ) -> ScenarioRun:
        initial_board = self._initial_board()
        board = initial_board
        transitions: list[ScenarioTransition] = []

        while len(transitions) < self.config.target_witness_count:
            board, transition, failures = self._generate_next_transition(board)
            if transition is None:
                raise GenerationError(
                    _format_generation_failure(
                        produced=len(transitions),
                        target=self.config.target_witness_count,
                        failures=failures,
                    )
                )
            transitions.append(transition)
            if progress_callback is not None:
                progress_callback(1)

        return ScenarioRun(
            config_name=self.config.config_name,
            config=self.config.model_dump(mode="json"),
            seed=self.config.seed,
            grammar_name=self.grammar_name,
            forbidden_snippets=self.language.forbidden_snippets,
            initial_board=initial_board,
            transitions=tuple(transitions),
        )

    def _generate_next_transition(
        self,
        board: Board,
    ) -> tuple[Board, ScenarioTransition | None, tuple[LengthFailure, ...]]:
        failures: list[LengthFailure] = []
        centroid = BoardScoring.centroid(board)
        remaining_lengths = list(
            range(
                self.config.length_distribution.start,
                self.config.length_distribution.end + 1,
            )
        )
        while remaining_lengths:
            sampled_length = _pop_random(self.rng, remaining_lengths)
            anchor_candidates = top_anchors(
                board,
                sampled_length,
                self.config.max_anchor_count,
                self.config.scoring,
                centroid,
            )
            if not anchor_candidates:
                failures.append(
                    LengthFailure(
                        length=sampled_length,
                        reason="no_anchor_candidates",
                        anchor_count=0,
                        template_count=0,
                        solver_attempt_count=0,
                        attempt_statuses=(),
                    )
                )
                continue

            attempts: tuple[SolverAttempt, ...] = ()
            template_count = 0
            expanded_anchor_count = 0
            seen_slots: set[tuple[Coord, int, int]] = set()
            result: TemplateSearchResult | None = None
            for start in range(0, len(anchor_candidates), self.config.top_anchor_count):
                remaining_budget = self.config.top_template_count - len(attempts)
                if remaining_budget <= 0:
                    break
                anchor_batch = anchor_candidates[start : start + self.config.top_anchor_count]
                expanded_anchor_count += len(anchor_batch)
                template_candidates = top_templates(
                    board,
                    anchor_batch,
                    sampled_length,
                    remaining_budget,
                    self.config.scoring,
                    prune=lambda template: extends_existing_sequence_in_any_axis(
                        board,
                        template.covered_coords,
                        template.axis,
                        self.language,
                    ),
                    domains_for_template=lambda template: self._domains_for_template(
                        board, template
                    ),
                    seen_slots=seen_slots,
                    centroid=centroid,
                )
                if not template_candidates:
                    continue
                template_count += len(template_candidates)
                result = self._try_templates(
                    board,
                    sampled_length,
                    template_candidates,
                    previous_attempts=attempts,
                )
                attempts = result.solver_attempts
                if result.solved:
                    if result.transition is None:
                        raise GenerationError("Solved template search returned no transition.")
                    return result.board, result.transition, tuple(failures)

            if template_count == 0:
                failures.append(
                    LengthFailure(
                        length=sampled_length,
                        reason="no_template_candidates",
                        anchor_count=expanded_anchor_count,
                        template_count=0,
                        solver_attempt_count=0,
                        attempt_statuses=(),
                    )
                )
                continue
            failures.append(
                LengthFailure(
                    length=sampled_length,
                    reason=_template_failure_reason(list(attempts)),
                    anchor_count=expanded_anchor_count,
                    template_count=template_count,
                    solver_attempt_count=len(attempts),
                    attempt_statuses=tuple(
                        attempt.status for attempt in attempts
                    ),
                )
            )

        return board, None, tuple(failures)

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

    def _try_templates(
        self,
        board: Board,
        sampled_length: int,
        top_templates: tuple[TemplateCandidate, ...],
        *,
        previous_attempts: tuple[SolverAttempt, ...] = (),
    ) -> TemplateSearchResult:
        attempts: list[SolverAttempt] = list(previous_attempts)
        for candidate in top_templates:
            domains = (
                [set(domain) for domain in candidate.domains]
                if candidate.domains
                else self._domains_for_template(board, candidate.template)
            )
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
            report = validate_move_detailed(board, self.language, rack, move)
            if not report.overall:
                attempts.append(SolverAttempt(candidate.template, "validator_failed", sequence))
                if report.failure_type in {"word_extension", "invalid_main_word"}:
                    continue
                raise GenerationError(f"Generated move failed validation: {report.result}")

            next_board = board.place(move)
            attempts.append(SolverAttempt(candidate.template, "solved", sequence))
            placed = _placed_cells(board, move)
            search_log = SearchLog(
                sampled_length=sampled_length,
                solver_attempts=tuple(attempts),
            )
            return TemplateSearchResult(
                board=next_board,
                transition=ScenarioTransition(
                    rack=rack,
                    move=move,
                    placed=placed,
                    search_log=search_log,
                ),
                solved=True,
                reason="solved",
                solver_attempts=tuple(attempts),
            )

        return TemplateSearchResult(
            board=board,
            transition=None,
            solved=False,
            reason=_template_failure_reason(attempts),
            solver_attempts=tuple(attempts),
        )

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


def _pop_random(rng: random.Random, values: list[int]) -> int:
    index = rng.randrange(len(values))
    return values.pop(index)


def _template_failure_reason(attempts: list[SolverAttempt]) -> str:
    statuses = {attempt.status for attempt in attempts}
    if statuses == {"no_solution"}:
        return "no_solver_solution"
    if statuses == {"validator_failed"}:
        return "validator_rejected_all"
    return "templates_exhausted"


def _format_generation_failure(
    *,
    produced: int,
    target: int,
    failures: tuple[LengthFailure, ...],
) -> str:
    lines = [
        f"Generator produced {produced} of {target} target witnesses.",
        "All lengths in length_distribution were tried once for the current board state.",
    ]
    if failures:
        lines.append("Failure summary by sampled length:")
        for failure in sorted(failures, key=lambda item: item.length):
            status_summary = _status_summary(failure.attempt_statuses)
            detail = (
                f"length={failure.length}: {failure.reason}; "
                f"anchors={failure.anchor_count}, templates={failure.template_count}, "
                f"solver_attempts={failure.solver_attempt_count}"
            )
            if status_summary:
                detail += f", statuses={status_summary}"
            lines.append(f"- {detail}")
    lines.append(_failure_suggestion(failures))
    return "\n".join(lines)


def _status_summary(statuses: tuple[str, ...]) -> str:
    if not statuses:
        return ""
    counts = {status: statuses.count(status) for status in sorted(set(statuses))}
    return ", ".join(f"{status}:{count}" for status, count in counts.items())


def _failure_suggestion(failures: tuple[LengthFailure, ...]) -> str:
    reasons = {failure.reason for failure in failures}
    if "no_anchor_candidates" in reasons:
        return (
            "Suggestion: the board has no available cross-axis anchors for at least "
            "one length; check dimensions or the generated board geometry."
        )
    if reasons == {"no_template_candidates"}:
        return (
            "Suggestion: increase max_anchor_count if configured, widen "
            "length_distribution, or relax feasibility/scoring constraints; "
            "all expanded anchors were pruned before solving."
        )
    if reasons <= {"no_solver_solution", "templates_exhausted", "validator_rejected_all"}:
        return (
            "Suggestion: increase top_template_count or max_anchor_count if configured, "
            "widen length_distribution, or relax the language/scoring constraints."
        )
    return (
        "Suggestion: inspect the per-length reasons above; likely config levers are "
        "top_template_count, max_anchor_count, length_distribution, and scoring."
    )
