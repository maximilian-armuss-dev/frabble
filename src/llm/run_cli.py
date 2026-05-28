from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from ..formal.grammar.serialization import load_grammar
from ..formal.parsing import SubmittedMove, parse_submitted_move
from ..generator.reconstruction import board_before_transition
from ..generator.scenario_io import load_scenario_run
from .client import call_llm
from .evaluation import evaluate_granular
from .prompting import build_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a single scenario transition against an LLM and evaluate the response."
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Path to a scenario JSON file (e.g. outputs/generator_v1.json).",
    )
    parser.add_argument(
        "--transition",
        required=True,
        type=int,
        help="Transition index N to evaluate (0-indexed).",
    )
    parser.add_argument(
        "--model",
        required=False,
        help="Model name as registered in config/model_configs.yaml. Not required with --dry-run.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/runs",
        help="Directory to write the run log. Default: outputs/runs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the prompt but skip the LLM call and do not write any output.",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print the system and user prompts before calling the LLM.",
    )
    return parser


def _resolve_grammar_path(grammar_path: str, scenario_path: Path) -> Path:
    direct = Path(grammar_path)
    if direct.exists():
        return direct
    relative_to_scenario = scenario_path.parent / grammar_path
    if relative_to_scenario.exists():
        return relative_to_scenario
    raise FileNotFoundError(
        f"Grammar file not found at '{direct}' or '{relative_to_scenario}'."
    )


def main() -> None:
    args = build_parser().parse_args()

    if not args.dry_run and args.model is None:
        print("--model is required unless --dry-run is set.")
        raise SystemExit(1)

    scenario_path = Path(args.scenario)

    try:
        scenario_run = load_scenario_run(scenario_path)
    except Exception as exc:
        print(f"Failed to load scenario: {exc}")
        raise SystemExit(1) from exc

    n = args.transition
    total = len(scenario_run.transitions)
    if n < 0 or n >= total:
        print(
            f"Transition index {n} is out of range. "
            f"Scenario has {total} transitions (0 to {total - 1})."
        )
        raise SystemExit(1)

    grammar_path_str = str(scenario_run.config.get("grammar_path", ""))
    try:
        resolved = _resolve_grammar_path(grammar_path_str, scenario_path)
        language, _, _ = load_grammar(resolved)
    except Exception as exc:
        print(f"Failed to load grammar: {exc}")
        raise SystemExit(1) from exc

    board = board_before_transition(scenario_run, n)
    transition = scenario_run.transitions[n]
    rack = transition.rack

    system_prompt, user_prompt = build_prompt(board, transition, language)

    if args.show_prompt:
        print("=== SYSTEM PROMPT ===")
        print(system_prompt)
        print()
        print("=== USER PROMPT ===")
        print(user_prompt)
        print()

    if args.dry_run:
        print("Dry run complete — prompt built successfully, no LLM call made.")
        return

    print(f"Calling {args.model} for transition {n} of {scenario_path.name} ...")
    try:
        raw_response = call_llm(system_prompt, user_prompt, args.model)
    except Exception as exc:
        print(f"LLM call failed: {exc}")
        raise SystemExit(1) from exc

    submitted: SubmittedMove | None = None
    parse_error: str | None = None
    try:
        submitted = parse_submitted_move(raw_response)
    except Exception as exc:
        parse_error = str(exc)

    evaluation = evaluate_granular(board, language, rack, submitted, parse_error)

    timestamp = datetime.now()
    model_tag = args.model.replace("/", "-").replace(":", "-")
    output_filename = f"{scenario_path.stem}_t{n}_{model_tag}_{timestamp.strftime('%Y%m%dT%H%M%S')}.json"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename

    run_log = {
        "scenario_file": str(scenario_path),
        "transition_index": n,
        "model": args.model,
        "timestamp": timestamp.isoformat(),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_response": raw_response,
        "parsed_move": submitted.model_dump() if submitted is not None else None,
        "evaluation": evaluation.to_json(),
        "ground_truth_move": transition.move.to_json(),
    }

    output_path.write_text(json.dumps(run_log, indent=2, ensure_ascii=False), encoding="utf-8")

    status = "PASS" if evaluation.overall else "FAIL"
    print(f"Result: {status}")
    if not evaluation.overall:
        print(f"  Failure: [{evaluation.failure_type}] {evaluation.message}")
    print(f"  Rack usage: {evaluation.rack_symbols_used}/{len(rack)} ({evaluation.rack_usage_ratio:.0%})")
    print(f"  Log written to: {output_path}")


if __name__ == "__main__":
    main()
