from __future__ import annotations

from .automata import build_demo_dfa, enumerate_accepted_words
from .board import build_demo_board
from .cli import main, print_scenario_summary
from .config import OpenAIConfig, get_openai_config, load_environment
from .generation import generate_scenario, sample_rack
from .models import Board, DFA, Move, Scenario, ValidationResult
from .openai_client import call_openai
from .parsing import SubmittedMove, parse_move, parse_submitted_move
from .prompting import build_prompt
from .scoring import (
    optimal_move,
    optimal_score,
    score_word,
    token_frequencies,
    token_scores_from_frequencies,
)
from .validation import enumerate_legal_moves, validate_move
from .visualization import build_dfa_graph, render_dfa_png

__all__ = [
    "Board",
    "DFA",
    "OpenAIConfig",
    "Move",
    "Scenario",
    "SubmittedMove",
    "ValidationResult",
    "build_demo_board",
    "build_demo_dfa",
    "build_dfa_graph",
    "build_prompt",
    "call_openai",
    "enumerate_accepted_words",
    "enumerate_legal_moves",
    "generate_scenario",
    "get_openai_config",
    "load_environment",
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
]


if __name__ == "__main__":
    main()
