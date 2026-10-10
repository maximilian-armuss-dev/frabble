from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from ..domain.models import ScenarioRun
from .readable_json import dumps_readable_json
from .scenario_codec import scenario_run_from_json, scenario_run_to_json


def load_scenario_run(path: str | Path) -> ScenarioRun:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return scenario_run_from_json(data)


def write_scenario_run(path: str | Path, scenario_run: ScenarioRun) -> Path:
    """Atomically replace a scenario using the stable readable JSON format.

    Serialization or temporary-file write failures leave an existing artifact
    untouched. Temporary files are created beside the destination and cleaned
    up on failure, so readers only see complete scenarios.
    """
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the serializer byte-for-byte; readers see only complete files.
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=f".{output.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(dumps_readable_json(scenario_run_to_json(scenario_run)))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output

