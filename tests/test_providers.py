import unittest
from types import SimpleNamespace
from unittest.mock import patch
from support import FixtureModelsMixin
from openrouter import components
from pydantic import ValidationError
from src.formal.parsing import SubmittedMove
from src.llm.client import LLMCallResult, call_llm_detailed
from src.llm.env import ENV, Environment
from src.llm.openrouter_client import (
    _parse_response,
    _request_kwargs,
)


class ProviderTests(FixtureModelsMixin, unittest.TestCase):
    def test_model_profiles_share_global_request_defaults(self):
        configs = list(ENV.model_configs.values())

        self.assertEqual({config.temperature for config in configs}, {1.0})
        self.assertEqual(
            {config.max_completion_tokens for config in configs},
            {32384},
        )
        self.assertEqual(
            {config.timeout_seconds for config in configs},
            {3600.0},
        )

    def test_openrouter_model_profile_builds_explicit_native_request(self):
        with patch.dict(
            "os.environ",
            {
                "OPENROUTER_API_KEY": "test-openrouter-key",
                "OPENROUTER_API_BASE": "https://openrouter.example/api/v1",
            },
        ):
            config = Environment().get_model_config("test_openrouter")

        request = _request_kwargs(
            config,
            "system",
            "user",
            reasoning_effort="xhigh",
        )

        self.assertEqual(config.backend, "openrouter")
        self.assertEqual(config.model, "openrouter/openai/gpt-5.5")
        self.assertEqual(config.request_model, "openai/gpt-5.5")
        self.assertEqual(config.api_key, "test-openrouter-key")
        self.assertEqual(
            config.base_url,
            "https://openrouter.example/api/v1",
        )
        self.assertEqual(
            request["provider"],
            {
                "only": ["openai"],
                "allow_fallbacks": False,
                "require_parameters": True,
            },
        )
        self.assertEqual(
            request["reasoning"],
            {"effort": "xhigh"},
        )
        self.assertEqual(request["max_tokens"], 32384)
        self.assertNotIn("max_completion_tokens", request)
        self.assertNotIn("temperature", request)
        self.assertIsNone(request["retries"])
        self.assertEqual(
            request["response_format"]["json_schema"]["schema"],
            SubmittedMove.model_json_schema(),
        )

    def test_submitted_move_schema_avoids_unsupported_axis_minimum(self):
        schema = SubmittedMove.model_json_schema()
        axis_schema = schema["properties"]["axis"]
        self.assertNotIn("minimum", axis_schema)
        self.assertIn("non-negative", axis_schema["description"])
        self.assertEqual(
            schema["properties"]["sequence"]["minItems"],
            1,
        )

        with self.assertRaisesRegex(ValidationError, "non-negative"):
            SubmittedMove(start=(0, 0), axis=-1, sequence=("A",))

    def test_openrouter_model_profile_uses_default_endpoint(self):
        with patch.dict(
            "os.environ",
            {"OPENROUTER_API_KEY": "test-openrouter-key"},
            clear=True,
        ):
            config = Environment().get_model_config("test_openrouter")

        self.assertIsNone(config.base_url)

    def test_openrouter_response_preserves_provider_metadata(self):
        response = components.ChatResult.model_validate(
            {
                "id": "gen-123",
                "created": 0,
                "model": "openai/gpt-5.5-20260423",
                "object": "chat.completion",
                "system_fingerprint": None,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"start":[0,0],"axis":0,"sequence":["A","B","C"]}'
                            ),
                            "reasoning": "hidden reasoning summary",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "completion_tokens_details": {"reasoning_tokens": 15},
                    "cost": 0.001,
                },
            }
        )

        result = _parse_response(response)

        self.assertEqual(result.metadata["backend"], "openrouter-sdk")
        self.assertEqual(result.metadata["model"], "openai/gpt-5.5-20260423")
        self.assertEqual(
            result.usage["completion_tokens_details"]["reasoning_tokens"],
            15,
        )

    def test_openrouter_passes_native_reasoning_effort_without_mapping(self):
        config = ENV.get_model_config("test_openrouter")

        request = _request_kwargs(
            config,
            "system",
            "user",
            reasoning_effort="minimal",
        )

        self.assertEqual(request["reasoning"], {"effort": "minimal"})

    def test_client_dispatches_openrouter_profiles_without_litellm(self):
        expected = LLMCallResult(
            content='{"start":[0,0],"axis":0,"sequence":["A"]}',
            usage={},
            metadata={"backend": "openrouter-sdk"},
        )
        with (
            patch(
                "src.llm.client.call_openrouter_detailed",
                return_value=expected,
            ) as direct_call,
            patch("src.llm.client.completion") as litellm_call,
        ):
            result = call_llm_detailed(
                "system",
                "user",
                "test_openrouter",
                reasoning_effort="high",
            )

        self.assertIs(result, expected)
        direct_call.assert_called_once()
        litellm_call.assert_not_called()

    def test_litellm_client_requests_and_validates_structured_output(self):
        message = SimpleNamespace(
            content='{"start":[0,0],"axis":0,"sequence":["A","B","C"]}'
        )
        choice = SimpleNamespace(message=message, finish_reason="stop")
        response = SimpleNamespace(
            choices=[choice],
            _response_headers={},
            _hidden_params={},
            get=lambda key, default=None: {
                "id": "response-id",
                "model": "gpt-5-mini-2025-08-07",
                "usage": {},
            }.get(key, default),
        )

        with patch("src.llm.client.completion", return_value=response) as mocked:
            result = call_llm_detailed(
                "system",
                "user",
                "test_litellm",
                reasoning_effort="high",
            )

        kwargs = mocked.call_args.kwargs
        self.assertIs(kwargs["response_format"], SubmittedMove)
        self.assertEqual(kwargs["reasoning_effort"], "high")
        self.assertEqual(kwargs["max_retries"], 0)
        self.assertEqual(
            SubmittedMove.model_validate_json(result.content).sequence,
            ("A", "B", "C"),
        )
        self.assertEqual(result.metadata["backend"], "litellm")
