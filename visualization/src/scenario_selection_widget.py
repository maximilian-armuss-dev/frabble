"""Compact selectors for scenario views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .artifact_catalog import ScenarioRecord, scenario_sources, scenarios
from .case_selection_widget import _axis_grid, _field, _panel


@dataclass
class ScenarioPickerSelection:
    widget: Any
    source: Any
    sequences: Any
    round_index: Any
    scenario: Any

    def selected_scenario(self) -> ScenarioRecord:
        record = self.scenario.value
        if record is None:
            raise ValueError("Choose a scenario first.")
        return record


def show_scenario_picker(*, dimensions: int = 2) -> ScenarioPickerSelection | None:
    """Select an existing scenario of the requested dimensionality."""
    from IPython.display import display
    from ipywidgets import Dropdown, HTML, Layout

    records_by_source = {
        source: tuple(record for record in scenarios(source) if record.dimensions == dimensions)
        for source in scenario_sources()
    }
    records_by_source = {
        source: records for source, records in records_by_source.items() if records
    }
    if not records_by_source:
        display(HTML(f"No {dimensions}D scenarios found. Generate or prepare a case set first."))
        return None

    sources = tuple(records_by_source)
    initial_source = (
        "generated/7r_final_merged"
        if dimensions == 2 and "generated/7r_final_merged" in sources
        else "evaluation/dimension_pilot"
        if dimensions == 3 and "evaluation/dimension_pilot" in sources
        else sources[0]
    )
    control_layout = Layout(width="calc(100% - 10px)", min_width="0")
    source = Dropdown(options=sources, value=initial_source, layout=control_layout)
    sequences = Dropdown(layout=control_layout)
    rounds = Dropdown(layout=control_layout)
    scenario = Dropdown(layout=control_layout)
    sequence_field = _field("Sequences on board", sequences)
    round_field = _field("Sampling round", rounds)
    scenario_field = _field("Scenario", scenario)
    updating = False

    def set_options(dropdown: Any, values: tuple[int, ...], label: str) -> None:
        previous = dropdown.value
        dropdown.options = tuple((label.format(value=value), value) for value in values)
        dropdown.value = previous if previous in values else values[0]

    def refresh(_change: object = None) -> None:
        nonlocal updating
        if updating:
            return
        updating = True
        try:
            records = records_by_source[source.value]
            structured = all(
                record.board_size is not None and record.sampling_round is not None
                for record in records
            )
            sequence_field.layout.display = "" if structured else "none"
            round_field.layout.display = "" if structured else "none"
            if structured:
                set_options(
                    sequences,
                    tuple(sorted({record.board_size for record in records})),
                    "{value} sequences",
                )
                matching_size = tuple(
                    record for record in records if record.board_size == sequences.value
                )
                set_options(
                    rounds,
                    tuple(sorted({record.sampling_round for record in matching_size})),
                    "Round {value}",
                )
                candidates = tuple(
                    record
                    for record in matching_size
                    if record.sampling_round == rounds.value
                )
            else:
                candidates = records
            scenario_field.layout.display = "" if len(candidates) > 1 else "none"
            previous = scenario.value
            scenario.options = tuple((record.name, record) for record in candidates)
            scenario.value = previous if previous in candidates else candidates[0]
        finally:
            updating = False

    for dropdown in (source, sequences, rounds):
        dropdown.observe(refresh, names="value")
    refresh()
    if 10 in dict(sequences.options).values():
        sequences.value = 10
    panel = _panel(
        HTML("<div style='font-size:20px; font-weight:700'>Select a scenario</div>"),
        _field("Source", source),
        _axis_grid(sequence_field, round_field, scenario_field),
    )
    display(panel)
    return ScenarioPickerSelection(panel, source, sequences, rounds, scenario)
