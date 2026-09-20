from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
from visualization.src.board_figures import _score_bitmap_mask_2d, plot_board_2d


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
