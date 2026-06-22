from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SupabaseConfig:
    url: str = ""
    anon_key: str = ""
    source: str = "None"

    @property
    def is_complete(self) -> bool:
        return bool(self.url and self.anon_key)

    @property
    def safe_debug_message(self) -> str:
        url_status = "FOUND" if self.url else "NOT FOUND"
        key_status = "FOUND" if self.anon_key else "NOT FOUND"
        return (
            f"SUPABASE_URL: {url_status} | "
            f"SUPABASE_ANON_KEY: {key_status} | "
            f"Config source: {self.source}"
        )


def load_supabase_config(
    streamlit_secrets: Any,
    environment: Mapping[str, str],
) -> SupabaseConfig:
    secret_url = _safe_secret(streamlit_secrets, "SUPABASE_URL")
    secret_key = _safe_secret(streamlit_secrets, "SUPABASE_ANON_KEY")
    if secret_url and secret_key:
        return SupabaseConfig(secret_url, secret_key, "Streamlit Secrets")

    environment_url = str(environment.get("SUPABASE_URL", "") or "").strip()
    environment_key = str(environment.get("SUPABASE_ANON_KEY", "") or "").strip()
    if environment_url and environment_key:
        return SupabaseConfig(environment_url, environment_key, "Environment Variables")

    return SupabaseConfig(
        secret_url or environment_url,
        secret_key or environment_key,
        "None",
    )


def _safe_secret(secrets: Any, name: str) -> str:
    try:
        value = secrets.get(name, "")
    except Exception:
        try:
            value = secrets[name]
        except Exception:
            return ""
    return str(value or "").strip()
