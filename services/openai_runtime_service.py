from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar


T = TypeVar("T")
HEALTH_KEY = "openai_health"
GLOBAL_OPENAI_STATE: dict[str, Any] = {}
TRANSIENT_ERRORS = {"timeout", "connection_error", "server_error", "rate_limit"}


class OpenAIRuntimeError(RuntimeError):
    def __init__(self, category: str, status_code: int | None = None) -> None:
        super().__init__(category)
        self.category = category
        self.status_code = status_code


class OpenAIRuntimeService:
    def __init__(
        self,
        state: Any,
        *,
        api_key_configured: bool = False,
        responses_model: str = "",
        embedding_model: str = "",
        max_retries: int = 2,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.state = state
        self.max_retries = max(0, int(max_retries))
        self.sleep = sleep
        health = dict(state.get(HEALTH_KEY, {}))
        health.update(
            {
                "api_key_configured": bool(api_key_configured),
                "responses_model": responses_model,
                "embedding_model": embedding_model,
            }
        )
        state[HEALTH_KEY] = health

    def call(self, operation: str, callback: Callable[[], T]) -> T:
        retry_count = 0
        while True:
            try:
                result = callback()
                self._record_success(operation, retry_count)
                return result
            except OpenAIRuntimeError:
                raise
            except Exception as error:
                category, status_code = classify_openai_error(error)
                if category in TRANSIENT_ERRORS and retry_count < self.max_retries:
                    retry_count += 1
                    self.sleep(_retry_delay(error, retry_count))
                    continue
                self._record_failure(operation, category, status_code, retry_count)
                raise OpenAIRuntimeError(category, status_code) from error

    def record_validation_failure(self, operation: str = "responses") -> OpenAIRuntimeError:
        self._record_failure(operation, "response_validation", None, 0)
        return OpenAIRuntimeError("response_validation")

    def health(self) -> dict[str, Any]:
        return dict(self.state.get(HEALTH_KEY, {}))

    def _record_success(self, operation: str, retry_count: int) -> None:
        health = self.health()
        health.update(
            {
                "last_operation": operation,
                "last_success_time": _now(),
                "last_error_type": "",
                "last_retry_count": retry_count,
                "last_status_code": None,
                "last_result": "success",
            }
        )
        self.state[HEALTH_KEY] = health

    def _record_failure(
        self,
        operation: str,
        category: str,
        status_code: int | None,
        retry_count: int,
    ) -> None:
        health = self.health()
        health.update(
            {
                "last_operation": operation,
                "last_failure_time": _now(),
                "last_error_type": category,
                "last_retry_count": retry_count,
                "last_status_code": status_code,
                "last_result": "failure",
            }
        )
        self.state[HEALTH_KEY] = health


def classify_openai_error(error: Exception) -> tuple[str, int | None]:
    status_code = _status_code(error)
    name = error.__class__.__name__.casefold()
    message = str(error).casefold()
    if status_code == 401 or "authentication" in name:
        return "authentication_error", status_code
    if status_code == 403 or "permission" in name:
        return "permission_error", status_code
    if status_code == 429:
        if any(term in message for term in ("quota", "billing", "credit", "insufficient_quota")):
            return "billing_or_quota", status_code
        return "rate_limit", status_code
    if status_code in {500, 502, 503, 504}:
        return "server_error", status_code
    if "timeout" in name or "timed out" in message:
        return "timeout", status_code
    if "connection" in name or any(term in message for term in ("connection", "network", "dns")):
        return "connection_error", status_code
    if status_code == 400 or any(term in message for term in ("invalid model", "model_not_found", "invalid request")):
        return "invalid_model_or_request", status_code
    return "unknown", status_code


def get_openai_health() -> dict[str, Any]:
    return dict(GLOBAL_OPENAI_STATE.get(HEALTH_KEY, {}))


def _status_code(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    if value is None:
        value = getattr(getattr(error, "response", None), "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _retry_delay(error: Exception, retry_count: int) -> float:
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        if retry_after is not None:
            return min(5.0, max(0.0, float(retry_after)))
    except (TypeError, ValueError):
        pass
    return 0.5 if retry_count == 1 else 1.5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
