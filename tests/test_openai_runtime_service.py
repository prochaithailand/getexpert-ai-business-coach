import unittest
from types import SimpleNamespace

from services.openai_runtime_service import (
    OpenAIRuntimeError,
    OpenAIRuntimeService,
    build_answer_metadata,
    classify_openai_error,
    get_openai_diagnostic_health,
    load_openai_config,
)


class StatusError(Exception):
    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(status_code=status_code, headers={})


class OpenAIRuntimeServiceTests(unittest.TestCase):
    def test_timeout_retries_then_succeeds(self) -> None:
        state = {}
        attempts = 0
        runtime = OpenAIRuntimeService(state, max_retries=2, sleep=lambda _: None)

        def callback():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise TimeoutError("timed out")
            return "ok"

        self.assertEqual(runtime.call("responses", callback), "ok")
        self.assertEqual(attempts, 3)
        self.assertEqual(runtime.health()["last_retry_count"], 2)
        self.assertEqual(runtime.health()["last_result"], "success")

    def test_connection_and_server_errors_retry(self) -> None:
        for error in (ConnectionError("network"), StatusError(503)):
            with self.subTest(error=error):
                attempts = 0
                runtime = OpenAIRuntimeService({}, max_retries=2, sleep=lambda _: None)

                def callback():
                    nonlocal attempts
                    attempts += 1
                    raise error

                with self.assertRaises(OpenAIRuntimeError):
                    runtime.call("responses", callback)
                self.assertEqual(attempts, 3)

    def test_authentication_and_invalid_model_do_not_retry(self) -> None:
        for error, category in (
            (StatusError(401), "authentication_error"),
            (StatusError(400, "invalid model"), "invalid_model_or_request"),
        ):
            attempts = 0
            runtime = OpenAIRuntimeService({}, max_retries=2, sleep=lambda _: None)

            def callback():
                nonlocal attempts
                attempts += 1
                raise error

            with self.assertRaises(OpenAIRuntimeError) as caught:
                runtime.call("responses", callback)
            self.assertEqual(attempts, 1)
            self.assertEqual(caught.exception.category, category)

    def test_rate_limit_retries_but_hard_quota_does_not(self) -> None:
        self.assertEqual(classify_openai_error(StatusError(429))[0], "rate_limit")
        self.assertEqual(
            classify_openai_error(StatusError(429, "insufficient_quota"))[0],
            "billing_or_quota",
        )

    def test_health_contains_only_operational_metadata(self) -> None:
        state = {}
        runtime = OpenAIRuntimeService(
            state,
            api_key_configured=True,
            responses_model="gpt-test",
            embedding_model="embedding-test",
        )
        runtime.call("embeddings", lambda: "ok")
        health = runtime.health()

        self.assertTrue(health["api_key_configured"])
        self.assertEqual(health["last_operation"], "embeddings")
        self.assertNotIn("api_key", health)
        self.assertNotIn("prompt", health)
        self.assertNotIn("response", health)

    def test_diagnostic_uses_live_streamlit_secret_config(self) -> None:
        config = load_openai_config(
            {"OPENAI_API_KEY": "sk-secret-1234", "OPENAI_MODEL": "gpt-live"},
            {},
            default_embedding_model="embedding-default",
        )
        health = get_openai_diagnostic_health(config)

        self.assertTrue(health["api_key_configured"])
        self.assertEqual(health["config_source"], "streamlit_secrets")
        self.assertEqual(health["masked_key"], "sk-...1234")
        self.assertEqual(health["responses_model"], "gpt-live")
        self.assertNotIn("sk-secret-1234", str(health))

    def test_diagnostic_reports_missing_key_without_exposing_values(self) -> None:
        config = load_openai_config(
            {},
            {},
            default_responses_model="gpt-default",
            default_embedding_model="embedding-default",
        )
        health = get_openai_diagnostic_health(config)

        self.assertFalse(health["api_key_configured"])
        self.assertEqual(health["config_source"], "missing")
        self.assertEqual(health["masked_key"], "-")

    def test_answer_metadata_contains_no_prompt_response_or_key(self) -> None:
        metadata = build_answer_metadata(
            "openai",
            health={"last_retry_count": 1},
            model="gpt-test",
        )

        self.assertEqual(metadata["answer_source"], "openai")
        self.assertEqual(metadata["retry_count"], 1)
        self.assertNotIn("prompt", metadata)
        self.assertNotIn("response", metadata)
        self.assertNotIn("api_key", metadata)


if __name__ == "__main__":
    unittest.main()
