from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from contextlib import contextmanager

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
        manifest = prepare_case_set(
            config,
            clean=args.clean,
            generation_progress_factory=_generation_progress,
        )
    except (EvaluationConfigError, ValueError) as exc:
        print(f"prepare failed: {exc}")
        raise SystemExit(1) from exc
    print(
        f"prepared {len(manifest['cases'])} cases for "
        f"{manifest['case_set']!r}"
    )


@contextmanager
def _generation_progress(
    scenario_id: str,
    total: int,
) -> Callable[[int], None]:
    with tqdm(
        total=total,
        desc=scenario_id,
        unit="move",
        disable=not sys.stderr.isatty(),
    ) as progress:
        yield progress.update


def cmd_evaluate() -> None:
    parser = _config_parser("Evaluate a prepared case set.")
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start a new run instead of reusing the latest matching run.",
    )
    args = parser.parse_args()
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
                new_run=args.new,
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
    if result["manifest"]["status"] == "complete":
        print(
            "All runs are valid (no transport or provider response errors). "
            f"Start a new run with: uv run evaluate --config {args.config} --new"
        )
    else:
        print(
            "Some jobs are still missing valid responses. "
            "Retry them with: "
            f"uv run evaluate --config {args.config}"
        )


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
