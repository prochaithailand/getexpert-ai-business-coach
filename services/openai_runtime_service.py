from __future__ import annotations

import time
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, TypeVar


T = TypeVar("T")
HEALTH_KEY = "openai_health"
GLOBAL_OPENAI_STATE: dict[str, Any] = {}
TRANSIENT_ERRORS = {"timeout", "connection_error", "server_error", "rate_limit"}


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str = ""
    source: str = "missing"
    responses_model: str = ""
    embedding_model: str = ""

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def masked_key(self) -> str:
        if not self.api_key:
            return "-"
        suffix = self.api_key[-4:] if len(self.api_key) >= 4 else "****"
        prefix = "sk-" if self.api_key.startswith("sk-") else "key-"
        return f"{prefix}...{suffix}"


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
                metadata = sanitize_openai_error_metadata(error)
                if category in TRANSIENT_ERRORS and retry_count < self.max_retries:
                    retry_count += 1
                    self.sleep(_retry_delay(error, retry_count))
                    continue
                self._record_failure(
                    operation,
                    category,
                    status_code,
                    retry_count,
                    metadata,
                )
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
                "last_error_code": "",
                "last_error_api_type": "",
                "last_error_message": "",
                "last_request_id": "",
            }
        )
        self.state[HEALTH_KEY] = health

    def _record_failure(
        self,
        operation: str,
        category: str,
        status_code: int | None,
        retry_count: int,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        health = self.health()
        safe_metadata = metadata or {}
        health.update(
            {
                "last_operation": operation,
                "last_failure_time": _now(),
                "last_error_type": category,
                "last_retry_count": retry_count,
                "last_status_code": status_code,
                "last_result": "failure",
                "last_error_code": safe_metadata.get("error_code", ""),
                "last_error_api_type": safe_metadata.get("error_type", ""),
                "last_error_message": safe_metadata.get("error_message", ""),
                "last_request_id": safe_metadata.get("request_id", ""),
            }
        )
        self.state[HEALTH_KEY] = health


def classify_openai_error(error: Exception) -> tuple[str, int | None]:
    status_code = _status_code(error)
    name = error.__class__.__name__.casefold()
    message = str(error).casefold()
    metadata = sanitize_openai_error_metadata(error)
    structured = " ".join(
        (
            metadata.get("error_code", ""),
            metadata.get("error_type", ""),
            metadata.get("error_message", ""),
        )
    ).casefold()
    if status_code == 401 or "authentication" in name:
        return "authentication_error", status_code
    if status_code == 403 or "permission" in name:
        return "permission_error", status_code
    if status_code == 429:
        if any(
            term in f"{message} {structured}"
            for term in ("quota", "billing", "credit", "insufficient_quota")
        ):
            return "billing_or_quota", status_code
        return "rate_limit", status_code
    if status_code in {500, 502, 503, 504}:
        return "server_error", status_code
    if "timeout" in name or "timed out" in message:
        return "timeout", status_code
    if "connection" in name or any(term in message for term in ("connection", "network", "dns")):
        return "connection_error", status_code
    if status_code == 400 or any(
        term in f"{message} {structured}"
        for term in ("invalid model", "model_not_found", "invalid request")
    ):
        return "invalid_model_or_request", status_code
    return "unknown", status_code


def sanitize_openai_error_metadata(error: Exception) -> dict[str, str]:
    body = getattr(error, "body", None)
    error_data: Mapping[str, Any] = {}
    if isinstance(body, Mapping):
        nested = body.get("error")
        error_data = nested if isinstance(nested, Mapping) else body

    code = _safe_text(
        error_data.get("code")
        or getattr(error, "code", "")
    )
    error_type = _safe_text(
        error_data.get("type")
        or getattr(error, "type", "")
    )
    message = _sanitize_error_message(
        error_data.get("message")
        or getattr(error, "message", "")
        or str(error)
    )
    request_id = _safe_text(getattr(error, "request_id", ""))
    if not request_id:
        headers = getattr(getattr(error, "response", None), "headers", {}) or {}
        if hasattr(headers, "get"):
            request_id = _safe_text(
                headers.get("x-request-id")
                or headers.get("request-id")
                or headers.get("openai-request-id")
            )
    return {
        "error_code": code,
        "error_type": error_type,
        "error_message": message,
        "request_id": request_id,
    }


def get_openai_health() -> dict[str, Any]:
    return dict(GLOBAL_OPENAI_STATE.get(HEALTH_KEY, {}))


def load_openai_config(
    streamlit_secrets: Any,
    environment: Mapping[str, str],
    *,
    default_responses_model: str = "",
    default_embedding_model: str = "",
) -> OpenAIConfig:
    environment_key = str(environment.get("OPENAI_API_KEY", "") or "").strip()
    secret_key = _safe_secret(streamlit_secrets, "OPENAI_API_KEY")
    if environment_key:
        api_key, source = environment_key, "environment"
    elif secret_key:
        api_key, source = secret_key, "streamlit_secrets"
    else:
        api_key, source = "", "missing"

    responses_model = (
        str(environment.get("OPENAI_MODEL", "") or "").strip()
        or _safe_secret(streamlit_secrets, "OPENAI_MODEL")
        or default_responses_model
    )
    embedding_model = (
        str(environment.get("OPENAI_EMBEDDING_MODEL", "") or "").strip()
        or _safe_secret(streamlit_secrets, "OPENAI_EMBEDDING_MODEL")
        or default_embedding_model
    )
    return OpenAIConfig(api_key, source, responses_model, embedding_model)


def get_openai_diagnostic_health(config: OpenAIConfig) -> dict[str, Any]:
    health = get_openai_health()
    health.update(
        {
            "api_key_configured": config.api_key_configured,
            "config_source": config.source,
            "masked_key": config.masked_key,
            "responses_model": config.responses_model,
            "embedding_model": config.embedding_model,
        }
    )
    return health


def build_answer_metadata(
    answer_source: str,
    *,
    health: Mapping[str, Any] | None = None,
    error_category: str = "",
    model: str = "",
) -> dict[str, Any]:
    operational = health or {}
    return {
        "answer_source": answer_source,
        "error_category": error_category,
        "retry_count": int(operational.get("last_retry_count", 0) or 0),
        "timestamp": _now(),
        "model": model if answer_source == "openai" else "",
    }


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


def _safe_secret(secrets: Any, name: str) -> str:
    try:
        value = secrets.get(name, "")
    except Exception:
        try:
            value = secrets[name]
        except Exception:
            return ""
    return str(value or "").strip()


def _safe_text(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _sanitize_error_message(value: Any) -> str:
    text = _safe_text(value, limit=300)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED_KEY]", text)
    text = re.sub(
        r"(?i)\b(?:api[_ -]?key|authorization|bearer)\s*[:=]\s*\S+",
        "[REDACTED_CREDENTIAL]",
        text,
    )
    text = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
        text,
    )
    return text[:240]
