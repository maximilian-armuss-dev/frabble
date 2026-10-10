"""Experiment recipes may change; their references must still resolve."""

from pathlib import Path

import pytest

from src.evaluation.config import load_case_set_config, load_run_config
from src.formal.grammar.config import load_grammar_config
from src.generator.config import load_generator_config
from src.llm.env import Environment

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "path", sorted((ROOT / "config/generation").glob("*.yaml")), ids=lambda p: p.stem
)
def test_generation_grammar_recipe_exists(path):
    config = load_generator_config(path.stem, validate_grammar=False)
    if config.grammar is not None:
        load_grammar_config(config.grammar)


@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "config/evaluation/case_sets").glob("*.yaml")),
    ids=lambda p: p.stem,
)
def test_case_set_recipes_exist(path):
    config = load_case_set_config(path.stem)
    load_generator_config(config.generation_config, validate_grammar=False)
    load_grammar_config(config.grammar_config)


@pytest.mark.parametrize(
    "path",
    sorted((ROOT / "config/evaluation/runs").glob("*.yaml")),
    ids=lambda p: p.stem,
)
def test_run_references_exist(path):
    config = load_run_config(path.stem)
    load_case_set_config(config.case_set)
    environment = Environment()
    for name in config.models:
        environment.get_model_config(name)
