from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str
    reasoning_effort: str | None = None


def load_environment() -> None:
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)


def get_openai_config() -> OpenAIConfig:
    load_environment()
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --call-model.")
    if not model:
        raise RuntimeError("OPENAI_MODEL is required for --call-model.")

    return OpenAIConfig(
        api_key=api_key,
        model=model,
        reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT"),
    )
