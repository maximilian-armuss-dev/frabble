from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import os
import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
MODEL_CONFIGS_PATH = CONFIG_DIR / "model_configs.yaml"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=False)


@dataclass(frozen=True)
class ModelConfig:
    name: str
    model: str
    api_key: str
    temperature: float
    max_completion_tokens: int
    timeout_seconds: float
    base_url: str | None = None
    provider: str | None = None

    @property
    def backend(self) -> str:
        return "openrouter" if self.model.startswith("openrouter/") else "litellm"

    @property
    def request_model(self) -> str:
        if self.backend == "openrouter":
            return self.model.removeprefix("openrouter/")
        return self.model


class Environment:
    def __init__(self) -> None:
        self.env_vars = self._load_env()
        self.model_configs = self._load_model_configs()

    def _optional_env(self, name: str) -> str:
        return (os.environ.get(name) or "").strip()

    def _load_env(self) -> dict[str, str]:
        return {
            "OPENAI_API_KEY": self._optional_env("OPENAI_API_KEY"),
            "OPENAI_BASE_URL": self._optional_env("OPENAI_BASE_URL"),
            "ANTHROPIC_API_KEY": self._optional_env("ANTHROPIC_API_KEY"),
            "GEMINI_API_KEY": self._optional_env("GEMINI_API_KEY"),
            "GEMINI_BASE_URL": self._optional_env("GEMINI_BASE_URL"),
            "OPENROUTER_API_KEY": self._optional_env("OPENROUTER_API_KEY"),
            "OPENROUTER_API_BASE": self._optional_env("OPENROUTER_API_BASE"),
        }

    def _load_model_configs(self) -> dict[str, ModelConfig]:
        data = yaml.safe_load(MODEL_CONFIGS_PATH.read_text(encoding="utf-8"))
        defaults = data.get("defaults")
        if not isinstance(defaults, dict):
            raise RuntimeError("Model config must define a 'defaults' mapping.")
        raw_models = data.get("models")
        if not isinstance(raw_models, list):
            raise RuntimeError("Model config must define a 'models' list.")
        configs: dict[str, ModelConfig] = {}
        for raw_model in raw_models:
            if not isinstance(raw_model, dict):
                raise RuntimeError("Each model config must be a mapping.")
            # Required values
            name = self._required_config_value(raw_model, "name")
            model = self._required_config_value(raw_model, "model")
            api_key_env = self._required_config_value(raw_model, "api_key_env")
            api_key = self._config_env(api_key_env)
            backend = (
                "openrouter" if model.startswith("openrouter/") else "litellm"
            )
            if backend == "openrouter" and model == "openrouter/":
                raise RuntimeError(
                    f"OpenRouter model profile '{name}' has no request model."
                )
            temperature = self._float_config_value(
                raw_model,
                defaults,
                "temperature",
                minimum=0,
            )
            max_completion_tokens = self._int_config_value(
                raw_model,
                defaults,
                "max_completion_tokens",
            )
            base_url_env = self._optional_config_value(raw_model, "base_url_env")
            base_url = (
                self._config_env(base_url_env) or None
                if base_url_env
                else None
            )
            timeout_seconds = self._float_config_value(
                raw_model,
                defaults,
                "timeout_seconds",
                minimum=0,
                inclusive=False,
            )
            provider = self._optional_config_value(raw_model, "provider")
            if backend == "openrouter" and provider is None:
                raise RuntimeError(
                    f"OpenRouter model profile '{name}' must configure provider."
                )
            configs[name] = ModelConfig(
                name=name,
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                base_url=base_url,
                timeout_seconds=timeout_seconds,
                provider=provider,
            )
        return configs

    def _config_env(self, name: str) -> str:
        value = self._optional_env(name)
        self.env_vars[name] = value
        return value

    def _int_config_value(
        self,
        raw_model: dict[str, object],
        defaults: dict[str, object],
        key: str,
    ) -> int:
        value = raw_model.get(key, defaults.get(key))
        if value is None:
            raise RuntimeError(f"Model config is missing default value '{key}'.")
        parsed = int(value)
        if parsed <= 0:
            raise RuntimeError(f"Model config value '{key}' must be positive.")
        return parsed

    def _float_config_value(
        self,
        raw_model: dict[str, object],
        defaults: dict[str, object],
        key: str,
        *,
        minimum: float,
        inclusive: bool = True,
    ) -> float:
        value = raw_model.get(key, defaults.get(key))
        if value is None:
            raise RuntimeError(f"Model config is missing default value '{key}'.")
        parsed = float(value)
        if parsed < minimum or (not inclusive and parsed == minimum):
            operator = ">=" if inclusive else ">"
            raise RuntimeError(
                f"Model config value '{key}' must be {operator} {minimum}."
            )
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
