"""Small real-process preparation probe; also captures the pre-change fixture."""
from __future__ import annotations

import argparse
import dataclasses
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.optimality import _enumerate_slots
from src.evaluation.config import CaseSetConfig
from src.evaluation.prepare import prepare_case_set
from src.formal.grammar.serialization import load_grammar
from src.generator.scenario_io import load_scenario_run


def reference_config() -> CaseSetConfig:
    return CaseSetConfig(
        config_name="reference", generation_config="evaluation_base",
        grammar_config="evaluation_base_grammar", root_seed=7,
        sampling_rounds=2, dimensions=[2, 5, 10], board_sizes=[3],
    )


def capture(root: Path) -> dict:
    scenarios = {}
    slots = {}
    for path in sorted((root / "reference" / "scenarios").glob("*.json")):
        data = json.loads(path.read_text())
        run = load_scenario_run(path)
        language, _, _ = load_grammar(data["config"]["grammar_path"])
        for field in ("grammar_path", "output_path"):
            data["config"][field] = Path(data["config"][field]).name
        scenarios[path.stem] = data
        board = run.initial_board
        slot_steps = []
        for transition in run.transitions:
            slot_steps.append([
                {**dataclasses.asdict(slot), "domains": [sorted(d) for d in slot.domains]}
                for slot in _enumerate_slots(
                    board, language, transition.rack, language.letter_score_map()
                )
            ])
            board = board.place(transition.move)
        slots[path.stem] = slot_steps
    return {"scenarios": scenarios, "slots": slots}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()
    options = {} if args.workers is None else {"workers": args.workers}
    starts, totals, exits = {}, {}, []

    @contextmanager
    def progress(scenario_id, total):
        assert scenario_id not in starts
        starts[scenario_id] = total
        totals[scenario_id] = 0

        def update(amount):
            assert amount > 0
            totals[scenario_id] += amount

        try:
            yield update
        finally:
            exits.append(scenario_id)

    with patch("src.evaluation.prepare.EVALUATION_OUTPUT_DIR", args.root):
        if args.cli:
            from src.evaluation.cli import cmd_prepare
            argv = ["prepare", "--config", "reference"]
            if args.workers is not None:
                argv.extend(["--workers", str(args.workers)])
            with (
                patch.object(sys, "argv", argv),
                patch("src.evaluation.cli.load_case_set_config", return_value=reference_config()),
                patch("src.evaluation.cli._generation_progress", progress),
            ):
                cmd_prepare()
        else:
            prepare_case_set(reference_config(), generation_progress_factory=progress, **options)
    assert starts == totals
    assert sorted(exits) == sorted(starts)
    args.output.write_text(json.dumps(capture(args.root), sort_keys=True))


if __name__ == "__main__":
    main()
