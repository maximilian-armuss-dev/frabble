"""Small, high-level entry points used by the interactive notebooks."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .artifact_catalog import (
    display_attempt_catalog_for_run,
    display_evaluation_config_run_catalog,
    display_scenario_catalog,
    resolve_attempt_selection,
    resolve_evaluation_run_config_selection,
    resolve_scenario_selection,
)
from .board_figures import (
    animate_scenario_2d,
    load_scenario_json,
    load_scenario_letter_scores,
)
from .case_playground import (
    display_case_preview,
    display_case_set_axes,
    case_set_axes,
    list_prepared_cases,
    load_saved_case_attempt,
    prepare_selected_case,
    run_prepared_case,
    select_prepared_case,
)
from .evaluation_figures import (
    EvaluationAttemptContext,
    load_evaluation_attempt,
    load_evaluation_results,
)
from .overview_selection import completed_runs, display_completed_runs, filtered_run_aggregate
from .case_selection_widget import show_case_picker, show_overview_filter
from .notebook_workflows import open_model_playground, load_overview_selection
from .run_figures import (
    PreparedLLMTransition,
    display_llm_prompt,
    prepare_llm_transition,
)
from .scenario_selection_widget import ScenarioPickerSelection, show_scenario_picker


def select_evaluation_run(
    run_config: str,
    run: int | str = 1,
    *,
    limit: int = 10,
) -> dict[str, object]:
    """Show matching runs and load the selected aggregate."""
    show(
        display_evaluation_config_run_catalog(
            run_config,
            selected=run,
            limit=limit,
        )
    )
    run_dir = resolve_evaluation_run_config_selection(run_config, run)
    _, aggregate = load_evaluation_results(None, run_path=run_dir)
    return aggregate


def select_evaluation_attempt(
    run_config: str,
    run: int | str = 1,
    *,
    job_id: str | None = None,
    model: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    status: str | None = None,
    limit: int = 20,
) -> EvaluationAttemptContext:
    """Show matching runs and attempts, then load one selected attempt."""
    show(
        display_evaluation_config_run_catalog(
            run_config,
            selected=run,
            limit=10,
        )
    )
    run_dir = resolve_evaluation_run_config_selection(run_config, run)
    show(
        display_attempt_catalog_for_run(
            run_dir,
            model=model,
            board_size=board_size,
            sampling_round=sampling_round,
            status=status,
            limit=limit,
        )
    )
    attempt_path = resolve_attempt_selection(
        run_dir,
        job_id=job_id,
        model=model,
        board_size=board_size,
        sampling_round=sampling_round,
        status=status,
    )
    return load_evaluation_attempt(attempt_path)


def show_scenario_animation(
    source: str,
    *,
    name: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    limit: int = 10,
) -> object:
    """Show matching scenarios and animate one unambiguous selection."""
    show(
        display_scenario_catalog(
            source,
            name=name,
            board_size=board_size,
            sampling_round=sampling_round,
            limit=limit,
        )
    )
    path = resolve_scenario_selection(
        source,
        name=name,
        board_size=board_size,
        sampling_round=sampling_round,
    )
    scenario = load_scenario_json(path)
    return animate_scenario_2d(
        scenario,
        letter_scores=load_scenario_letter_scores(path),
        title=str(scenario["config_name"]),
    )


def show_selected_scenario_animation(selection: ScenarioPickerSelection) -> object:
    """Animate the scenario currently selected in the notebook picker."""
    path = selection.selected_scenario().path
    scenario = load_scenario_json(path)
    return animate_scenario_2d(
        scenario,
        letter_scores=load_scenario_letter_scores(path),
        title=str(scenario["config_name"]),
    )


def prepare_selected_model_run(
    source: str,
    *,
    transition_index: int,
    model_name: str,
    reasoning_effort: str,
    name: str | None = None,
    board_size: int | None = None,
    sampling_round: int | None = None,
    limit: int = 10,
) -> PreparedLLMTransition:
    """Select a scenario, prepare one model request, and show its prompt."""
    show(
        display_scenario_catalog(
            source,
            name=name,
            board_size=board_size,
            sampling_round=sampling_round,
            limit=limit,
        )
    )
    path = resolve_scenario_selection(
        source,
        name=name,
        board_size=board_size,
        sampling_round=sampling_round,
    )
    prepared = prepare_llm_transition(
        scenario_name=Path(path),
        transition_index=transition_index,
        model_name=model_name,
        reasoning_effort=reasoning_effort,
    )
    display_llm_prompt(prepared)
    return prepared


def show(value: object) -> None:
    from IPython.display import display

    display(value)


def show_all(values: Iterable[object]) -> None:
    """Display each figure or rich notebook object in order."""
    for value in values:
        show(value)
