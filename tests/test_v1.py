import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.benchmark.scoring import BoardScoring
from src.cli import build_parser
from src.domain.board import Board
from src.domain.models import Move, SlotTemplate
from src.formal.language import StrictlyLocalLanguage
from src.formal.parsing import parse_move
from src.formal.slot_csp import SlotCSP
from src.formal.validation import validate_move
from src.generator.config import GeneratorConfig, load_generator_config
from src.generator.candidates import _normalize_feature
from src.generator.engine import GenerationError, ScenarioGenerator
from src.generator.readable_json import dumps_readable_json
from src.generator.reconstruction import reconstruct_boards
from src.generator.scenario_codec import scenario_run_to_json
from src.generator.scenario_io import load_scenario_run
from src.llm.prompting import build_prompt
from src.tools.check_model import clip_preview


def language() -> StrictlyLocalLanguage:
    return StrictlyLocalLanguage(
        language_id="test",
        alphabet=("A", "B", "C", "D", "E", "F"),
        k=2,
        forbidden_snippets=(
            ("A", "A"),
            ("B", "B"),
            ("C", "C"),
            ("D", "D"),
            ("E", "E"),
            ("F", "F"),
        ),
        min_word_length=3,
    )


def config_dict(output_path: str) -> dict[str, object]:
    return {
        "config_name": "unit",
        "dimensions": 2,
        "seed": 11,
        "language": {
            "language_id": "test",
            "alphabet": ["A", "B", "C", "D", "E", "F"],
            "k": 2,
            "forbidden_snippets": [
                ["A", "A"],
                ["B", "B"],
                ["C", "C"],
                ["D", "D"],
                ["E", "E"],
                ["F", "F"],
            ],
            "min_word_length": 3,
        },
        "initial_word_axis": 0,
        "initial_word_length": 5,
        "length_distribution": {"start": 5, "end": 5},
        "top_anchor_count": 12,
        "top_template_count": 24,
        "failure_budget": 8,
        "target_witness_count": 3,
        "scoring": {
            "anchor_centroid_weight": 1.0,
            "anchor_free_span_weight": 1.0,
            "template_bbox_weight": 1.0,
            "template_centroid_weight": 1.0,
            "template_new_cell_bonus_weight": 1.5,
            "template_local_density_penalty_weight": 1.0,
        },
        "additional_rack_noise": 1,
        "output_path": output_path,
        "include_search_logs": True,
    }


class V1Tests(unittest.TestCase):
    def test_strictly_local_language_rejects_short_and_forbidden_sequences(self):
        sl = language()

        self.assertTrue(sl.accepts(("A", "B", "A")))
        self.assertFalse(sl.accepts(("A", "B")))
        self.assertFalse(sl.accepts(("A", "A", "B")))
        self.assertFalse(sl.accepts(("A", "G", "B")))

    def test_slot_csp_solves_fixed_domains_with_ortools_automaton(self):
        result = SlotCSP(language()).solve(
            [
                {"A", "B", "C"},
                {"B"},
                {"A", "C"},
            ]
        )

        self.assertEqual(result, ("A", "B", "A"))

    def test_board_is_sparse_immutable_and_analyzes_slot(self):
        board = Board.empty(2).place(Move(start=(-1, 0), axis=0, sequence=("A", "B", "C")))
        template = SlotTemplate(
            anchor_coord=(0, 0),
            anchor_symbol="B",
            axis=1,
            length=3,
            anchor_index=1,
            start=(0, -1),
            covered_coords=((0, -1), (0, 0), (0, 1)),
        )

        analysis = board.analyze_slot(template)
        next_board = board.place(Move(start=(0, -1), axis=1, sequence=("A", "B", "C")))

        self.assertTrue(analysis.valid_geometry)
        self.assertEqual(analysis.fixed_symbols, {1: "B"})
        self.assertIsNone(board.get((0, -1)))
        self.assertEqual(next_board.get((0, -1)), "A")
        self.assertEqual(board.axes_at((0, 0)), {0})
        self.assertEqual(next_board.axes_at((0, 0)), {0, 1})

    def test_local_adjacent_density_ignores_diagonals_and_template_internals(self):
        board = Board.empty(2)
        for move in (
            Move(start=(-1, 0), axis=0, sequence=("A", "B", "C")),
            Move(start=(1, 1), axis=1, sequence=("A", "B", "C")),
        ):
            board = board.place(move)

        density = BoardScoring.local_adjacent_density(board, ((0, 1), (0, 2)))

        self.assertEqual(density, 3)

    def test_candidate_feature_normalization_is_pool_local(self):
        self.assertEqual(_normalize_feature([2, 4, 6]), (0.0, 0.5, 1.0))
        self.assertEqual(_normalize_feature([3, 3, 3]), (0.0, 0.0, 0.0))
        self.assertEqual(_normalize_feature([]), ())

    def test_validator_accepts_crossing_and_rejects_extension(self):
        sl = language()
        board = Board.empty(2).place(Move(start=(-1, 0), axis=0, sequence=("A", "B", "C")))
        valid_move = Move(start=(0, -1), axis=1, sequence=("A", "B", "C"))
        extension = Move(start=(-1, 0), axis=0, sequence=("A", "B", "C", "D"))

        self.assertTrue(validate_move(board, sl, ("A", "C", "D"), valid_move).ok)
        result = validate_move(board, sl, ("D",), extension)

        self.assertFalse(result.ok)
        self.assertEqual(result.failure_type, "word_extension")

    def test_validator_rejects_implicit_same_axis_sequence_extension(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(-2, -2), axis=1, sequence=("B", "A", "B")),
            Move(start=(-1, -2), axis=1, sequence=("A", "B", "A")),
            Move(start=(0, -2), axis=1, sequence=("B", "A", "B")),
            Move(start=(1, -2), axis=1, sequence=("A", "B", "A")),
        ):
            board = board.place(move)

        result = validate_move(
            board,
            sl,
            ("C",),
            Move(start=(-2, -2), axis=0, sequence=("B", "A", "B", "A", "C")),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.failure_type, "word_extension")

    def test_validator_allows_gap_fill_from_non_word_crossing_symbols(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(0, -1), axis=1, sequence=("B", "A", "B")),
            Move(start=(2, -1), axis=1, sequence=("B", "C", "B")),
        ):
            board = board.place(move)

        result = validate_move(
            board,
            sl,
            ("B",),
            Move(start=(0, 0), axis=0, sequence=("A", "B", "C")),
        )

        self.assertTrue(result.ok)

    def test_parser_requires_sequence_list(self):
        move = parse_move('{"start": [0, -1], "axis": 1, "sequence": ["a", "b", "c"]}')

        self.assertEqual(move, Move(start=(0, -1), axis=1, sequence=("A", "B", "C")))
        with self.assertRaises(ValidationError):
            parse_move('{"start": [0, -1], "axis": 1, "sequence": "ABC"}')

    def test_config_loader_requires_explicit_known_keys(self):
        config = load_generator_config("generator_v1")

        self.assertEqual(config.config_name, "generator_v1")
        invalid = config_dict("unused.json")
        invalid.pop("failure_budget")
        with self.assertRaises(ValidationError):
            GeneratorConfig.model_validate(invalid)
        invalid = config_dict("unused.json")
        invalid["fallback"] = True
        with self.assertRaises(ValidationError):
            GeneratorConfig.model_validate(invalid)

    def test_generator_v1_config_uses_word_length_range(self):
        config = load_generator_config("generator_v1")

        self.assertEqual(config.length_distribution.start, 3)
        self.assertGreater(config.length_distribution.end, config.length_distribution.start)

    def test_generator_is_reproducible_and_writes_incremental_transitions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = str(Path(temp_dir) / "scenarios.json")
            config = GeneratorConfig.model_validate(config_dict(output_path))
            progress_updates: list[int] = []

            first = ScenarioGenerator(config).generate(progress_callback=progress_updates.append)
            second = ScenarioGenerator(config).generate()
            written_path = ScenarioGenerator(config).write(first)
            self.assertTrue(written_path.exists())
            written_text = written_path.read_text(encoding="utf-8")
            loaded = load_scenario_run(written_path)
            data = json.loads(written_text)
            loaded_boards = reconstruct_boards(loaded)
            run_boards = reconstruct_boards(first)

        first_moves = [transition.move for transition in first.transitions]
        second_moves = [transition.move for transition in second.transitions]

        self.assertEqual(loaded, first)
        self.assertEqual(first_moves, second_moves)
        self.assertEqual(len(first.transitions), 3)
        self.assertEqual(progress_updates, [1, 1, 1])
        self.assertTrue(
            all(
                len(transition.rack) == len(transition.placed) + 1
                for transition in first.transitions
            )
        )
        self.assertEqual(len(loaded_boards), 4)
        self.assertIn('\n  "initial_board"', written_text)
        self.assertIn('"alphabet": ["A", "B", "C", "D", "E", "F"]', written_text)
        self.assertEqual(
            [board.occupied_sorted() for board in run_boards],
            [board.occupied_sorted() for board in loaded_boards],
        )
        self.assertIn("initial_board", data)
        self.assertIn("transitions", data)
        self.assertNotIn("board_before_move", data["transitions"][0])
        self.assertNotIn("board_after_move", data["transitions"][0])
        self.assertNotIn("top_anchors", data["transitions"][0]["search_log"])
        self.assertNotIn("top_templates", data["transitions"][0]["search_log"])
        self.assertIn("placed", data["transitions"][0])

    def test_generator_fails_when_target_witness_count_is_not_reached(self):
        config = GeneratorConfig.model_validate(
            config_dict("unused.json") | {"failure_budget": 1, "target_witness_count": 10}
        )

        with self.assertRaisesRegex(GenerationError, r"\d+ of 10 target witnesses"):
            ScenarioGenerator(config).generate()

    def test_readable_json_truncates_floats(self):
        rendered = dumps_readable_json({"score": 1.23456, "loss": -1.23456})

        self.assertIn('"score": 1.2345', rendered)
        self.assertIn('"loss": -1.2345', rendered)
        self.assertNotIn("1.23456", rendered)

    def test_scenario_codec_can_omit_search_logs_and_reconstruct_boards(self):
        config = GeneratorConfig.model_validate(
            config_dict("unused.json") | {"include_search_logs": False}
        )
        scenario_run = ScenarioGenerator(config).generate()
        data = scenario_run_to_json(scenario_run)
        loaded_boards = reconstruct_boards(data)
        run_boards = reconstruct_boards(scenario_run)

        self.assertNotIn("search_log", data["transitions"][0])
        self.assertEqual(
            [board.occupied_sorted() for board in run_boards],
            [board.occupied_sorted() for board in loaded_boards],
        )

    def test_prompt_uses_sequence_schema_and_board_configuration(self):
        config = GeneratorConfig.model_validate(config_dict("unused.json"))
        scenario_run = ScenarioGenerator(config).generate()
        sl = language()

        _, user_prompt = build_prompt(
            scenario_run.initial_board,
            scenario_run.transitions[0],
            sl,
        )

        self.assertIn('"sequence"', user_prompt)
        self.assertIn('"occupied"', user_prompt)
        self.assertNotIn("Token scores", user_prompt)

    def test_cli_parser_requires_config_only(self):
        args = build_parser().parse_args(["--config", "generator_v1"])

        self.assertEqual(args.config, "generator_v1")

    def test_clip_preview_truncates_long_model_output(self):
        preview = clip_preview("Pong " * 30, max_length=20)

        self.assertEqual(preview, "Pong Pong Pong Pong…")


if __name__ == "__main__":
    unittest.main()
