from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    temperature: float = 0.7
    reasoning_effort: str | None = None


def load_environment() -> None:
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)


def get_llm_config() -> LLMConfig:
    load_environment()
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL")

    if not api_key:
        raise RuntimeError("LLM_API_KEY is required for --call-model.")
    if not model:
        raise RuntimeError("LLM_MODEL is required for --call-model.")

    temperature_str = os.environ.get("LLM_TEMPERATURE", "0.7")
    try:
        temperature = float(temperature_str)
    except ValueError:
        raise RuntimeError(f"LLM_TEMPERATURE must be a valid float, got: {temperature_str}")

    return LLMConfig(
        api_key=api_key,
        model=model,
        temperature=temperature,
        reasoning_effort=os.environ.get("LLM_REASONING_EFFORT"),
    )
