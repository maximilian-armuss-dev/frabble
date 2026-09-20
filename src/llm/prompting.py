from __future__ import annotations

from pathlib import Path

from ..domain.board import Board
from ..domain.models import ScenarioTransition
from ..formal.language import StrictlyLocalLanguage
from .representers import RepresenterConfig

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt_template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def describe_axes(dimensions: int) -> str:
    return "; ".join(
        f"axis {axis} increments coordinate[{axis}]" for axis in range(dimensions)
    )


def build_prompt(
    board: Board,
    transition: ScenarioTransition,
    language: StrictlyLocalLanguage,
    representers: RepresenterConfig,
) -> tuple[str, str]:
    system_prompt = load_prompt_template("system.txt").strip()
    user_prompt = load_prompt_template("user.txt").format(
        dimensions=board.dimensions,
        axis_description=describe_axes(board.dimensions),
        formal_language=representers.language.represent(language),
        board=representers.board.represent(board),
        rack=representers.rack.represent(transition.rack),
        letter_scores=language.describe_letter_scores(),
    )
    return system_prompt, user_prompt
