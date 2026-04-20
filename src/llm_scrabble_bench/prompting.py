from __future__ import annotations

import json
from pathlib import Path

from .models import Scenario
from .parsing import SubmittedMove


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt_template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def describe_axes(dimensions: int) -> str:
    if dimensions == 1:
        return "Axis 0 is the only axis."
    axis_parts = [f"{axis} advances coordinate index {axis}" for axis in range(dimensions)]
    return "Axis selects the board dimension along which the token sequence advances: " + ", ".join(
        axis_parts
    ) + "."


def build_prompt(scenario: Scenario) -> tuple[str, str]:
    score_lines = "\n".join(
        f"- {token}: {score}" for token, score in sorted(scenario.token_scores.items())
    )
    response_example = {
        "start": [0 for _ in range(scenario.board.dimensions)],
        "axis": 0,
        "tokens": "ABC",
    }
    output_schema = SubmittedMove.model_json_schema()
    system_prompt = load_prompt_template("system.txt").strip()
    user_prompt = load_prompt_template("user.txt").format(
        dimensions=scenario.board.dimensions,
        axis_description=describe_axes(scenario.board.dimensions),
        formal_language=scenario.dfa.describe(),
        board=scenario.board.render(),
        rack=list(scenario.rack),
        token_scores=score_lines,
        output_schema=json.dumps(output_schema, indent=2),
        response_example=json.dumps(response_example),
    )
    return system_prompt, user_prompt
