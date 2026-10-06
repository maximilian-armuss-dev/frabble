from __future__ import annotations

import json
import asyncio
import tempfile
import unittest
from functools import partial
from pathlib import Path
from unittest.mock import patch

import httpx

from src.evaluation.config import RunConfig
from src.evaluation.job_execution import model_config_snapshot
from src.evaluation.jobs import build_evaluation_jobs
from src.llm.env import ENV, Environment
from src.llm.openrouter_client import (
    _AsyncBudgetClient, _BudgetClient, _request_kwargs,
    acall_openrouter_detailed, call_openrouter_detailed,
)


class ReasoningConfigTests(unittest.TestCase):
    def load_profiles(self, *, defaults=None, overrides=None):
        payload = {
            "defaults": {
                "temperature": 1, "timeout_seconds": 3600,
                "max_completion_tokens": 100000,
                "reasoning_max_tokens": 99000,
                "reasoning_effort": "high",
                **(defaults or {}),
            },
            "models": [
                {"name": name, "model": "openrouter/test/model",
                 "api_key_env": "FRABBLE_TEST_UNUSED_KEY", "provider": "test",
                 **(overrides or {}).get(name, {})}
                for name in ("inherited", "custom")
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "models.yaml"
            path.write_text(json.dumps(payload))
            with patch("src.llm.env.MODEL_CONFIGS_PATH", path):
                return Environment().model_configs

    def jobs(self, profiles):
        config = RunConfig(config_name="test", case_set="test",
                           models={name: ["all"] for name in profiles})
        with patch.object(ENV, "model_configs", profiles):
            return build_evaluation_jobs(config, {
                "cases": {"case": {"board_size": 20, "path": "unused.json"}}
            })

    def test_default_budgets_reach_serialized_request_and_snapshot(self):
        profiles = self.load_profiles()
        for job in self.jobs(profiles):
            with patch.object(ENV, "model_configs", profiles):
                snapshot = model_config_snapshot(job)
            for body in self.capture_requests(profiles[job.model_name], job.reasoning_effort):
                self.assertEqual(body["max_tokens"], 100000)
                self.assertEqual(body["reasoning"], {"max_tokens": 99000})
                self.assertEqual(snapshot["request_max_tokens"], body["max_tokens"])
                self.assertEqual(snapshot["reasoning"], body["reasoning"])
                self.assertEqual(snapshot["reasoning_max_tokens"], 99000)

    def capture_requests(self, config, effort):
        bodies = []

        def respond(request):
            bodies.append(json.loads(request.content))
            self.assertEqual(int(request.headers["content-length"]), len(request.content))
            return httpx.Response(200, json={
                "id": "test", "created": 0, "model": "test/model",
                "object": "chat.completion", "system_fingerprint": None,
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant",
                    "content": '{"start":[0,0],"axis":0,"sequence":["A"]}',
                }}],
            })

        transport = httpx.MockTransport(respond)
        with patch("src.llm.openrouter_client._BudgetClient",
                   partial(_BudgetClient, transport=transport)):
            call_openrouter_detailed(config, "system", "user", reasoning_effort=effort)
        with patch("src.llm.openrouter_client._AsyncBudgetClient",
                   partial(_AsyncBudgetClient, transport=transport)):
            asyncio.run(acall_openrouter_detailed(
                config, "system", "user", reasoning_effort=effort))
        self.assertEqual(len(bodies), 2)
        return bodies

    def test_per_model_budgets_override_defaults(self):
        profiles = self.load_profiles(overrides={"custom": {
            "max_completion_tokens": 30000, "reasoning_max_tokens": 24000,
        }})
        request = _request_kwargs(profiles["custom"], "system", "user",
                                  reasoning_effort="low")
        self.assertEqual(request["max_tokens"], 30000)
        self.assertEqual(request["reasoning"], {"max_tokens": 24000})
        self.assertEqual(profiles["inherited"].reasoning_max_tokens, 99000)

    def test_null_budget_enables_model_effort_for_batch_and_single_calls(self):
        profiles = self.load_profiles(overrides={"custom": {
            "reasoning_max_tokens": None, "reasoning_effort": "medium",
        }})
        job = next(job for job in self.jobs(profiles) if job.model_name == "custom")
        self.assertEqual(job.reasoning_effort, "medium")
        self.assertIn("__medium__", job.job_id)
        for effort in (None, job.reasoning_effort, "low"):
            request = _request_kwargs(profiles["custom"], "system", "user",
                                      reasoning_effort=effort)
            self.assertEqual(request["reasoning"], {"effort": effort or "medium"})
        with patch.object(ENV, "model_configs", profiles):
            self.assertEqual(model_config_snapshot(job)["reasoning"], {"effort": "medium"})
        for body in self.capture_requests(profiles["custom"], None):
            self.assertEqual(body["reasoning"], {"effort": "medium"})

    def test_global_effort(self):
        profiles = self.load_profiles(defaults={
            "reasoning_max_tokens": None, "reasoning_effort": "low",
        })
        self.assertEqual({job.reasoning_effort for job in self.jobs(profiles)}, {"low"})

    def test_invalid_reasoning_settings_are_rejected(self):
        for defaults in ({"reasoning_effort": "typo"}, {"reasoning_max_tokens": 0}):
            with self.subTest(defaults=defaults), self.assertRaises(RuntimeError):
                self.load_profiles(defaults=defaults)


if __name__ == "__main__":
    unittest.main()
