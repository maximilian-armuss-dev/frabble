"""Small widget mocks for selecting prepared cases and overview ranges."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .board_figures import PROJECT_ROOT
from .case_playground import (
    PreparedCaseRecord,
    case_set_axes,
    list_prepared_cases,
    select_prepared_case,
)
from .overview_selection import completed_runs, filtered_run_aggregate


@dataclass
class CasePickerSelection:
    widget: Any
    case_set: Any
    dimensions: Any
    sequences: Any
    round_index: Any

    def selected_case(self) -> PreparedCaseRecord:
        return select_prepared_case(
            list_prepared_cases(self.case_set.value),
            self.dimensions.value,
            self.sequences.value,
            self.round_index.value,
        )


@dataclass
class OverviewFilterSelection:
    widget: Any
    case_set: Any
    run: Any | None
    dimension_group: Any
    sequence_group: Any
    round_group: Any

    def aggregate(self) -> tuple[Any, dict[str, Any], int]:
        if self.run is None or self.run.value is None:
            raise FileNotFoundError("Choose a case set with a completed evaluation run.")
        cases = list_prepared_cases(self.case_set.value)
        axes = case_set_axes(cases)

        def checked(group: Any, values: tuple[int, ...]) -> list[int]:
            return [value for value, box in zip(values, group.children) if box.value]

        return filtered_run_aggregate(
            cases,
            completed_runs(self.case_set.value),
            self.run.value,
            checked(self.dimension_group, axes.dimensions),
            checked(self.sequence_group, axes.visible_sequences),
            checked(self.round_group, axes.rounds),
        )


def _selectable_case_sets() -> tuple[str, ...]:
    """Legacy tier-based sets do not have the three coordinates used here."""
    evaluation_dir = PROJECT_ROOT / "outputs" / "evaluation"
    if not evaluation_dir.is_dir():
        return ()
    names = []
    for directory in sorted(evaluation_dir.iterdir()):
        if not directory.is_dir():
            continue
        first_case = next((directory / "cases").glob("*.json"), None)
        if first_case and "board_size" in json.loads(first_case.read_text()):
            names.append(directory.name)
    return tuple(names)


def _case_set_dropdown(case_sets: tuple[str, ...], default: str):
    from ipywidgets import Dropdown, Layout

    initial = default if default in case_sets else case_sets[0]
    return Dropdown(
        options=case_sets,
        value=initial,
        layout=Layout(width="calc(100% - 10px)", min_width="0"),
    )


def _field(label: str, control):
    from ipywidgets import HTML, Layout, VBox

    return VBox(
        (HTML(f"<b style='font-size:12px'>{label}</b>"), control),
        layout=Layout(width="100%", min_width="0"),
    )


def _panel(*children):
    from ipywidgets import Layout, VBox

    return VBox(
        children,
        layout=Layout(
            width="calc(100% - 42px)",
            max_width="638px",
            border="1px solid var(--jp-border-color2, #dbe2ec)",
            padding="20px",
        ),
    )


def _axis_grid(*fields):
    from ipywidgets import GridBox, Layout

    return GridBox(
        fields,
        layout=Layout(
            width="100%",
            grid_template_columns="repeat(auto-fit, minmax(165px, 1fr))",
            grid_gap="12px",
        ),
    )


def _show_case_picker(default_case_set: str) -> CasePickerSelection | None:
    """Display dependent dropdowns; selecting a puzzle never calls a model."""
    from IPython.display import display
    from ipywidgets import Dropdown, HTML, Layout

    case_sets = _selectable_case_sets()
    if not case_sets:
        display(HTML("No compatible prepared case sets found."))
        return None

    case_set = _case_set_dropdown(case_sets, default_case_set)
    dimensions = Dropdown(layout=Layout(width="calc(100% - 10px)", min_width="0"))
    sequences = Dropdown(layout=Layout(width="calc(100% - 10px)", min_width="0"))
    rounds = Dropdown(layout=Layout(width="calc(100% - 10px)", min_width="0"))
    updating = False

    def set_options(
        dropdown: Dropdown, values: tuple[int, ...], label_template: str
    ) -> None:
        previous = dropdown.value
        dropdown.options = tuple(
            (label_template.format(value=value), value) for value in values
        )
        dropdown.value = previous if previous in values else values[0]

    def refresh(_change: object = None) -> None:
        nonlocal updating
        if updating:
            return
        updating = True
        try:
            cases = list_prepared_cases(case_set.value)
            set_options(
                dimensions, tuple(sorted({case.dimensions for case in cases})), "{value}D"
            )
            matching_dimension = [
                case for case in cases if case.dimensions == dimensions.value
            ]
            set_options(
                sequences,
                tuple(sorted({case.visible_sequences for case in matching_dimension})),
                "{value} Sequences",
            )
            matching_size = [
                case
                for case in matching_dimension
                if case.visible_sequences == sequences.value
            ]
            set_options(
                rounds, tuple(sorted({case.sampling_round for case in matching_size})),
                "Round {value}",
            )
        finally:
            updating = False

    for dropdown in (case_set, dimensions, sequences, rounds):
        dropdown.observe(refresh, names="value")
    refresh()
    if 10 in dict(sequences.options).values():
        sequences.value = 10
    panel = _panel(
        HTML("<div style='font-size:20px; font-weight:700'>Select a puzzle</div>"),
        _field("Case Set", case_set),
        _axis_grid(
            _field("Dimension", dimensions),
            _field("Sequences on board", sequences),
            _field("Sampling round", rounds),
        ),
    )
    display(panel)
    return CasePickerSelection(panel, case_set, dimensions, sequences, rounds)


def show_case_picker() -> CasePickerSelection | None:
    """Show the puzzle selector used by the model playground."""
    return _show_case_picker("7r")


def show_case_picker_mock() -> CasePickerSelection | None:
    """Show the same selector with the dimension pilot as its initial set."""
    return _show_case_picker("dimension_pilot")


def _show_overview_filter(
    default_case_set: str, *, include_run: bool
) -> OverviewFilterSelection | None:
    """Show checkbox ranges and the number of prepared cases they include."""
    from IPython.display import display
    from ipywidgets import Checkbox, HTML, Layout, VBox

    case_sets = _selectable_case_sets()
    if not case_sets:
        display(HTML("No compatible prepared case sets found."))
        return None

    case_set = _case_set_dropdown(case_sets, default_case_set)
    run = None
    if include_run:
        from ipywidgets import Dropdown

        run = Dropdown(layout=Layout(width="calc(100% - 10px)", min_width="0"))
    dimension_group = VBox()
    sequence_group = VBox()
    round_group = VBox()
    count = HTML()
    cases = ()
    axes = None

    def selected(group: VBox, values: tuple[int, ...]) -> set[int]:
        return {value for value, box in zip(values, group.children) if box.value}

    def update_count(_change: object = None) -> None:
        included_dimensions = selected(dimension_group, axes.dimensions)
        included_sequences = selected(sequence_group, axes.visible_sequences)
        included_rounds = selected(round_group, axes.rounds)
        included = sum(
            case.dimensions in included_dimensions
            and case.visible_sequences in included_sequences
            and case.sampling_round in included_rounds
            for case in cases
        )
        count.value = (
            f"<span style='font-size:12px; opacity:.7'>"
            f"{included} of {len(cases)} prepared cases selected</span>"
        )

    def checkboxes(values: tuple[int, ...], label_template: str) -> tuple[Checkbox, ...]:
        items = []
        for value in values:
            box = Checkbox(
                value=True,
                description=label_template.format(value=value),
                indent=False,
                layout=Layout(width="100%"),
            )
            box.observe(update_count, names="value")
            items.append(box)
        return tuple(items)

    def refresh(_change: object = None) -> None:
        nonlocal cases, axes
        cases = list_prepared_cases(case_set.value)
        axes = case_set_axes(cases)
        dimension_group.children = checkboxes(axes.dimensions, "{value}D")
        sequence_group.children = checkboxes(
            axes.visible_sequences, "{value} Sequences"
        )
        round_group.children = checkboxes(axes.rounds, "Round {value}")
        if run is not None:
            completed = completed_runs(case_set.value)
            if completed:
                run.options = tuple(
                    (
                        f"#{number} · {len(record.models)} "
                        f"{'model' if len(record.models) == 1 else 'models'} · "
                        f"{(record.completed_at or record.created_at)[:16].replace('T', ' ')}",
                        number,
                    )
                    for number, record in enumerate(completed, start=1)
                )
                run.value = (
                    2 if case_set.value == "7r" and len(completed) >= 2 else 1
                )
                run.disabled = False
            else:
                run.options = (("No completed run", None),)
                run.disabled = True
        update_count()

    case_set.observe(refresh, names="value")
    refresh()
    children = [
        HTML("<div style='font-size:20px; font-weight:700'>Filter evaluation</div>"),
        _field("Case Set", case_set),
    ]
    if run is not None:
        children.append(_field("Evaluation run", run))
    children.extend(
        (
            _axis_grid(
                _field("Dimensions", dimension_group),
                _field("Sequences on board", sequence_group),
                _field("Sampling rounds", round_group),
            ),
            count,
        )
    )
    panel = _panel(*children)
    display(panel)
    return OverviewFilterSelection(
        panel, case_set, run, dimension_group, sequence_group, round_group
    )


def show_overview_filter() -> OverviewFilterSelection | None:
    """Show run and checkbox controls for the evaluation overview."""
    return _show_overview_filter("7r", include_run=True)


def show_overview_filter_mock() -> OverviewFilterSelection | None:
    """Show checkbox ranges without loading a run."""
    return _show_overview_filter("dimension_pilot", include_run=False)
