from __future__ import annotations

from .benchmark.generation import generate_scenario, sample_rack
from .benchmark.prompting import build_prompt
from .benchmark.scoring import (
    optimal_move,
    optimal_score,
    score_word,
    token_frequencies,
    token_scores_from_frequencies,
)
from .cli import main, print_scenario_summary
from .domain.board import build_demo_board
from .domain.models import Board, DFA, Move, Scenario, ValidationResult
from .domain.visualization import build_dfa_graph, render_dfa_png
from .formal.automata import build_demo_dfa, enumerate_accepted_words
from .formal.parsing import SubmittedMove, parse_move, parse_submitted_move
from .formal.validation import enumerate_legal_moves, validate_move
from .llm.client import call_llm
from .llm.env import (
    ENV,
    ENV_PATH,
    Environment,
    MODEL_CONFIGS_PATH,
    ModelConfig,
    CONFIG_DIR,
)

__all__ = [
    "Board",
    "DFA",
    "ENV",
    "ENV_PATH",
    "Environment",
    "MODEL_CONFIGS_PATH",
    "ModelConfig",
    "Move",
    "Scenario",
    "SubmittedMove",
    "ValidationResult",
    "build_demo_board",
    "build_demo_dfa",
    "build_dfa_graph",
    "build_prompt",
    "call_llm",
    "enumerate_accepted_words",
    "enumerate_legal_moves",
    "generate_scenario",
    "main",
    "optimal_move",
    "optimal_score",
    "parse_move",
    "parse_submitted_move",
    "print_scenario_summary",
    "render_dfa_png",
    "sample_rack",
    "score_word",
    "token_frequencies",
    "token_scores_from_frequencies",
    "validate_move",
    "CONFIG_DIR",
]


if __name__ == "__main__":
    main()
