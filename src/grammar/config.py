from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
GRAMMAR_CONFIGS_PATH = CONFIG_DIR / "grammar_configs.yaml"


@dataclass(frozen=True)
class AutoResampleConfig:
    enabled: bool
    max_attempts: int
    perron_min: float
    perron_max: float
    resample_length_min: int
    resample_length_max: int
    min_word_count: int


@dataclass(frozen=True)
class SLSamplingConfig:
    alphabet_case: str
    forbidden_fraction: float
    minimize_dfa: bool
    auto_resample: AutoResampleConfig


def load_sl_sampling_config() -> SLSamplingConfig:
    data = yaml.safe_load(GRAMMAR_CONFIGS_PATH.read_text(encoding="utf-8"))
    sl = data["sl_grammar"]
    ar = sl["auto_resample"]
    return SLSamplingConfig(
        alphabet_case=str(sl["alphabet_case"]),
        forbidden_fraction=float(sl["forbidden_fraction"]),
        minimize_dfa=bool(sl["minimize_dfa"]),
        auto_resample=AutoResampleConfig(
            enabled=bool(ar["enabled"]),
            max_attempts=int(ar["max_attempts"]),
            perron_min=float(ar["perron_min"]),
            perron_max=float(ar["perron_max"]),
            resample_length_min=int(ar["resample_length_min"]),
            resample_length_max=int(ar["resample_length_max"]),
            min_word_count=int(ar["min_word_count"]),
        ),
    )


GRAMMAR_CONFIG = load_sl_sampling_config()
