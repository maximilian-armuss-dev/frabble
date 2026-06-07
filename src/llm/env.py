from __future__ import annotations

from dataclasses import dataclass
from typing import List
from pathlib import Path
from dotenv import load_dotenv

import os
import yaml


CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
MODEL_CONFIGS_PATH = CONFIG_DIR / "model_configs.yaml"
ENV_PATH = CONFIG_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model: str
    api_key: str
    temperature: float
    max_completion_tokens: int | None = None
    base_url: str | None = None
    timeout_seconds: float | None = None


class Environment:
    def __init__(self) -> None:
        self.env_vars = self._load_env()
        self.model_configs = self._load_model_configs()

    def _optional_env(self, name: str) -> str:
        return (os.environ.get(name) or "").strip()

    def _load_env(self) -> dict[str, str]:
        return {
            "TEMPERATURE_DEFAULT": self._optional_env("TEMPERATURE_DEFAULT"),
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
            # Required values
            name = self._required_config_value(raw_model, "name")
            model = self._required_config_value(raw_model, "model")
            api_key_env = self._required_config_value(raw_model, "api_key_env")
            api_key = self.env_vars.get(api_key_env, "")
            temperature_str = raw_model.get("temperature")
            if temperature_str is None:
                temperature_str = self.get_env("TEMPERATURE_DEFAULT")
            temperature = max(float(temperature_str), 1e-6)
            # Optional values
            max_completion_tokens = self._optional_int_config_value(
                raw_model, "max_completion_tokens"
            )
            base_url_env = self._optional_config_value(raw_model, "base_url_env")
            base_url = self.env_vars.get(base_url_env, "") if base_url_env else None
            timeout_seconds = self._optional_float_config_value(
                raw_model, "timeout_seconds"
            )
            configs[name] = ModelConfig(
                name=name,
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                base_url=base_url,
                timeout_seconds=timeout_seconds,
            )
        return configs

    def _optional_int_config_value(
        self, raw_model: dict[str, object], key: str
    ) -> int | None:
        value = raw_model.get(key)
        if value is None:
            return None
        parsed = int(value)
        if parsed <= 0:
            raise RuntimeError(f"Model config value '{key}' must be positive.")
        return parsed

    def _optional_float_config_value(
        self, raw_model: dict[str, object], key: str
    ) -> float | None:
        value = raw_model.get(key)
        if value is None:
            return None
        parsed = float(value)
        if parsed <= 0:
            raise RuntimeError(f"Model config value '{key}' must be positive.")
        return parsed

    def _optional_config_value(
        self, raw_model: dict[str, object], key: str
    ) -> str | None:
        value = raw_model.get(key)
        if value is None:
            return None
        return str(value).strip()

    def _required_config_value(self, raw_model: dict[str, object], key: str) -> str:
        value = self._optional_config_value(raw_model, key)
        if not value:
            raise RuntimeError(f"Model config is missing required key '{key}'.")
        return value

    def get_model_config(self, model_name: str) -> ModelConfig:
        if model_name not in self.model_configs:
            registered = self.get_registered_model_names()
            raise RuntimeError(
                f"Unknown model name '{model_name}'. Registered models: {registered}"
            )
        return self.model_configs[model_name]

    def get_env(self, var_name: str) -> str:
        if var_name not in self.env_vars or not self.env_vars[var_name]:
            raise RuntimeError(f"'{var_name}' not defined in .env.")
        return self.env_vars[var_name]

    def get_registered_model_names(self) -> List[str]:
        names = [name for name in self.model_configs.keys()]
        return names


ENV = Environment()
