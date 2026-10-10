from __future__ import annotations

import shutil
from contextlib import AbstractContextManager
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..formal.grammar.config import load_grammar_config
from ..generator.config import PROJECT_ROOT, load_generator_config
from .artifacts import content_sha256
from .case_preparation import CaseSetPreparer
from .config import CaseSetConfig
from .preparation_artifacts import PreparationManifest
from .scenario_workers import resolve_worker_count

EVALUATION_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluation"


def prepare_case_set(
    config: CaseSetConfig,
    *,
    clean: bool = False,
    workers: int | None = None,
    generation_progress_factory: (
        Callable[
            [str, int],
            AbstractContextManager[Callable[[int], None]],
        ]
        | None
    ) = None,
) -> dict[str, Any]:
    """Materialize local cases, reusing matching registered artifacts on resume.

    ``clean`` removes the whole case-set directory, including evaluation runs.
    Worker counts are validated before deletion; one worker runs serially.
    Failures leave registered work available for a later invocation. No model
    calls are made. The returned manifest describes the completed case set.
    """
    resolve_worker_count(workers, 0)  # Validate before --clean or any writes.
    root = EVALUATION_OUTPUT_DIR / config.config_name
    base_grammar = load_grammar_config(config.grammar_config)
    base_generation = load_generator_config(
        config.generation_config,
        validate_grammar=False,
    )
    if clean:
        _clean_case_set_root(root)

    # Keep existing single-dimension case sets compatible with their manifests.
    config_hash = content_sha256(config.model_dump(mode="json", exclude_none=True))
    manifest = PreparationManifest.load_or_create(
        root / "prepare-manifest.json",
        config,
        config_hash,
    )
    manifest.data["status"] = "in_progress"
    manifest.data["completed_at"] = None
    manifest.write_interface_schemas(root)

    preparer = CaseSetPreparer(
        config=config,
        base_grammar=base_grammar,
        base_generation=base_generation,
        root=root,
        config_hash=config_hash,
        manifest=manifest,
        workers=workers,
        generation_progress_factory=generation_progress_factory,
    )
    preparer.prepare()
    manifest.mark_complete()
    return manifest.data


def _clean_case_set_root(root: Path) -> None:
    output_root = EVALUATION_OUTPUT_DIR.resolve()
    resolved_root = root.resolve()
    if resolved_root.parent != output_root:
        raise ValueError(
            f"Refusing to clean path outside evaluation output: {root}"
        )
    if root.is_symlink() or root.is_file():
        root.unlink()
    elif root.exists():
        shutil.rmtree(root)
