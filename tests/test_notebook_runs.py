import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from support import FixtureModelsMixin, config_dict
from src.generator.config import GeneratorConfig
from src.generator.engine import ScenarioGenerator
from src.llm.client import LLMCallResult
from visualization.src.run_figures import (
    TimedLLMResponse,
    call_prepared_llm_transition,
    display_llm_prompt,
    display_llm_response,
    display_llm_run_summary,
    finalize_llm_transition,
    llm_call_diagnostics,
    prepare_llm_transition,
)


class NotebookRunTests(FixtureModelsMixin, unittest.TestCase):
    def scenario_path(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        config = GeneratorConfig.model_validate(
            config_dict(str(Path(directory) / "scenario.json"))
        )
        generator = ScenarioGenerator(config)
        return generator.write(generator.generate())

    def test_response_display_explains_reasoning_only_length_limit(self):
        response = TimedLLMResponse(
            raw_response="",
            elapsed_seconds=12.0,
            usage={
                "completion_tokens": 4096,
                "completion_tokens_details": {"reasoning_tokens": 4096},
            },
            metadata={
                "backend": "litellm",
                "finish_reason": "length",
                "incomplete": True,
            },
        )

        rendered = display_llm_response(response).data

        self.assertIn("No visible model output", rendered)
        self.assertIn("consumed by reasoning tokens", rendered)
        self.assertIn("color:#1f2937", rendered)
        self.assertIn("completion tokens", rendered)
        self.assertNotIn("model response", rendered)
        self.assertNotIn("COMPLETE", rendered)

    def test_response_display_renders_configuration_and_metrics(self):
        response = TimedLLMResponse(
            raw_response='{"start":[-2,5],"axis":0,"sequence":["U","I","A"]}',
            elapsed_seconds=3.0,
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": 10},
            },
            metadata={
                "configured_model": "gpt-5-mini",
                "backend": "litellm",
                "reasoning_effort": "minimal",
                "provider_processing_ms": "2500",
            },
        )

        rendered = display_llm_response(response).data

        self.assertIn(">model<", rendered)
        self.assertIn(">backend<", rendered)
        self.assertIn(">reasoning<", rendered)
        self.assertIn(">LLM time<", rendered)
        self.assertIn("gpt-5-mini", rendered)
        self.assertIn("minimal", rendered)
        self.assertIn("prompt tokens", rendered)
        self.assertIn("reasoning tokens", rendered)
        self.assertIn("completion tokens", rendered)
        self.assertNotIn(">start<", rendered)
        first_row = rendered.split("<li", 1)[1].split("</li>", 1)[0]
        self.assertNotIn("border-top:1px", first_row)

    def test_llm_transition_phases_isolate_the_timed_client_call(self):
        with patch("visualization.src.run_figures.call_llm_detailed") as mocked_call:
            prepared = prepare_llm_transition(
                scenario_name=self.scenario_path(),
                transition_index=0,
                model_name="test_litellm",
                reasoning_effort="minimal",
            )
            mocked_call.assert_not_called()
            mocked_call.return_value = LLMCallResult(
                content=json.dumps(prepared.reference_move.to_json()),
                usage={
                    "prompt_tokens": 100,
                    "completion_tokens": 25,
                    "total_tokens": 125,
                    "completion_tokens_details": {
                        "reasoning_tokens": 10,
                        "text_tokens": 15,
                    },
                },
                metadata={
                    "model": "gpt-5-mini-2025-08-07",
                    "provider_processing_ms": "1200",
                },
            )

            response = call_prepared_llm_transition(prepared)

            mocked_call.assert_called_once_with(
                prepared.system_prompt,
                prepared.user_prompt,
                prepared.model_name,
                reasoning_effort="minimal",
            )
            self.assertGreaterEqual(response.elapsed_seconds, 0.0)
            self.assertEqual(
                llm_call_diagnostics(response)["reasoning_tokens"],
                10,
            )
            diagnostics = llm_call_diagnostics(response)
            self.assertEqual(diagnostics["configured_model"], "test_litellm")
            self.assertEqual(diagnostics["backend"], "litellm")
            self.assertEqual(
                diagnostics["reasoning_effort"],
                "minimal",
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                context = finalize_llm_transition(
                    prepared,
                    response,
                    output_dir=temp_dir,
                )

            mocked_call.assert_called_once()
            self.assertEqual(
                context.run_log["llm_elapsed_seconds"],
                response.elapsed_seconds,
            )
            self.assertEqual(context.run_log["llm_usage"], response.usage)
            self.assertEqual(
                context.run_log["model_config"]["reasoning_effort"],
                "minimal",
            )
            self.assertNotIn("backend", context.run_log["model_config"])
            displayed_summary = display_llm_run_summary(context).data
            self.assertIn("failure classes", displayed_summary)
            self.assertIn("grid-template-columns:minmax(0,1fr)", displayed_summary)
            self.assertIn("model response", displayed_summary)
            self.assertIn(">start<", displayed_summary)
            self.assertIn(">axis<", displayed_summary)
            self.assertIn(">sequence<", displayed_summary)
            self.assertIn(">rack<", displayed_summary)
            self.assertIn("#dcfce7", displayed_summary)
            self.assertIn("text-align:left", displayed_summary)
            self.assertIn("text-align:right", displayed_summary)
            self.assertIn("min-width:22px", displayed_summary)
            self.assertIn(">tokens<", displayed_summary)
            self.assertIn("prompt", displayed_summary)
            self.assertIn("reasoning", displayed_summary)
            self.assertIn("visible output", displayed_summary)
            self.assertIn("completion", displayed_summary)
            self.assertIn("total", displayed_summary)
            for value in ("100", "10", "15", "25", "125"):
                self.assertIn(value, displayed_summary)
            self.assertNotIn("<strong>none</strong>", displayed_summary)
            self.assertNotIn(">transition 0<", displayed_summary)
            displayed_prompt = display_llm_prompt(prepared).data
            self.assertIn("prompts/system.txt", displayed_prompt)
            self.assertIn("omitted from notebook display", displayed_prompt)
            self.assertNotIn(
                prepared.user_prompt.split("Existing sequences:\n", 1)[1].split(
                    "\n\nRack:\n", 1
                )[0],
                displayed_prompt,
            )

    def test_finalize_llm_transition_marks_length_completion_as_truncated(self):
        prepared = prepare_llm_transition(
            scenario_name=self.scenario_path(),
            transition_index=0,
            model_name="test_litellm",
            reasoning_effort="high",
        )
        response = TimedLLMResponse(
            raw_response="",
            elapsed_seconds=1.0,
            usage={
                "completion_tokens": 100,
                "completion_tokens_details": {"reasoning_tokens": 100},
            },
            metadata={"finish_reason": "length"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            context = finalize_llm_transition(
                prepared,
                response,
                output_dir=temp_dir,
            )

        evaluation = context.run_log["evaluation"]
        self.assertEqual(evaluation["failure_type"], "truncated")
        self.assertIsNone(evaluation["letter_score_total"])
        self.assertEqual(
            evaluation["message"],
            "Completion truncated before the answer (finish_reason=length).",
        )
