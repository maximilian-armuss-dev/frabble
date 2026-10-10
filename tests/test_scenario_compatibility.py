"""Historical artifacts retain move order without acquiring optimality claims."""

import copy
import json
from dataclasses import replace

import pytest

from support import FIXTURES
from src.generator.reconstruction import reconstruct_boards
from src.generator.scenario_codec import scenario_run_from_json, scenario_run_to_json


@pytest.fixture
def scenario():
    reference = json.loads(
        (FIXTURES / "generation_reference.json").read_text()
    )
    return copy.deepcopy(next(iter(reference["scenarios"].values())))


def test_legacy_scenario_round_trip_preserves_moves_and_boards(scenario):
    certified = scenario_run_from_json(scenario)
    scenario["schema_version"] = 1
    scenario.pop("initial_optimal_score")
    scenario.pop("initial_rack")
    for transition in scenario["transitions"]:
        transition.pop("optimal_score")
    legacy = scenario_run_from_json(scenario)
    assert legacy.initial_optimal_score is None
    assert all(t.optimal_score is None for t in legacy.transitions)
    assert [t.move for t in legacy.transitions] == [
        t.move for t in certified.transitions
    ]
    assert reconstruct_boards(legacy) == reconstruct_boards(certified)
    assert scenario_run_to_json(legacy) == scenario


@pytest.mark.parametrize(
    "field", ["initial_optimal_score", "initial_rack", "optimal_score"]
)
def test_certified_scenario_rejects_missing_certificates(scenario, field):
    target = scenario["transitions"][0] if field == "optimal_score" else scenario
    target.pop(field)
    with pytest.raises(ValueError, match="missing optimal scores"):
        scenario_run_from_json(scenario)


def test_writer_rejects_partial_certification(scenario):
    run = scenario_run_from_json(scenario)
    incomplete = replace(
        run,
        transitions=(
            replace(run.transitions[0], optimal_score=None),
            *run.transitions[1:],
        ),
    )
    with pytest.raises(ValueError, match="only some optimality certificates"):
        scenario_run_to_json(incomplete)
