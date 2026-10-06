"""Regression coverage for overview denominators, quality and cost accounting."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from visualization.src.overview_data import attempt_record, overview_payload, reported_cost
from visualization.src.case_playground import PreparedCaseRecord
from visualization.src.overview_selection import filtered_run_aggregate
from visualization.src.overview_figures import (
    display_run_summary,
    plot_case_outcomes,
    plot_move_quality,
    plot_outcome_composition,
    plot_rate_heatmaps,
    plot_runtime,
    plot_token_usage,
)


def attempt(model="model-a", dimension=2, size=20, round_index=0, **changes):
    return {
        "case_id": f"pilot.d{dimension}.b{size}.r{round_index}",
        "model": model, "dimensions": dimension, "board_size": size,
        "sampling_round": round_index, "language_representation": "forbidden-snippets",
        "reasoning_effort": "high", "status": "complete",
        "evaluation": {"overall": True, "letter_score_total": 12, "overlap_count": 2},
        "optimal_score": 20,
        "usage": {"cost": 0.2, "completion_tokens": 100, "prompt_tokens": 30},
        "model_config": {"request_max_tokens": 150}, "llm_elapsed_seconds": 60,
        **changes,
    }


def aggregate(attempts):
    return {"overview": overview_payload(attempts, attempts, run_id="test-run")}


class OverviewTests(unittest.TestCase):
    def test_run_filter_retains_full_cost_and_enriches_transport_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "attempts").mkdir()
            rows = [attempt(), attempt(dimension=3, status="transport_error", usage={})]
            cases = tuple(PreparedCaseRecord(r["case_id"], r["dimensions"], 20, 0,
                                             root / f"{r['case_id']}.json") for r in rows)
            # Transport artifacts can identify their case solely through case_file.
            rows[1]["case_file"] = str(cases[1].path)
            for key in ["case_id", "dimensions", "board_size", "sampling_round"]:
                rows[1].pop(key)
            for index, row in enumerate(rows):
                (root / "attempts" / f"{index}.json").write_text(json.dumps(row))
            _, result, count = filtered_run_aggregate(
                cases, (SimpleNamespace(path=root, run_id="test"),), 1, [3], [20], [0],
            )
        self.assertEqual(count, 1)
        self.assertEqual(result["overview"]["run_cost"]["usd"], 0.2)
        self.assertIsNone(result["overview"]["selection_cost"]["usd"])
        self.assertEqual(result["overview"]["attempts"][0]["dimensions"], 3)
        self.assertEqual(result["overview"]["attempts"][0]["case_id"], cases[1].case_id)
        self.assertEqual(result["overall"]["transport_errors"], 1)

    def test_costs_preserve_missing_and_zero_and_keep_full_run_when_filtered(self):
        rows = [attempt(usage={"cost": 0}), attempt(dimension=3, usage={}),
                attempt(dimension=4, usage={"cost": 0.4}, retry_count=2)]
        data = overview_payload(rows, rows[:2], run_id="test")
        self.assertEqual(data["run_cost"]["usd"], 0.4)
        self.assertEqual(data["selection_cost"]["usd"], 0)
        self.assertEqual(data["selection_cost"]["missing"], 1)
        self.assertEqual(data["run_cost"]["retries"], 2)
        self.assertIsNone(reported_cost(rows[1:2])["usd"])
        self.assertEqual(data["model_costs"]["model-a"]["run"]["reported"], 2)
        self.assertIn("$0.00", display_run_summary({"overview": data}).data)

    def test_only_valid_moves_have_quality_and_optima_are_not_inferred(self):
        invalid = attempt(evaluation={"overall": False, "failure_type": "sequence",
                                      "letter_score_total": 0, "overlap_count": 1})
        truncated = attempt(evaluation={"overall": False, "failure_type": "truncated"})
        historical = attempt(optimal_score=None)
        self.assertEqual(attempt_record(attempt())["score_ratio"], 0.6)
        for row in [invalid, truncated]:
            record = attempt_record(row)
            self.assertIsNone(record["score"])
            self.assertIsNone(record["overlap"])
            self.assertIsNone(record["score_ratio"])
        self.assertIsNone(attempt_record(historical)["score_ratio"])
        self.assertEqual(attempt_record(historical)["score"], 12)
        self.assertIsNone(attempt_record(attempt(optimal_score=0))["score_ratio"])

    def test_provider_finish_error_is_distinct_from_format_failure(self):
        row = attempt(provider_metadata={"finish_reason": "error"},
                      evaluation={"overall": False, "failure_type": "parse"})
        record = attempt_record(row)
        self.assertEqual(record["outcome"], "provider")
        self.assertEqual(record["failure"], "parse")
        self.assertTrue(record["completed"])
        self.assertEqual(attempt_record(attempt(status="transport_error"))["outcome"], "transport")

    def test_heatmaps_pool_counts_across_rounds_and_preserve_unmeasured_cells(self):
        rows = [attempt(), attempt(round_index=1, evaluation={"overall": False, "failure_type": "truncated"}),
                attempt(round_index=2, status="transport_error"),
                attempt(dimension=3, status="transport_error"),
                attempt(model="model-b", dimension=3, size=100)]
        figure = plot_rate_heatmaps(aggregate(rows))[0]
        pass_a = figure.data[0]
        self.assertEqual(list(pass_a.x), ["20", "100"])
        self.assertEqual(list(pass_a.y), ["2D", "3D"])
        self.assertEqual(pass_a.z[0][0], 0.5)  # 1/2 completed, not 1/3 scheduled
        self.assertIsNone(pass_a.z[1][0])  # transport-only, not zero percent
        self.assertIsNone(pass_a.z[0][1])  # not scheduled
        self.assertEqual(figure.data[1].text[0], "1/2")
        self.assertEqual(figure.data[1].text[2], "—")
        buttons = figure.layout.updatemenus[0].buttons
        self.assertFalse(buttons[0].args[1]["coloraxis.reversescale"])
        self.assertTrue(all(button.args[1]["coloraxis.reversescale"] for button in buttons[1:]))
        transport_button = figure.layout.updatemenus[0].buttons[3]
        visible = transport_button.args[0]["visible"]
        transport_a = next(trace for trace, shown in zip(figure.data, visible)
                           if shown and trace.type == "heatmap")
        self.assertAlmostEqual(transport_a.z[0][0], 1 / 3)
        self.assertEqual(transport_a.z[1][0], 1)

    def test_outcome_composition_includes_success_and_all_provider_failures(self):
        rows = [attempt(), attempt(dimension=3, status="transport_error"),
                attempt(dimension=4, provider_metadata={"finish_reason": "error"},
                        evaluation={"overall": False, "failure_type": "parse"})]
        figure = plot_outcome_composition(aggregate(rows))[0]
        self.assertEqual({trace.name for trace in figure.data},
                         {"Valid", "Provider response error", "Transport / request error"})
        self.assertAlmostEqual(sum(trace.x[0] for trace in figure.data), 1)
        self.assertTrue(all(trace.customdata[0][1] == 3 for trace in figure.data))

    def test_metric_controls_preserve_legends_and_set_shared_scales(self):
        rows = [attempt(), attempt(model="model-b", dimension=3, size=100,
                                   evaluation={"overall": False, "failure_type": "truncated"})]
        figure = plot_move_quality(aggregate(rows))[0]
        buttons = figure.layout.updatemenus[0].buttons
        self.assertEqual([b.label for b in buttons], ["Score / certified optimum", "Word score"])
        self.assertEqual(figure.layout.yaxis.range, figure.layout.yaxis2.range)
        self.assertEqual(figure.layout.xaxis.domain, figure.layout.xaxis2.domain)
        self.assertNotEqual(figure.layout.yaxis.domain, figure.layout.yaxis2.domain)
        self.assertIn("No eligible observations", str(figure.layout.annotations))
        for button in buttons:
            visibility = button.args[0]["visible"]
            self.assertEqual(len(visibility), len(figure.data))
            self.assertTrue(all(visibility[i] for i, trace in enumerate(figure.data) if trace.showlegend is not False))
        for function in [plot_case_outcomes, plot_move_quality, plot_token_usage, plot_runtime]:
            for fig in function(aggregate(rows)):
                self.assertTrue(fig.to_json())

    def test_numeric_board_sizes_preserve_distances_in_point_charts(self):
        rows = [attempt(size=size) for size in [20, 100, 300]]
        for function in [plot_move_quality, plot_token_usage, plot_runtime]:
            figure = function(aggregate(rows))[0]
            points = next(trace for trace in figure.data if trace.mode == "markers" and trace.x[0] is not None)
            self.assertEqual(list(points.x), [20, 100, 300])
            self.assertEqual(figure.layout.xaxis.type, "linear")
            if function == plot_move_quality:
                self.assertEqual(points.marker.symbol, "circle")

    def test_outcomes_are_sorted_by_valid_share_within_failure_profile(self):
        rows = [attempt(model="many", round_index=i, evaluation={
            "overall": i < 2, "failure_type": None if i < 2 else "sequence",
        }) for i in range(10)] + [attempt(model="one"), attempt(
            model="one", round_index=1, evaluation={"overall": False, "failure_type": "sequence"},
        )]
        figure = plot_outcome_composition(aggregate(rows))[0]
        self.assertEqual(list(figure.data[0].y), ["one", "many"])

    def test_matching_failure_profiles_stay_together_despite_different_pass_rates(self):
        rows = []
        for model, passed, failure in [
            ("semantic-high", 3, "sequence"), ("truncated-mid", 2, "truncated"),
            ("semantic-low", 1, "sequence"), ("truncated-zero", 0, "truncated"),
        ]:
            rows.extend(attempt(model=model, round_index=i, evaluation={
                "overall": i < passed, "failure_type": None if i < passed else failure,
            }) for i in range(4))
        figure = plot_outcome_composition(aggregate(rows))[0]
        self.assertEqual(list(figure.data[0].y), [
            "semantic-high", "semantic-low", "truncated-mid", "truncated-zero",
        ])

    def test_case_matrix_retains_rounds_and_splits_long_selections(self):
        rows = [attempt(round_index=i) for i in range(25)]
        figures = plot_case_outcomes(aggregate(rows))
        self.assertEqual([len(f.data[0].x) for f in figures], [24, 1])
        self.assertIn("r24", figures[1].layout.xaxis.ticktext[0])

    def test_representation_and_effort_are_not_silently_pooled(self):
        rows = [attempt(), attempt(reasoning_effort="low"), attempt(language_representation="allowed")]
        self.assertEqual(len(plot_rate_heatmaps(aggregate(rows))), 3)

    def test_runtime_sums_retry_time_and_wait_without_inventing_missing_values(self):
        row = attempt(llm_elapsed_seconds_total=90, retry_wait_seconds_total=30)
        self.assertEqual(attempt_record(row)["runtime_minutes"], 2)
        self.assertIsNone(attempt_record(attempt(llm_elapsed_seconds=None))["runtime_minutes"])


if __name__ == "__main__":
    unittest.main()
