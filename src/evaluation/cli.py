from __future__ import annotations

import argparse
import asyncio

from tqdm import tqdm

from .config import EvaluationConfigError, load_case_set_config, load_run_config
from .decomposition import decompose_run
from .prepare import prepare_case_set
from .runner import evaluate_run


def cmd_prepare() -> None:
    parser = _config_parser("Prepare an evaluation case set.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the existing case-set output before preparing.",
    )
    args = parser.parse_args()
    try:
        config = load_case_set_config(args.config)
        total = len(config.board_sizes) * config.sampling_rounds
        with tqdm(total=total, desc="cases", unit="case") as progress:
            manifest = prepare_case_set(
                config,
                clean=args.clean,
                progress_callback=progress.update,
            )
    except (EvaluationConfigError, ValueError) as exc:
        print(f"prepare failed: {exc}")
        raise SystemExit(1) from exc
    print(
        f"prepared {len(manifest['cases'])} cases for "
        f"{manifest['case_set']!r}"
    )


def cmd_evaluate() -> None:
    args = _config_parser("Evaluate a prepared case set.").parse_args()
    progress: tqdm | None = None

    def update_progress(finished: int, total: int) -> None:
        nonlocal progress
        if progress is None:
            progress = tqdm(
                total=total,
                initial=finished,
                desc="requests",
                unit="request",
            )
            return
        progress.update(finished - progress.n)

    try:
        result = asyncio.run(
            evaluate_run(
                load_run_config(args.config),
                progress_callback=update_progress,
            )
        )
    except (EvaluationConfigError, ValueError) as exc:
        print(f"evaluation failed: {exc}")
        raise SystemExit(1) from exc
    finally:
        if progress is not None:
            progress.close()
    print(f"evaluation run: {result['run_dir']}")
    print(f"summary: {result['summary']}")


def cmd_decompose() -> None:
    args = _config_parser("Decompose failed results from an evaluation run.").parse_args()
    try:
        result = asyncio.run(decompose_run(load_run_config(args.config)))
    except (EvaluationConfigError, ValueError) as exc:
        print(f"decomposition failed: {exc}")
        raise SystemExit(1) from exc
    print(f"decomposition summary: {result}")


def _config_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        required=True,
        help="Config name without path or suffix.",
    )
    return parser
