from __future__ import annotations

import argparse
from pathlib import Path

from .alphabet import LetterAlphabetSampler
from .analysis import perron_eigenvalue, word_count_spectrum
from .config import AutoResampleConfig, GRAMMAR_CONFIG, SLSamplingConfig
from .serialization import load_grammar, save_grammar
from .sampler import GrammarSamplingError, sample_sl_grammar, sample_sl_grammar_auto


def cmd_sample() -> None:
    cfg = GRAMMAR_CONFIG

    parser = argparse.ArgumentParser(description="Sample a random SL_k grammar.")

    # Output
    parser.add_argument("--name", required=True, help="Grammar name; saved as <name>.json")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/grammars"),
        help="Directory to write the grammar file (default: outputs/grammars/)",
    )

    # Grammar structure
    parser.add_argument("--alphabet-size", type=int, default=5, metavar="INT")
    parser.add_argument("--k", type=int, default=3, metavar="INT",
                        help="Forbidden pattern length (default: 3)")
    parser.add_argument("--forbidden-fraction", type=float, default=None, metavar="FLOAT",
                        help=f"Fraction of k-grams to forbid (yaml default: {cfg.forbidden_fraction})")
    parser.add_argument("--min-word-length", type=int, default=None, metavar="INT",
                        help="Minimum accepted word length (default: value of --k)")
    parser.add_argument("--seed", type=int, default=42, metavar="INT")

    # Alphabet case
    parser.add_argument("--alphabet-case", choices=["upper", "lower"], default=None,
                        help=f"Letter case (yaml default: {cfg.alphabet_case!r})")

    # Auto-resample
    parser.add_argument("--auto-resample", action=argparse.BooleanOptionalAction, default=None,
                        help=f"Auto-resample until quality bounds are met (yaml default: {cfg.auto_resample.enabled})")
    parser.add_argument("--max-attempts", type=int, default=None, metavar="INT",
                        help=f"Max resample attempts (yaml default: {cfg.auto_resample.max_attempts})")
    parser.add_argument("--perron-min", type=float, default=None, metavar="FLOAT",
                        help=f"Min Perron eigenvalue (yaml default: {cfg.auto_resample.perron_min})")
    parser.add_argument("--perron-max", type=float, default=None, metavar="FLOAT",
                        help=f"Max Perron eigenvalue (yaml default: {cfg.auto_resample.perron_max})")
    parser.add_argument("--resample-length-min", type=int, default=None, metavar="INT",
                        help=f"Word-count window start (yaml default: {cfg.auto_resample.resample_length_min})")
    parser.add_argument("--resample-length-max", type=int, default=None, metavar="INT",
                        help=f"Word-count window end (yaml default: {cfg.auto_resample.resample_length_max})")
    parser.add_argument("--min-word-count", type=int, default=None, metavar="INT",
                        help=f"Min words in window (yaml default: {cfg.auto_resample.min_word_count})")

    # Output behaviour
    parser.add_argument("--show-stats", action="store_true",
                        help="Print Perron eigenvalue and word-count spectrum after sampling")

    args = parser.parse_args()

    # Resolve each parameter: CLI value if given, else yaml default
    alphabet_case = args.alphabet_case if args.alphabet_case is not None else cfg.alphabet_case
    forbidden_fraction = args.forbidden_fraction if args.forbidden_fraction is not None else cfg.forbidden_fraction
    auto_resample_enabled = args.auto_resample if args.auto_resample is not None else cfg.auto_resample.enabled
    max_attempts = args.max_attempts if args.max_attempts is not None else cfg.auto_resample.max_attempts
    perron_min = args.perron_min if args.perron_min is not None else cfg.auto_resample.perron_min
    perron_max = args.perron_max if args.perron_max is not None else cfg.auto_resample.perron_max
    resample_length_min = args.resample_length_min if args.resample_length_min is not None else cfg.auto_resample.resample_length_min
    resample_length_max = args.resample_length_max if args.resample_length_max is not None else cfg.auto_resample.resample_length_max
    min_word_count = args.min_word_count if args.min_word_count is not None else cfg.auto_resample.min_word_count
    min_word_length = args.min_word_length if args.min_word_length is not None else args.k

    resolved_config = SLSamplingConfig(
        alphabet_case=alphabet_case,
        forbidden_fraction=forbidden_fraction,
        auto_resample=AutoResampleConfig(
            enabled=auto_resample_enabled,
            max_attempts=max_attempts,
            perron_min=perron_min,
            perron_max=perron_max,
            resample_length_min=resample_length_min,
            resample_length_max=resample_length_max,
            min_word_count=min_word_count,
        ),
    )

    sampler = LetterAlphabetSampler(case=alphabet_case)
    alphabet = sampler.sample(args.alphabet_size, args.seed)

    try:
        if auto_resample_enabled:
            grammar, actual_seed = sample_sl_grammar_auto(
                alphabet=alphabet,
                k=args.k,
                forbidden_fraction=forbidden_fraction,
                min_word_length=min_word_length,
                seed=args.seed,
                max_attempts=max_attempts,
                perron_min=perron_min,
                perron_max=perron_max,
                resample_length_min=resample_length_min,
                resample_length_max=resample_length_max,
                min_word_count=min_word_count,
                language_id=args.name,
            )
            if actual_seed != args.seed:
                print(f"Note: resampled {actual_seed - args.seed} time(s); seed used = {actual_seed}")
        else:
            grammar = sample_sl_grammar(
                alphabet, args.k, forbidden_fraction, min_word_length, args.seed,
                language_id=args.name,
            )
    except GrammarSamplingError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"{args.name}.json"
    save_grammar(grammar, resolved_config, output_path, args.name)
    print(f"Grammar saved to: {output_path}")

    if args.show_stats:
        lam = perron_eigenvalue(grammar)
        spectrum = word_count_spectrum(grammar, 12)
        print(f"\n{grammar.describe()}")
        print(f"Perron eigenvalue: {lam:.4f}")
        print("Word-count spectrum:")
        for length, cnt in spectrum.items():
            print(f"  length {length:2d}: {cnt:,}")


def cmd_analyze() -> None:
    parser = argparse.ArgumentParser(
        description="Analyse a saved grammar: Perron eigenvalue and word-count spectrum."
    )
    parser.add_argument("grammar_file", type=Path, metavar="GRAMMAR_FILE")
    parser.add_argument("--max-length", type=int, default=12, metavar="INT",
                        help="Analyse word counts up to this length (default: 12)")
    args = parser.parse_args()

    grammar, _, name = load_grammar(args.grammar_file)
    print(f"Grammar: {name}")
    print(f"{grammar.describe()}")

    lam = perron_eigenvalue(grammar)
    print(f"\nPerron eigenvalue: {lam:.6f}")
    if lam > 1:
        print("  → language grows exponentially (good for puzzle generation)")
    elif lam == 1:
        print("  → language is infinite but sub-exponential")
    else:
        print("  → language is finite or empty")

    spectrum = word_count_spectrum(grammar, args.max_length)
    print(f"\nWord-count spectrum (min_word_length = {grammar.min_word_length}):")
    for length, cnt in spectrum.items():
        marker = " ←" if cnt == 0 else ""
        print(f"  length {length:2d}: {cnt:>8,}{marker}")
