from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import ScenarioRun
from .readable_json import dumps_readable_json
from .scenario_codec import scenario_run_from_json, scenario_run_to_json


def load_scenario_run(path: str | Path) -> ScenarioRun:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return scenario_run_from_json(data)


def write_scenario_run(path: str | Path, scenario_run: ScenarioRun) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        dumps_readable_json(scenario_run_to_json(scenario_run)),
        encoding="utf-8",
    )
    return output

