from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..formal.grammar.config import load_grammar_config
from ..generator.config import PROJECT_ROOT, load_generator_config
from .artifacts import content_sha256
from .case_preparation import CaseSetPreparer
from .config import CaseSetConfig
from .preparation_artifacts import PreparationManifest

EVALUATION_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluation"


def prepare_case_set(
    config: CaseSetConfig,
    *,
    progress_callback: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    root = EVALUATION_OUTPUT_DIR / config.config_name
    config_hash = content_sha256(config.model_dump(mode="json"))
    manifest = PreparationManifest.load_or_create(
        root / "prepare-manifest.json",
        config,
        config_hash,
    )
    manifest.write_interface_schemas(root)

    preparer = CaseSetPreparer(
        config=config,
        base_grammar=load_grammar_config(config.grammar_config),
        base_generation=load_generator_config(
            config.generation_config,
            validate_grammar=False,
        ),
        root=root,
        config_hash=config_hash,
        manifest=manifest,
        progress_callback=progress_callback,
    )
    preparer.prepare()
    manifest.mark_complete()
    return manifest.data
