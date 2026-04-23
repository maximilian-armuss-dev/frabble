from __future__ import annotations

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_CONFIGS_PATH = PROJECT_ROOT / "model_configs.yaml"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model: str
    api_key: str
    temperature: float = 0.8
    reasoning_effort: str | None = None
    base_url: str | None = None


class Environment:

    def __init__(self):
        self.env_vars = self._load_env()
        self.model_configs = self._load_model_configs()

    def _required_env(self, name: str) -> str:
        return os.environ[name].strip()

    def _optional_env(self, name: str) -> str:
        return os.environ.get(name) or ""

    def _load_env(self) -> dict[str, str]:
        return {
            "LLM_MODEL_NAME": self._required_env("LLM_MODEL_NAME"),
            "OPENAI_API_KEY": self._optional_env("OPENAI_API_KEY"),
            "OPENAI_BASE_URL": self._optional_env("OPENAI_BASE_URL"),
            "GEMINI_API_KEY": self._optional_env("GEMINI_API_KEY"),
            "GEMINI_BASE_URL": self._optional_env("GEMINI_BASE_URL"),
        }

    def _load_model_configs(self) -> dict[str, ModelConfig]:
        data = yaml.safe_load(MODEL_CONFIGS_PATH.read_text(encoding="utf-8"))
        raw_models = data.get("models")
        configs: dict[str, ModelConfig] = {}
        for raw_model in raw_models:
            get = lambda var: raw_model.get(var).strip()
            name = get("name")
            api_key = self.env_vars[get("api_key_env")]
            base_url = self.env_vars[get("base_url_env")]
            configs[name] = ModelConfig(
                name=name,
                model=get("model"),
                api_key=api_key,
                temperature=min(get("temperature"), 0),
                reasoning_effort=get("reasoning_effort"),
                base_url=base_url,
            )
        return configs
    
    def get_model_config(self, model_name: str) -> ModelConfig:
        if model_name not in self.model_configs:
            raise RuntimeError(f"Unknown model name '{model_name}'. Registered models: {[conf.name for conf in self.model_configs.values()]}")
        return self.model_configs[model_name]

    def get_env(self, var_name: str) -> str:
        if var_name not in self.env_vars or not self.env_vars[var_name]:
            raise RuntimeError(f"'{var_name}' not defined in .env.")
        return self.env_vars[var_name]


ENV = Environment()
