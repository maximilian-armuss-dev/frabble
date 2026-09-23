"""Select one saved evaluation run and rebuild summaries for case axes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.evaluation.run_artifacts import load_attempts
from src.evaluation.result_aggregation import build_aggregate

from .artifact_catalog import EvaluationRunRecord, _display_table, evaluation_runs
from .board_figures import PROJECT_ROOT
from .case_playground import PreparedCaseRecord, case_set_axes


def completed_runs(
    case_set: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[EvaluationRunRecord, ...]:
    return tuple(
        run
        for run in evaluation_runs(case_set, project_root=project_root)
        if run.status == "complete" and (run.path / "aggregate.json").exists()
    )


def display_completed_runs(
    runs: tuple[EvaluationRunRecord, ...], *, case_set: str
) -> object:
    return _display_table(
        f"Completed evaluation runs · {case_set}",
        ("#", "run config", "completed", "models", "run ID"),
        (
            (
                str(number),
                run.run_config or "—",
                run.completed_at or "—",
                ", ".join(run.models) or "—",
                run.run_id,
            )
            for number, run in enumerate(runs, start=1)
        ),
    )


def filtered_run_aggregate(
    cases: tuple[PreparedCaseRecord, ...],
    runs: tuple[EvaluationRunRecord, ...],
    run_number: int,
    dimensions: list[int],
    visible_sequences: list[int],
    rounds: list[int],
) -> tuple[EvaluationRunRecord, dict[str, Any], int]:
    """Recompute the aggregate from attempts in the selected run and case slice."""
    if (
        isinstance(run_number, bool)
        or not isinstance(run_number, int)
        or not 1 <= run_number <= len(runs)
    ):
        raise ValueError(f"RUN must be one of 1..{len(runs)}.")
    axes = case_set_axes(cases)
    for label, values, available in (
        ("DIMENSIONS", dimensions, axes.dimensions),
        ("SEQUENCES_ON_BOARD", visible_sequences, axes.visible_sequences),
        ("ROUNDS", rounds, axes.rounds),
    ):
        if (
            not isinstance(values, list)
            or not values
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in values
            )
            or len(values) != len(set(values))
            or not set(values).issubset(available)
        ):
            raise ValueError(
                f"{label} must contain distinct values from {list(available)}."
            )

    selected = {
        case.case_id: case
        for case in cases
        if case.dimensions in dimensions
        and case.visible_sequences in visible_sequences
        and case.sampling_round in rounds
    }
    if not selected:
        raise ValueError("No prepared cases match those three axis lists.")

    run = runs[run_number - 1]
    attempts = []
    for attempt in load_attempts(run.path):
        case_id = attempt.get("case_id") or Path(str(attempt.get("case_file") or "")).stem
        case = selected.get(str(case_id))
        if case is None:
            continue
        enriched = dict(attempt)
        enriched.update(
            dimensions=case.dimensions,
            board_size=case.visible_sequences,
            sampling_round=case.sampling_round,
        )
        attempts.append(enriched)
    if not attempts:
        raise FileNotFoundError(
            "The selected run has no attempts for those dimensions, sequence counts, "
            "and rounds. Choose another run or expand the lists."
        )
    return run, build_aggregate(attempts), len(attempts)
