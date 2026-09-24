from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.benchmark.scoring import tile_multiplier
from src.domain.board import Board
from src.domain.models import Move
from visualization.src.artifact_catalog import (
    display_evaluation_config_run_catalog,
    evaluation_attempts,
    evaluation_case_sets,
    evaluation_runs,
    evaluation_runs_for_config,
    resolve_attempt_selection,
    resolve_evaluation_attempt_selection,
    resolve_evaluation_run_config_selection,
    resolve_evaluation_run_selection,
    resolve_scenario_selection,
    scenario_sources,
    scenarios,
)
from visualization.src.board_figures import (
    _score_bitmap_mask_2d,
    plot_board_2d,
    plot_playground_board_2d,
)
from visualization.src.board_3d import (
    _plane_hexagon,
    _plane_lattice_coords,
    plot_board_3d,
    write_grounded_html,
)
from visualization.src.evaluation_figures import plot_attempt_move
from visualization.src.notebook_workflows import ModelPlaygroundSession


class ArtifactCatalogTests(unittest.TestCase):
    def test_evaluation_catalog_resolves_latest_completed_run_with_aggregate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runs = root / "outputs" / "evaluation" / "case-a" / "runs"
            self._write_run(runs / "older", status="complete", created="2026-01-01", aggregate=True)
            self._write_run(runs / "newer", status="complete", created="2026-01-02", aggregate=True)
            self._write_run(runs / "unfinished", status="in_progress", created="2026-01-03")

            self.assertEqual(evaluation_case_sets(project_root=root), ("case-a",))
            self.assertEqual(
                [record.run_id for record in evaluation_runs("case-a", project_root=root)],
                ["unfinished", "newer", "older"],
            )
            self.assertEqual(
                resolve_evaluation_run_selection("case-a", project_root=root).name,
                "newer",
            )

    def test_attempt_catalog_filters_and_resolves_semantic_coordinates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "outputs" / "evaluation" / "case-a" / "runs" / "run-a"
            self._write_run(run_dir, status="complete", created="2026-01-01", aggregate=True)
            self._write_json(
                run_dir / "attempts" / "job-a.json",
                {
                    "job_id": "job-a",
                    "model": "model-a",
                    "board_size": 10,
                    "sampling_round": 2,
                    "status": "complete",
                    "reasoning_effort": "high",
                },
            )

            records = evaluation_attempts(
                run_dir,
                model="model-a",
                board_size=10,
                sampling_round=2,
            )
            self.assertEqual([record.job_id for record in records], ["job-a"])
            self.assertEqual(
                resolve_evaluation_attempt_selection(
                    "case-a",
                    run="run-a",
                    model="model-a",
                    board_size=10,
                    sampling_round=2,
                    project_root=root,
                ).name,
                "job-a.json",
            )
            self.assertEqual(
                resolve_attempt_selection(
                    run_dir,
                    model="model-a",
                    board_size=10,
                    sampling_round=2,
                ).name,
                "job-a.json",
            )

    def test_run_config_catalog_includes_regular_and_exported_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            regular = (
                root
                / "outputs"
                / "evaluation"
                / "case-a"
                / "runs"
                / "regular"
            )
            exported = root / "outputs" / "paper-v1" / "runs" / "exported"
            self._write_run(
                regular,
                status="complete",
                created="2026-01-01",
                aggregate=True,
                run_config="paper-run",
            )
            self._write_run(
                exported,
                status="complete",
                created="2026-01-02",
                aggregate=True,
                run_config="paper-run",
            )

            records = evaluation_runs_for_config("paper-run", project_root=root)

            self.assertEqual([record.run_id for record in records], ["exported", "regular"])
            self.assertEqual(
                resolve_evaluation_run_config_selection(
                    "paper-run",
                    1,
                    project_root=root,
                ),
                exported,
            )
            self.assertEqual(
                resolve_evaluation_run_config_selection(
                    "paper-run",
                    "regular",
                    project_root=root,
                ),
                regular,
            )

    def test_catalog_html_uses_notebook_theme_colors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "outputs" / "evaluation" / "case-a" / "runs" / "run-a"
            self._write_run(
                run_dir,
                status="complete",
                created="2026-01-01",
                aggregate=True,
                run_config="test-run",
            )

            catalog = display_evaluation_config_run_catalog(
                "test-run",
                project_root=root,
            )
            markup = catalog.data if hasattr(catalog, "data") else str(catalog)

            self.assertIn("--vscode-editor-foreground", markup)
            self.assertIn("--vscode-editor-background", markup)
            self.assertNotIn("color:#1f2937", markup)

    def test_scenario_catalog_uses_source_and_board_coordinates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "outputs" / "collection-a" / "scenarios" / "set.b010.r02.json"
            self._write_json(path, {"config_name": "set.b010.r02", "seed": 17})

            self.assertEqual(scenario_sources(project_root=root), ("generated/collection-a",))
            records = scenarios(
                "generated/collection-a",
                board_size=10,
                sampling_round=2,
                project_root=root,
            )
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].seed, 17)
            self.assertEqual(
                resolve_scenario_selection(
                    "generated/collection-a",
                    board_size=10,
                    sampling_round=2,
                    project_root=root,
                ),
                path,
            )

    def test_board_plot_adds_small_score_labels_to_tiles(self):
        board = Board.empty(2).place(
            Move(start=(0, 0), axis=0, sequence=("A", "B", "C"))
        )

        figure = plot_board_2d(
            board,
            letter_scores={"A": 1, "B": 2, "C": 3},
        )

        self.assertEqual(len(figure.data), 2)
        self.assertEqual(tuple(figure.data[1].text), ("1", "2", "3"))
        self.assertEqual(figure.data[1].mode, "text")
        self.assertEqual(tuple(figure.data[1].x), (0.27, 1.27, 2.27))
        self.assertEqual(tuple(figure.data[1].y), (-0.27, -0.27, -0.27))
        self.assertLess(figure.data[1].textfont.size, figure.data[0].textfont.size)

        mask = _score_bitmap_mask_2d("2", 42)
        ys, xs = mask.nonzero()
        self.assertGreater(len(xs), 0)
        self.assertGreater(float(xs.mean()), 21.0)
        self.assertGreater(float(ys.mean()), 21.0)

    def test_playground_2d_keeps_scrabble_tiles_and_marks_bonus_cells(self):
        board = Board.empty(2).place(
            Move(start=(0, 0), axis=0, sequence=("A", "B", "C", "D", "E"))
        ).place(Move(start=(0, 0), axis=1, sequence=("A", "F", "G")))

        figure = plot_playground_board_2d(board, letter_scores={"A": 1, "C": 3, "G": 2})

        bonus = next(trace for trace in figure.data if "×2" in trace.text)
        tiles = next(trace for trace in figure.data if trace.customdata is not None)
        self.assertEqual(bonus.marker.symbol, "square")
        self.assertIn((1, 1), set(zip(bonus.x, bonus.y)))
        self.assertEqual(tiles.marker.symbol, "square")
        self.assertEqual(set(tiles.text), set("ABCDEFG"))
        rims = {
            tuple(row[0]): color
            for row, color in zip(tiles.customdata, tiles.marker.line.color, strict=True)
        }
        self.assertEqual(rims[(2, 0)], "#9560ad")
        self.assertEqual(rims[(0, 2)], "#cf624c")
        self.assertEqual(figure.layout.plot_bgcolor, "#f8fbfd")

    def test_playground_3d_routes_move_to_grounded_view(self):
        board = Board.empty(3).place(
            Move(start=(-1, 0, 0), axis=0, sequence=("A", "B", "C"))
        )
        move = Move(start=(1, 0, 0), axis=1, sequence=("C", "D", "E"))
        context = SimpleNamespace(
            board=board, parsed_move=move, ground_truth_move=move,
            language=SimpleNamespace(letter_score_map=lambda: {"A": 1, "B": 2, "C": 3}),
        )
        figure, = plot_attempt_move(context)

        self.assertEqual(figure.layout.scene.dragmode, "turntable")
        self.assertIn("New tile", [trace.name for trace in figure.data])
        self.assertIn("Reused tile", [trace.name for trace in figure.data])
        session = ModelPlaygroundSession(picker=None, case=None, mode="saved", context=context)
        with patch("visualization.src.notebook_workflows.display_grounded_3d") as grounded:
            with patch("visualization.src.notebook_workflows.display") as regular:
                session.show_witness()
        grounded.assert_called_once()
        regular.assert_not_called()

    def test_3d_view_shows_cell_level_multiplier_planes(self):
        board = Board.empty(3).place(
            Move(start=(-2, 0, 0), axis=0, sequence=("A", "B", "C", "D", "E"))
        )
        figure = plot_board_3d(board)

        self.assertEqual(board.dimensions, 3)
        self.assertEqual(
            [button.label for button in figure.layout.updatemenus[0].buttons],
            ["Σ=2"],
        )
        vertices = _plane_hexagon(2, (0, 0, 0), 12)
        self.assertEqual(len(vertices), 6)
        for vertex in vertices:
            self.assertAlmostEqual(sum(vertex), 2)
        center = tuple(
            sum(coord[axis] for coord in board.cells) / len(board.cells)
            for axis in range(3)
        )
        lattice = _plane_lattice_coords(2, center, 12)
        self.assertEqual({tile_multiplier(coord) for coord in lattice}, {2, 3, 4})
        self.assertEqual(
            {trace.name for trace in figure.data if trace.name and trace.name.startswith("Available ×")},
            {"Available ×2", "Available ×3", "Available ×4"},
        )
        self.assertEqual(figure.layout.scene.dragmode, "turntable")
        self.assertIsNone(figure.layout.width)
        self.assertEqual(figure.layout.height, 500)
        self.assertEqual(figure.layout.scene.camera.up.z, 1)
        self.assertEqual(figure.layout.scene.camera.projection.type, "orthographic")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_grounded_html(figure, Path(temp_dir) / "preview.html")
            html = path.read_text(encoding="utf-8")
        self.assertIn("graph.on('plotly_relayout', constrain)", html)
        self.assertNotIn("plotly_relayouting", html)
        self.assertIn("Math.asin", html)

    @staticmethod
    def _write_run(
        run_dir: Path,
        *,
        status: str,
        created: str,
        aggregate: bool = False,
        run_config: str = "test-run",
    ) -> None:
        ArtifactCatalogTests._write_json(
            run_dir / "run-manifest.json",
            {
                "run_id": run_dir.name,
                "run_config": run_config,
                "case_set": "case-a",
                "status": status,
                "created_at": created,
                "completed_at": created if status == "complete" else None,
                "completed_jobs": 1 if status == "complete" else 0,
                "error_jobs": 0,
                "config": {"models": {"model-a": ["all"]}},
            },
        )
        if aggregate:
            ArtifactCatalogTests._write_json(run_dir / "aggregate.json", {})

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
