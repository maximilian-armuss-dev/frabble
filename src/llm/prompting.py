from __future__ import annotations

import json
from pathlib import Path

from ..domain.board import Board
from ..domain.models import ScenarioTransition
from ..formal.language import StrictlyLocalLanguage
from ..formal.parsing import SubmittedMove
from .representers import RepresenterConfig

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt_template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def describe_axes(dimensions: int) -> str:
    if dimensions == 1:
        return "Axis 0 is the only axis."
    axis_parts = [f"axis {axis} advances coordinate index {axis}" for axis in range(dimensions)]
    return "Axis selects the board dimension along which the sequence advances: " + ", ".join(
        axis_parts
    ) + "."


def build_prompt(
    board: Board,
    transition: ScenarioTransition,
    language: StrictlyLocalLanguage,
    representers: RepresenterConfig | None = None,
) -> tuple[str, str]:
    if representers is None:
        representers = RepresenterConfig()
    response_example = {
        "start": [0 for _ in range(board.dimensions)],
        "axis": 0,
        "sequence": list(language.alphabet[: language.min_word_length]),
    }
    output_schema = SubmittedMove.model_json_schema()
    system_prompt = load_prompt_template("system.txt").strip()
    user_prompt = load_prompt_template("user.txt").format(
        dimensions=board.dimensions,
        axis_description=describe_axes(board.dimensions),
        formal_language=representers.language.represent(language),
        board=representers.board.represent(board),
        rack=representers.rack.represent(transition.rack),
        output_schema=json.dumps(output_schema, indent=2, ensure_ascii=False),
        response_example=json.dumps(response_example, ensure_ascii=False),
    )
    return system_prompt, user_prompt
