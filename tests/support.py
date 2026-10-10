"""Small, deterministic inputs independent of experiment configs and outputs."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from src.configuration import NamedYamlConfigSource
from src.formal.grammar.config import GrammarConfig, GrammarConfigError
from src.generator.config import ConfigError, GeneratorConfig
from src.llm.env import ENV, Environment

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def generation_config(config_name="tiny", *, validate_grammar=False):
    return NamedYamlConfigSource(
        FIXTURES / "config/generation",
        "generation",
        ConfigError,
    ).load(config_name, GeneratorConfig)


def grammar_config(config_name="tiny"):
    return NamedYamlConfigSource(
        FIXTURES / "config/grammars",
        "grammar",
        GrammarConfigError,
    ).load(config_name, GrammarConfig)


@contextmanager
def preparation_recipes():
    """Keep real sampling, generation and spawned workers; only replace recipes."""
    with (
        patch(
            "src.evaluation.prepare.load_generator_config",
            side_effect=generation_config,
        ),
        patch("src.evaluation.prepare.load_grammar_config", side_effect=grammar_config),
    ):
        yield


class FixtureModelsMixin:
    def setUp(self):
        super().setUp()
        self.enterContext(
            patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENROUTER_API_KEY": "test-key",
                    "OPENROUTER_API_BASE": "",
                },
            )
        )
        self.enterContext(
            patch("src.llm.env.MODEL_CONFIGS_PATH", FIXTURES / "model_configs.yaml")
        )
        self.enterContext(
            patch.object(ENV, "model_configs", Environment().model_configs)
        )


def config_dict(output_path: str, *, dimensions: int = 2) -> dict[str, object]:
    return {
        "config_name": "unit",
        "dimensions": dimensions,
        "seed": 11,
        "grammar_path": str(FIXTURES / "grammar.json"),
        "initial_word_axis": 0,
        "initial_word_length": 5,
        "length_distribution": {"start": 5, "end": 5},
        "top_anchor_count": 12,
        "max_anchor_count": None,
        "top_template_count": 24,
        "target_transition_count": 3,
        "scoring": {
            "anchor_centroid_weight": 1.0,
            "template_centroid_weight": 1.0,
            "template_local_density_penalty_weight": 1.0,
        },
        "additional_rack_noise": 1,
        "output_path": output_path,
        "include_search_logs": True,
    }
