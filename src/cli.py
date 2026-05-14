from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark.generation import generate_scenario
from .benchmark.prompting import build_prompt
from .benchmark.scoring import optimal_move, optimal_score
from .domain.models import Scenario
from .domain.visualization import render_dfa_png
from .formal.parsing import parse_move
from .formal.validation import validate_move
from .llm.client import call_llm


def print_scenario_summary(scenario: Scenario) -> None:
    best_move = optimal_move(scenario)
    best_score = optimal_score(scenario)

    print("Board:")
    print(scenario.board.render())
    print()
    print(f"Rack: {list(scenario.rack)}")
    print(f"Token scores: {scenario.token_scores}")
    print(
        "Accepted words in finite reference set "
        f"(length <= {scenario.reference_max_length}): {list(scenario.accepted_words)}"
    )
    print(f"Number of legal moves: {len(scenario.legal_moves)}")
    print(f"Optimal move: {best_move} with score {best_score}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--model-name",
        help="Name of the model profile from model_configs.yaml.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--call-model", action="store_true")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument(
        "--reference-max-length",
        type=int,
        default=None,
        help=(
            "Maximum accepted-word length used for finite token-frequency analysis. "
            "Defaults to the largest board-axis size."
        ),
    )
    parser.add_argument(
        "--visualize-dfa",
        type=Path,
        help="Render the scenario DFA as a PNG at the given path.",
    )
    parser.add_argument(
        "--grammar",
        type=Path,
        default=None,
        help="Path to a grammar JSON file produced by sample-grammar. Replaces the demo DFA.",
    )
    args = parser.parse_args()

    scenario = generate_scenario(
        seed=args.seed,
        reference_max_length=args.reference_max_length,
        grammar_path=str(args.grammar) if args.grammar else None,
    )
    system_prompt, user_prompt = build_prompt(scenario)

    print_scenario_summary(scenario)
    if args.visualize_dfa:
        output_path = render_dfa_png(scenario.dfa, args.visualize_dfa)
        print(f"DFA visualization written to: {output_path}")

    if args.show_prompt:
        print("\n--- SYSTEM PROMPT ---")
        print(system_prompt)
        print("\n--- USER PROMPT ---")
        print(user_prompt)

    if args.dry_run and not args.call_model:
        return
    if not args.call_model:
        print("\nNo model call requested. Use --call-model to query LLM.")
        return

    raw_output = call_llm(system_prompt, user_prompt, model_name=args.model_name)
    print("\n--- MODEL OUTPUT ---")
    print(raw_output)
    move = parse_move(raw_output)
    result = validate_move(
        scenario.board,
        scenario.dfa,
        scenario.rack,
        scenario.token_scores,
        move,
    )
    print("\n--- VALIDATION ---")
    print(json.dumps(result.__dict__, indent=2, ensure_ascii=False))
    if result.ok:
        normalized = result.score / optimal_score(scenario)
        print(f"normalized_score: {normalized:.3f}")


if __name__ == "__main__":
    main()
