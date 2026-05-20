from __future__ import annotations

import argparse
import sys

from tqdm import tqdm

from .generator.config import ConfigError, load_generator_config
from .generator.engine import GenerationError, ScenarioGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate V1 multidimensional Scrabble benchmark scenarios."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Config name under config/, for example: generator_v1",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        config = load_generator_config(args.config)
        generator = ScenarioGenerator(config)
        with tqdm(
            total=config.target_witness_count,
            desc="witnesses",
            unit="witness",
            disable=not sys.stderr.isatty(),
        ) as progress:
            scenario_run = generator.generate(progress_callback=progress.update)
        output_path = generator.write(scenario_run)
    except (ConfigError, GenerationError, ValueError) as exc:
        print(f"generation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(
        f"generated {len(scenario_run.transitions)} witness transitions "
        f"with config {config.config_name!r}"
    )
    print(f"output: {output_path}")


if __name__ == "__main__":
    main()
