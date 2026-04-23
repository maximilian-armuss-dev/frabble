import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import os

from llm_scrabble_bench.prototype import (
    Board,
    ModelConfig,
    Move,
    Environment,
    build_demo_dfa,
    generate_scenario,
    optimal_move,
    optimal_score,
    parse_move,
    parse_submitted_move,
    render_dfa_png,
    validate_move,
)


class PrototypeTests(unittest.TestCase):
    def test_demo_dfa_accepts_expected_language(self):
        dfa = build_demo_dfa()

        self.assertTrue(dfa.accepts("ABC"))
        self.assertTrue(dfa.accepts("AABC"))
        self.assertTrue(dfa.accepts("ABAAC"))
        self.assertFalse(dfa.accepts("AC"))
        self.assertFalse(dfa.accepts("ABBC"))
        self.assertFalse(dfa.accepts("ABCA"))

    def test_scenario_has_legal_optimal_move(self):
        scenario = generate_scenario(seed=7)

        self.assertEqual(scenario.reference_max_length, 5)
        self.assertGreater(len(scenario.legal_moves), 0)
        result = validate_move(
            scenario.board,
            scenario.dfa,
            scenario.rack,
            scenario.token_scores,
            optimal_move(scenario),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.score, optimal_score(scenario))

    def test_scenario_uses_configurable_finite_reference_length(self):
        scenario = generate_scenario(seed=7, reference_max_length=4)

        self.assertEqual(scenario.reference_max_length, 4)
        self.assertTrue(all(len(word) <= 4 for word in scenario.accepted_words))
        self.assertGreater(len(scenario.accepted_words), 0)

    def test_validator_rejects_rack_failure(self):
        scenario = generate_scenario(seed=7)
        move = Move(start=(2, 0), axis=1, tokens="AAABC")

        result = validate_move(
            scenario.board,
            scenario.dfa,
            rack=("B", "C"),
            token_scores=scenario.token_scores,
            move=move,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.failure_type, "rack")

    def test_parse_move_accepts_json_object(self):
        move = parse_move('{"start": [2, 1], "axis": 1, "tokens": "abc"}')

        self.assertEqual(move, Move(start=(2, 1), axis=1, tokens="ABC"))

    def test_submitted_move_accepts_token_list(self):
        submitted = parse_submitted_move(
            '{"start": [2, 1], "axis": 0, "tokens": ["a", "b", "c"]}'
        )

        self.assertEqual(submitted.start, (2, 1))
        self.assertEqual(submitted.axis, 0)
        self.assertEqual(submitted.tokens, "ABC")

    def test_validator_accepts_three_dimensional_axis_move(self):
        dfa = build_demo_dfa()
        cells = np.full((3, 3, 3), None, dtype=object)
        cells[1, 1, 0] = "A"
        board = Board(cells=cells)
        move = Move(start=(1, 1, 0), axis=2, tokens="ABC")

        result = validate_move(
            board=board,
            dfa=dfa,
            rack=("B", "C"),
            token_scores={"A": 1, "B": 1, "C": 1},
            move=move,
        )

        self.assertTrue(result.ok)

    def test_render_dfa_png_writes_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "dfa.png"
            rendered_path = render_dfa_png(build_demo_dfa(), output_path)

            self.assertEqual(rendered_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)

    def test_environment_loads_model_configs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            model_path = Path(temp_dir) / "model_configs.yaml"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_MODEL_NAME=openai_test",
                        "OPENAI_API_KEY=test-key",
                        "GEMINI_API_KEY=gemini-key",
                    ]
                ),
                encoding="utf-8",
            )
            model_path.write_text(
                "\n".join(
                    [
                        "models:",
                        "  - name: openai_test",
                        "    model: openai/gpt-5-mini",
                        "    api_key_env: OPENAI_API_KEY",
                        "    temperature: 0.7",
                        "  - name: google_test",
                        "    model: gemini/gemini-2.0-flash-exp",
                        "    api_key_env: GEMINI_API_KEY",
                        "    temperature: 0.8",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "LLM_MODEL_NAME": "openai_test",
                    "OPENAI_API_KEY": "test-key",
                    "GEMINI_API_KEY": "gemini-key",
                },
                clear=True,
            ):
                with patch("llm_scrabble_bench.env.MODEL_CONFIGS_PATH", model_path):
                    local_env = Environment()

        self.assertEqual(set(local_env.model_configs), {"openai_test", "google_test"})
        self.assertEqual(
            local_env.model_configs["openai_test"],
            ModelConfig(
                name="openai_test",
                model="openai/gpt-5-mini",
                api_key="test-key",
                temperature=0.7,
                reasoning_effort=None,
                base_url=None,
            ),
        )

    def test_environment_returns_selected_model_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            model_path = Path(temp_dir) / "model_configs.yaml"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_MODEL_NAME=openai_test",
                        "OPENAI_API_KEY=test-key",
                    ]
                ),
                encoding="utf-8",
            )
            model_path.write_text(
                "\n".join(
                    [
                        "models:",
                        "  - name: openai_test",
                        "    model: openai/gpt-5-mini",
                        "    api_key_env: OPENAI_API_KEY",
                        "    temperature: 0.3",
                        "    reasoning_effort: medium",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "LLM_MODEL_NAME": "openai_test",
                    "OPENAI_API_KEY": "test-key",
                },
                clear=True,
            ):
                with patch("llm_scrabble_bench.env.MODEL_CONFIGS_PATH", model_path):
                    config = Environment().get_model_config("openai_test")

        self.assertEqual(config.name, "openai_test")
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.model, "openai/gpt-5-mini")
        self.assertEqual(config.temperature, 0.3)
        self.assertEqual(config.reasoning_effort, "medium")


if __name__ == "__main__":
    unittest.main()
