from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import perron_eigenvalue, word_count_spectrum
from .config import (
    GrammarConfigError,
    load_grammar_config,
    resolve_grammar_output_path,
)
from .serialization import load_grammar, save_grammar
from .sampler import GrammarSamplingError, sample_grammar_from_config


def cmd_sample() -> None:
    parser = argparse.ArgumentParser(description="Sample a configured SL_k grammar.")
    parser.add_argument(
        "--config",
        required=True,
        help="Config name under config/grammars/ without path or suffix.",
    )
    parser.add_argument(
        "--show-stats",
        action="store_true",
        help="Print analysis even when show_stats is false in the config.",
    )
    args = parser.parse_args()

    try:
        config = load_grammar_config(args.config)
        grammar, actual_seed = sample_grammar_from_config(config)
        output_path = resolve_grammar_output_path(config)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_grammar(grammar, config, output_path, config.config_name)
    except (GrammarConfigError, GrammarSamplingError, ValueError) as exc:
        print(f"grammar sampling failed: {exc}")
        raise SystemExit(1) from exc

    if actual_seed != config.seed:
        print(
            f"Note: resampled {actual_seed - config.seed} time(s); "
            f"seed used = {actual_seed}"
        )
    print(f"Grammar saved to: {output_path}")
    if args.show_stats or config.show_stats:
        _print_stats(grammar)


def cmd_analyze() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse a saved grammar: Perron eigenvalue and word-count spectrum."
    )
    parser.add_argument(
        "grammar",
        help="Grammar ID or explicit JSON path.",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=12,
        metavar="INT",
        help="Analyse word counts up to this length (default: 12)",
    )
    args = parser.parse_args()

    grammar_path = _resolve_grammar_argument(args.grammar)
    grammar, _, name = load_grammar(grammar_path)
    print(f"Grammar: {name}")
    print(f"{grammar.describe()}")

    lam = perron_eigenvalue(grammar)
    print(f"\nPerron eigenvalue: {lam:.6f}")
    if lam > 1:
        print("  -> language grows exponentially (good for puzzle generation)")
    elif lam == 1:
        print("  -> language is infinite but sub-exponential")
    else:
        print("  -> language is finite or empty")

    spectrum = word_count_spectrum(grammar, args.max_length)
    print(f"\nWord-count spectrum (min_word_length = {grammar.min_word_length}):")
    for length, count in spectrum.items():
        marker = " <-" if count == 0 else ""
        print(f"  length {length:2d}: {count:>8,}{marker}")


def _resolve_grammar_argument(value: str) -> Path:
    direct = Path(value)
    if direct.suffix == ".json" or "/" in value or "\\" in value:
        return direct
    from .config import default_grammar_output_path

    return default_grammar_output_path(value)


def _print_stats(grammar) -> None:
    lam = perron_eigenvalue(grammar)
    spectrum = word_count_spectrum(grammar, 12)
    print(f"\n{grammar.describe()}")
    print(f"Perron eigenvalue: {lam:.4f}")
    print("Word-count spectrum:")
    for length, count in spectrum.items():
        print(f"  length {length:2d}: {count:,}")
