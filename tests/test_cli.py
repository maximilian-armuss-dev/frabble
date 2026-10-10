"""Installed commands and the local grammar → scenario workflow."""

import importlib.metadata
import json
import sys
import tomllib
from pathlib import Path

import pytest

from support import config_dict, grammar_config
from src.cli import main as generate
from src.formal.grammar.cli import cmd_analyze, cmd_sample
from src.formal.validation import validate_move
from src.generator.config import GeneratorConfig
from src.generator.scenario_io import load_scenario_run
from src.formal.grammar.serialization import load_grammar

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]


def test_installed_commands_match_project_metadata():
    installed = {
        entry.name: entry.value
        for entry in importlib.metadata.distribution("llm-scrabble-bench").entry_points
        if entry.group == "console_scripts"
    }
    assert installed == SCRIPTS


@pytest.mark.parametrize("name", SCRIPTS)
def test_installed_command_help(name, monkeypatch, capsys):
    entry = importlib.metadata.EntryPoint(
        name=name, value=SCRIPTS[name], group="console_scripts"
    )
    monkeypatch.setattr(sys, "argv", [name, "--help"])
    with pytest.raises(SystemExit) as result:
        entry.load()()
    assert result.value.code == 0
    assert "usage:" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["generate", "sample-grammar", "prepare", "evaluate"])
def test_config_commands_require_explicit_selection(name, monkeypatch, capsys):
    entry = importlib.metadata.EntryPoint(
        name=name, value=SCRIPTS[name], group="console_scripts"
    )
    monkeypatch.setattr(sys, "argv", [name])
    with pytest.raises(SystemExit) as result:
        entry.load()()
    assert result.value.code == 2
    assert "--config" in capsys.readouterr().err


def test_sample_analyze_generate_pipeline(tmp_path, monkeypatch, capsys):
    grammar_path = tmp_path / "grammar.json"
    recipe = grammar_config().model_copy(update={"output_path": str(grammar_path)})
    monkeypatch.setattr(
        "src.formal.grammar.cli.load_grammar_config", lambda name: recipe
    )
    monkeypatch.setattr(sys, "argv", ["sample-grammar", "--config", "tiny"])
    cmd_sample()
    assert grammar_path.is_file()

    monkeypatch.setattr(
        sys, "argv", ["analyze-grammar", str(grammar_path), "--max-length", "3"]
    )
    cmd_analyze()
    assert "Word-count spectrum" in capsys.readouterr().out

    scenario_path = tmp_path / "scenario.json"
    config = GeneratorConfig.model_validate(
        config_dict(str(scenario_path))
        | {
            "grammar_path": str(grammar_path),
            "target_transition_count": 1,
        }
    )
    monkeypatch.setattr("src.cli.load_generator_config", lambda name: config)
    monkeypatch.setattr(sys, "argv", ["generate", "--config", "tiny"])
    generate()
    run = load_scenario_run(scenario_path)
    language, _, _ = load_grammar(grammar_path)
    assert len(run.transitions) == 1
    transition = run.transitions[0]
    assert validate_move(
        run.initial_board, language, transition.rack, transition.move
    ).ok
    assert json.loads(scenario_path.read_text())["schema_version"] == 2
