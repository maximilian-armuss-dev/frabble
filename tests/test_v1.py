import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from src.benchmark.scoring import BoardScoring
from src.cli import build_parser
from src.domain.board import Board
from src.domain.models import AnchorCandidate, Move, SlotTemplate, TemplateCandidate
from src.formal.language import StrictlyLocalLanguage
from src.formal.parsing import SubmittedMove, parse_move
from src.formal.slot_csp import SlotCSP
from src.formal.validation import (
    extends_existing_axis_sequence,
    extends_existing_sequence_in_any_axis,
    validate_move,
    validate_move_detailed,
)
from src.generator.config import GeneratorConfig, load_generator_config, resolve_config_path
from src.generator.candidates import _normalize_feature, top_anchors, top_templates
from src.generator.engine import GenerationError, ScenarioGenerator
from src.generator.readable_json import dumps_readable_json
from src.generator.reconstruction import reconstruct_boards
from src.generator.scenario_codec import scenario_run_to_json
from src.generator.scenario_io import load_scenario_run
from src.llm.evaluation import evaluate_granular
from src.llm.prompting import build_prompt
from src.llm.representers import RepresenterConfig
from src.tools.check_model import clip_preview
from visualization.board_figures import (
    animate_scenario_2d,
    animate_scenario_2d_canvas,
    animate_scenario_2d_image,
    animate_scenario_3d,
    plot_board_2d,
    plot_board_3d,
)


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


class CountingLanguage:
    def __init__(self, delegate: StrictlyLocalLanguage) -> None:
        self.delegate = delegate
        self.automaton_calls = 0

    def __getattr__(self, name: str) -> object:
        return getattr(self.delegate, name)

    def ortools_automaton(
        self,
    ) -> tuple[int, list[int], list[tuple[int, int, int]], dict[str, int]]:
        self.automaton_calls += 1
        return self.delegate.ortools_automaton()


def config_dict(output_path: str, *, dimensions: int = 2) -> dict[str, object]:
    return {
        "config_name": "unit",
        "dimensions": dimensions,
        "seed": 11,
        "grammar_path": "outputs/grammars/generator_v1_grammar.json",
        "initial_word_axis": 0,
        "initial_word_length": 5,
        "length_distribution": {"start": 5, "end": 5},
        "top_anchor_count": 12,
        "max_anchor_count": None,
        "top_template_count": 24,
        "target_witness_count": 3,
        "scoring": {
            "anchor_centroid_weight": 1.0,
            "anchor_free_span_weight": 1.0,
            "template_centroid_weight": 1.0,
            "template_new_cell_bonus_weight": 1.5,
            "template_local_density_penalty_weight": 1.0,
            "template_domain_slack_weight": 1.0,
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

    def test_slot_csp_skips_empty_domains_and_reuses_automaton(self):
        counted_language = CountingLanguage(language())
        solver = SlotCSP(counted_language)  # type: ignore[arg-type]

        self.assertIsNone(solver.solve([{"A"}, set(), {"B"}]))
        self.assertEqual(counted_language.automaton_calls, 0)

        self.assertEqual(solver.solve([{"A"}, {"B"}, {"A"}]), ("A", "B", "A"))
        self.assertEqual(solver.solve([{"B"}, {"A"}, {"B"}]), ("B", "A", "B"))
        self.assertEqual(counted_language.automaton_calls, 1)

    def test_slot_csp_randomized_search_is_seeded_and_varies_solutions(self):
        domains = [set(language().alphabet) for _ in range(5)]

        first_solver = SlotCSP(language(), rng=random.Random(17))
        second_solver = SlotCSP(language(), rng=random.Random(17))
        first = tuple(first_solver.solve(domains) for _ in range(8))
        second = tuple(second_solver.solve(domains) for _ in range(8))

        self.assertEqual(first, second)
        self.assertGreater(len(set(first)), 1)
        self.assertTrue(
            all(sequence is not None and language().accepts(sequence) for sequence in first)
        )

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

    def test_3d_anchor_candidates_use_all_available_cross_axes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = GeneratorConfig.model_validate(
                config_dict(str(Path(temp_dir) / "scenarios.json"), dimensions=3)
            )
        board = Board.empty(3).place(
            Move(start=(-1, 0, 0), axis=0, sequence=("A", "B", "C"))
        )

        candidates = top_anchors(board, 3, 20, config.scoring)
        center_axes = {
            candidate.axis
            for candidate in candidates
            if candidate.coord == (0, 0, 0)
        }

        self.assertEqual(center_axes, {1, 2})

    def test_3d_board_allows_crossing_on_third_axis(self):
        sl = language()
        board = Board.empty(3)
        for move in (
            Move(start=(-1, 0, 0), axis=0, sequence=("A", "B", "C")),
            Move(start=(0, -1, 0), axis=1, sequence=("A", "B", "C")),
        ):
            board = board.place(move)
        move = Move(start=(0, 0, -1), axis=2, sequence=("A", "B", "C"))

        result = validate_move(board, sl, ("A", "C"), move)

        self.assertTrue(result.ok)

    def test_2d_visualization_requires_and_applies_hidden_axis_slice(self):
        board = Board.empty(3).place(
            Move(start=(0, 0, 0), axis=2, sequence=("A", "B", "C"))
        )

        with self.assertRaisesRegex(ValueError, "slice_coords"):
            plot_board_2d(board)
        figure = plot_board_2d(board, slice_coords={2: 1})
        visible_symbols = tuple(figure.data[0].text)

        self.assertIn("B", visible_symbols)
        self.assertNotIn("A", visible_symbols)
        self.assertNotIn("C", visible_symbols)
        self.assertEqual(figure.data[0].type, "scatter")
        self.assertEqual(figure.data[0].mode, "markers+text")
        self.assertEqual(figure.data[0].marker.symbol, "square")

    def test_2d_visualization_uses_marker_letters_and_heatmap(self):
        board = Board.empty(2).place(
            Move(start=(-1, 0), axis=0, sequence=("A", "B", "C"))
        )

        figure = plot_board_2d(board)

        self.assertEqual(figure.data[0].type, "scatter")
        self.assertEqual(figure.data[0].mode, "markers+text")
        self.assertEqual(tuple(figure.data[0].text), ("A", "B", "C"))
        self.assertEqual(figure.data[0].marker.color[0], "#0057d9")
        self.assertEqual(figure.data[0].marker.color[1], "#e60023")
        self.assertEqual(figure.data[0].marker.line.color, "rgba(0, 0, 0, 0)")
        self.assertEqual(figure.data[0].marker.line.width, 0)
        self.assertEqual(figure.layout.plot_bgcolor, "rgba(0, 0, 0, 0)")
        self.assertEqual(
            figure.data[0].textfont.family,
            "DejaVu Sans Mono, Menlo, Consolas, monospace",
        )
        highlighted = plot_board_2d(board, highlight_coords={(0, 0)})

        self.assertEqual(highlighted.data[0].marker.color[1], "#ff00b8")

    def test_3d_visualization_selects_slice_from_higher_dimensional_board(self):
        board = Board.empty(5)
        for move in (
            Move(start=(-1, 0, 0, 4, -2), axis=0, sequence=("A", "B", "C")),
            Move(start=(-1, 0, 0, 5, -2), axis=0, sequence=("D", "E", "F")),
        ):
            board = board.place(move)

        with self.assertRaisesRegex(ValueError, r"missing \[3, 4\]"):
            plot_board_3d(board)
        figure = plot_board_3d(board, slice_coords={3: 4, 4: -2})

        self.assertEqual(tuple(figure.data[2].text), ("A", "B", "C"))

    def test_3d_visualization_uses_opaque_cube_nodes_with_face_letters_and_heatmap(self):
        board = Board.empty(3).place(
            Move(start=(-1, 0, 0), axis=0, sequence=("A", "B", "C"))
        )

        figure = plot_board_3d(board)

        self.assertEqual(figure.data[0].type, "mesh3d")
        self.assertEqual(figure.data[0].opacity, 1.0)
        self.assertEqual(figure.data[1].type, "mesh3d")
        self.assertEqual(figure.data[1].color, "#15181d")
        self.assertEqual(figure.data[2].type, "scatter3d")
        self.assertEqual(tuple(figure.data[2].text), ("A", "B", "C"))
        self.assertEqual(len(figure.data[0].facecolor), 36)
        self.assertGreater(len(set(figure.data[0].facecolor)), 1)
        self.assertEqual(figure.layout.scene.aspectmode, "manual")
        self.assertGreater(figure.layout.scene.camera.eye.x, 3.5)
        self.assertLess(figure.layout.scene.camera.eye.y, -4.0)
        zoomed_in = plot_board_3d(board, camera_zoom=1.0)

        self.assertLess(zoomed_in.layout.scene.camera.eye.x, figure.layout.scene.camera.eye.x)
        self.assertEqual(tuple(figure.layout.sliders), ())
        highlighted = plot_board_3d(board, highlight_coords={(0, 0, 0)})

        self.assertIn("#ff00b8", highlighted.data[0].facecolor)

    def test_3d_animation_shows_generation_steps_with_slider(self):
        scenario = {
            "schema_version": 1,
            "config_name": "unit",
            "config": {},
            "seed": 11,
            "grammar_name": "unit",
            "forbidden_snippets": [],
            "initial_board": {
                "dimensions": 3,
                "occupied": [
                    [[-1, 0, 0], "A"],
                    [[0, 0, 0], "B"],
                    [[1, 0, 0], "C"],
                ],
                "segments": [
                    {"start": [-1, 0, 0], "axis": 0, "sequence": ["A", "B", "C"]}
                ],
            },
            "transitions": [
                {
                    "rack": ["A", "C"],
                    "move": [[0, -1, 0], 1, ["A", "B", "C"]],
                    "placed": [
                        [[0, -1, 0], "A"],
                        [[0, 1, 0], "C"],
                    ],
                }
            ],
        }

        figure = animate_scenario_3d(scenario)

        self.assertEqual([step.label for step in figure.layout.sliders[0].steps], ["0", "1"])
        self.assertEqual([frame.name for frame in figure.frames], ["0", "1"])
        self.assertEqual(figure.data[0].type, "scatter3d")
        self.assertEqual(figure.frames[1].data[0].type, "scatter3d")

    def test_2d_animation_shows_only_current_step_number_beside_slider(self):
        config = GeneratorConfig.model_validate(
            config_dict("unused.json") | {"target_witness_count": 1}
        )
        scenario = scenario_run_to_json(ScenarioGenerator(config).generate())

        figure = animate_scenario_2d(scenario)
        slider = figure.layout.sliders[0]

        self.assertTrue(slider.currentvalue.visible)
        self.assertEqual(slider.currentvalue.prefix, "")
        self.assertEqual(slider.currentvalue.xanchor, "left")
        self.assertEqual(slider.currentvalue.font.color, "#15181d")
        self.assertEqual([step.label for step in slider.steps], ["0", "1"])
        self.assertEqual(slider.font.color, "rgba(0, 0, 0, 0)")
        self.assertEqual(slider.tickcolor, "rgba(0, 0, 0, 0)")
        self.assertIsNone(slider.x)
        self.assertIsNone(slider.len)
        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].type, "scatter")
        self.assertEqual(figure.data[0].mode, "markers+text")
        self.assertEqual(len(figure.frames[0].data), 1)
        self.assertEqual(figure.frames[0].data[0].type, "scatter")

    def test_2d_image_animation_uses_single_png_trace_per_frame(self):
        config = GeneratorConfig.model_validate(
            config_dict("unused.json") | {"target_witness_count": 1}
        )
        scenario = scenario_run_to_json(ScenarioGenerator(config).generate())

        figure = animate_scenario_2d_image(scenario)

        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].type, "image")
        self.assertTrue(figure.data[0].source.startswith("data:image/png;base64,"))
        self.assertEqual([step.label for step in figure.layout.sliders[0].steps], ["0", "1"])
        self.assertEqual(len(figure.frames[0].data), 1)

    def test_2d_canvas_animation_returns_preloaded_html(self):
        config = GeneratorConfig.model_validate(
            config_dict("unused.json") | {"target_witness_count": 1}
        )
        scenario = scenario_run_to_json(ScenarioGenerator(config).generate())

        html = animate_scenario_2d_canvas(scenario)
        payload = html.data if hasattr(html, "data") else html

        self.assertIn("<canvas", payload)
        self.assertIn("data:image/png;base64,", payload)
        self.assertIn('type="range"', payload)

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

    def test_validator_rejects_valid_cross_axis_sequence_extension(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(0, -2), axis=1, sequence=("A", "B", "A")),
            Move(start=(1, 0), axis=1, sequence=("B", "A", "B")),
        ):
            board = board.place(move)
        move = Move(start=(0, 1), axis=0, sequence=("B", "A", "B"))

        result = validate_move(board, sl, ("B", "B"), move)

        self.assertFalse(result.ok)
        self.assertEqual(result.failure_type, "word_extension")

    def test_detailed_validator_reports_granular_fields(self):
        sl = language()
        board = Board.empty(2).place(Move(start=(-1, 0), axis=0, sequence=("A", "B", "C")))
        move = Move(start=(0, -1), axis=1, sequence=("A", "B", "C"))

        result = validate_move(board, sl, ("A", "C"), move)
        report = validate_move_detailed(board, sl, ("A", "C"), move)

        self.assertEqual(report.result, result)
        self.assertTrue(report.overall)
        self.assertTrue(report.sequence_valid)
        self.assertTrue(report.min_length_fulfilled)
        self.assertTrue(report.spatial_valid)
        self.assertTrue(report.overlap_valid)
        self.assertTrue(report.no_word_extension)
        self.assertTrue(report.cross_words_valid)
        self.assertEqual(report.rack_symbols_used, 2)
        self.assertEqual(report.rack_usage_ratio, 1.0)

    def test_granular_evaluation_flags_cross_axis_word_extension(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(0, -2), axis=1, sequence=("A", "B", "A")),
            Move(start=(1, 0), axis=1, sequence=("B", "A", "B")),
        ):
            board = board.place(move)

        evaluation = evaluate_granular(
            board,
            sl,
            ("B", "B"),
            SubmittedMove(start=(0, 1), axis=0, sequence=("B", "A", "B")),
        )

        self.assertFalse(evaluation.overall)
        self.assertEqual(evaluation.failure_type, "word_extension")
        self.assertFalse(evaluation.no_word_extension)

    def test_templates_prune_deterministic_implicit_word_extensions_before_solving(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(-2, -2), axis=1, sequence=("B", "A", "B")),
            Move(start=(-1, -2), axis=1, sequence=("A", "B", "A")),
            Move(start=(0, -2), axis=1, sequence=("B", "A", "B")),
            Move(start=(1, -2), axis=1, sequence=("A", "B", "A")),
        ):
            board = board.place(move)
        anchor = AnchorCandidate((-2, -2), "B", 0, 0.0, 0.0, 0)
        extension_start = (-2, -2)
        scoring = GeneratorConfig.model_validate(config_dict("unused.json")).scoring

        unpruned = top_templates(board, (anchor,), 5, 10, scoring)
        pruned = top_templates(
            board,
            (anchor,),
            5,
            10,
            scoring,
            prune=lambda template: extends_existing_axis_sequence(
                board, template.covered_coords, template.axis, sl
            ),
        )

        self.assertTrue(
            any(candidate.template.start == extension_start for candidate in unpruned)
        )
        self.assertFalse(
            any(candidate.template.start == extension_start for candidate in pruned)
        )

    def test_templates_prune_deterministic_cross_axis_word_extensions(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(0, -2), axis=1, sequence=("A", "B", "A")),
            Move(start=(1, 0), axis=1, sequence=("B", "A", "B")),
        ):
            board = board.place(move)
        scoring = GeneratorConfig.model_validate(config_dict("unused.json")).scoring
        anchor = AnchorCandidate((1, 1), "A", 0, 0.0, 0.0, 0)

        templates = top_templates(
            board,
            (anchor,),
            3,
            10,
            scoring,
            prune=lambda template: extends_existing_sequence_in_any_axis(
                board, template.covered_coords, template.axis, sl
            ),
        )

        self.assertFalse(
            any(candidate.template.start == (0, 1) for candidate in templates)
        )

    def test_templates_prune_empty_cross_domains_before_ranking(self):
        sl = language()
        board = Board.empty(2)
        for move in (
            Move(start=(-1, 0), axis=0, sequence=("A", "B", "C")),
            Move(start=(1, -2), axis=1, sequence=("B", "C", "C")),
        ):
            board = board.place(move)
        config = GeneratorConfig.model_validate(config_dict("unused.json"))
        generator = ScenarioGenerator(config)
        generator.language = sl
        anchor = AnchorCandidate((0, 0), "B", 1, 0.0, 0.0, 0)

        templates = top_templates(
            board,
            (anchor,),
            3,
            10,
            config.scoring,
            domains_for_template=lambda template: generator._domains_for_template(
                board, template
            ),
        )

        self.assertFalse(
            any(candidate.template.start == (0, -1) for candidate in templates)
        )

    def test_generator_progressive_widening_expands_only_new_anchor_batches(self):
        data = config_dict("unused.json") | {
            "length_distribution": {"start": 3, "end": 3},
            "top_anchor_count": 1,
            "target_witness_count": 1,
        }
        config = GeneratorConfig.model_validate(data)
        generator = ScenarioGenerator(config)
        generator.language = language()
        generator.solver = SlotCSP(generator.language)
        board = Board.empty(2).place(
            Move(start=(-1, 0), axis=0, sequence=("A", "B", "C"))
        )
        first = AnchorCandidate((-1, 0), "A", 1, 2.0, 0.0, 1)
        second = AnchorCandidate((0, 0), "B", 1, 1.0, 1.0, 1)
        template = SlotTemplate(
            anchor_coord=(0, 0),
            anchor_symbol="B",
            axis=1,
            length=3,
            anchor_index=1,
            start=(0, -1),
            covered_coords=((0, -1), (0, 0), (0, 1)),
        )
        candidate = TemplateCandidate(
            template=template,
            score=1.0,
            distance_to_centroid=0.0,
            domains=(frozenset({"A"}), frozenset({"B"}), frozenset({"A"})),
            domain_slack=2,
        )
        batches: list[tuple[AnchorCandidate, ...]] = []

        def fake_templates(
            _board: Board,
            anchors: tuple[AnchorCandidate, ...],
            *_args: object,
            **_kwargs: object,
        ) -> tuple[TemplateCandidate, ...]:
            batches.append(anchors)
            return () if anchors == (first,) else (candidate,)

        with (
            patch("src.generator.engine.top_anchors", return_value=(first, second)),
            patch("src.generator.engine.top_templates", side_effect=fake_templates),
        ):
            _, transition, _ = generator._generate_next_transition(board)

        self.assertIsNotNone(transition)
        self.assertEqual(batches, [(first,), (second,)])

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
        self.assertEqual(resolve_config_path("generator_v1").parent.name, "generation")
        invalid = config_dict("unused.json")
        invalid.pop("top_template_count")
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
        self.assertIn('"grammar_name"', written_text)
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

    def test_generator_accepts_nd_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for dimensions in (3, 4, 7):
                with self.subTest(dimensions=dimensions):
                    data = config_dict(
                        str(Path(temp_dir) / "scenarios.json"),
                        dimensions=dimensions,
                    )
                    data["target_witness_count"] = 1
                    config = GeneratorConfig.model_validate(data)

                    run = ScenarioGenerator(config).generate()
                    boards = reconstruct_boards(run)

                    self.assertEqual(run.initial_board.dimensions, dimensions)
                    self.assertEqual(len(run.transitions), 1)
                    self.assertTrue(
                        all(
                            len(coord) == dimensions
                            for board in boards
                            for coord in board.cells
                        )
                    )

    def test_generator_failure_reports_exhausted_lengths_and_config_levers(self):
        data = config_dict("unused.json") | {
            "length_distribution": {"start": 3, "end": 3},
            "top_anchor_count": 1,
            "max_anchor_count": 1,
            "top_template_count": 1,
            "target_witness_count": 10,
        }
        config = GeneratorConfig.model_validate(data)

        with self.assertRaisesRegex(
            GenerationError,
            r"All lengths in length_distribution were tried once",
        ):
            ScenarioGenerator(config).generate()

    def test_generator_tries_each_length_once_per_board_state(self):
        data = config_dict("unused.json") | {
            "length_distribution": {"start": 3, "end": 5},
        }
        config = GeneratorConfig.model_validate(data)
        board = Board.empty(2)
        for move in (
            Move(start=(0, 0), axis=0, sequence=("A",)),
            Move(start=(0, 0), axis=1, sequence=("A",)),
        ):
            board = board.place(move)

        _, transition, failures = ScenarioGenerator(config)._generate_next_transition(board)

        self.assertIsNone(transition)
        self.assertEqual(sorted(failure.length for failure in failures), [3, 4, 5])
        self.assertEqual({failure.reason for failure in failures}, {"no_anchor_candidates"})

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
        self.assertIn("placed", data["transitions"][0])
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
            RepresenterConfig(),
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
