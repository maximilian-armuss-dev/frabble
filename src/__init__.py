"""Core package for the Frabble benchmark."""

from .benchmark.scoring import BoardScoring
from .domain.board import Board
from .domain.models import (
    BoardConfiguration,
    DFA,
    Move,
    ScenarioRun,
    ScenarioTransition,
    Segment,
    SlotAnalysis,
    SlotTemplate,
    ValidationResult,
)
from .domain.visualization import build_dfa_graph, render_dfa_png
from .formal.automata import enumerate_accepted_sequences
from .formal.language import StrictlyLocalLanguage
from .formal.parsing import SubmittedMove, parse_move, parse_submitted_move
from .formal.slot_csp import SlotCSP
from .formal.validation import MoveValidationReport, validate_move, validate_move_detailed
from .generator.config import ConfigError, GeneratorConfig, load_generator_config
from .generator.engine import GenerationError, ScenarioGenerator
from .generator.reconstruction import board_before_transition, reconstruct_boards
from .generator.scenario_codec import scenario_run_from_json
from .generator.scenario_io import load_scenario_run

__all__ = [
    "Board",
    "BoardConfiguration",
    "BoardScoring",
    "ConfigError",
    "DFA",
    "GenerationError",
    "GeneratorConfig",
    "Move",
    "MoveValidationReport",
    "ScenarioGenerator",
    "ScenarioRun",
    "ScenarioTransition",
    "Segment",
    "SlotAnalysis",
    "SlotCSP",
    "SlotTemplate",
    "StrictlyLocalLanguage",
    "SubmittedMove",
    "ValidationResult",
    "board_before_transition",
    "build_dfa_graph",
    "enumerate_accepted_sequences",
    "load_generator_config",
    "load_scenario_run",
    "parse_move",
    "parse_submitted_move",
    "reconstruct_boards",
    "render_dfa_png",
    "scenario_run_from_json",
    "validate_move",
    "validate_move_detailed",
]
