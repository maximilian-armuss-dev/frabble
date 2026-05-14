from __future__ import annotations

import json
from pathlib import Path

from .config import AutoResampleConfig, SLSamplingConfig
from .sl_grammar import SLGrammar

_SCHEMA_VERSION = 1


def save_grammar(
    grammar: SLGrammar,
    config: SLSamplingConfig,
    path: str | Path,
    name: str,
) -> None:
    data = {
        "schema_version": _SCHEMA_VERSION,
        "type": "sl",
        "name": name,
        "alphabet": list(grammar.alphabet),
        "k": grammar.k,
        "forbidden": sorted(grammar.forbidden),
        "min_word_length": grammar.min_word_length,
        "seed": grammar.seed,
        "sampling_config": {
            "alphabet_size": len(grammar.alphabet),
            "forbidden_fraction": config.forbidden_fraction,
            "alphabet_case": config.alphabet_case,
            "minimize_dfa": config.minimize_dfa,
            "auto_resample": {
                "enabled": config.auto_resample.enabled,
                "max_attempts": config.auto_resample.max_attempts,
                "perron_min": config.auto_resample.perron_min,
                "perron_max": config.auto_resample.perron_max,
                "resample_length_min": config.auto_resample.resample_length_min,
                "resample_length_max": config.auto_resample.resample_length_max,
                "min_word_count": config.auto_resample.min_word_count,
            },
        },
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_grammar(path: str | Path) -> tuple[SLGrammar, SLSamplingConfig, str]:
    """Return (grammar, sampling_config, name) from a saved grammar JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    sc = data["sampling_config"]
    ar = sc["auto_resample"]
    config = SLSamplingConfig(
        alphabet_case=str(sc["alphabet_case"]),
        forbidden_fraction=float(sc["forbidden_fraction"]),
        minimize_dfa=bool(sc["minimize_dfa"]),
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
    grammar = SLGrammar(
        alphabet=tuple(data["alphabet"]),
        k=int(data["k"]),
        forbidden=frozenset(data["forbidden"]),
        min_word_length=int(data["min_word_length"]),
        seed=int(data["seed"]),
    )
    return grammar, config, str(data["name"])
