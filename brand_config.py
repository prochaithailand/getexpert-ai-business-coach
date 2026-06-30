from __future__ import annotations

from collections.abc import Mapping
from typing import Any


BRANDS: dict[str, dict[str, str]] = {
    "getexpert": {
        "app_name": "GetExpert AI Business Coach",
        "short_name": "GetExpert",
        "powered_by": "",
        "logo_path": "assets/getexpert_logo.png",
        "primary_color": "#0F172A",
        "mark": "GE",
        "subtitle": "AI Member Success System",
        "hero_title": "GetExpert โค้ชธุรกิจ AI",
        "system_identity": (
            "คุณคือ GetExpert AI Business Coach ผู้ช่วยพัฒนานักธุรกิจเครือข่ายยุคดิจิทัล "
            "ตอบเป็นภาษาไทย ชัดเจน ใช้งานได้จริง และอ้างอิงจากคลังความรู้ของระบบ"
        ),
    },
    "tglife": {
        "app_name": "TG Life AI Business Coach",
        "short_name": "TG Life",
        "powered_by": "powered by GetExpert",
        "logo_path": "assets/tglife_logo.png",
        "primary_color": "#0F172A",
        "mark": "TG",
        "subtitle": "AI Business Coach for TG Life Members",
        "hero_title": "TG Life AI Business Coach",
        "system_identity": (
            "You are TG Life AI Business Coach powered by GetExpert. "
            "Answer in the same language as the user. "
            "If the user asks in Burmese/Myanmar language, answer in Burmese/Myanmar language. "
            "If the user asks in Thai, answer in Thai. "
            "If the user asks in English, answer in English. "
            "Your role is to help TG Life members learn, build teams, follow up prospects, "
            "and develop business skills."
        ),
    },
}


def _setting(source: Mapping[str, Any] | None, name: str) -> str:
    if not source:
        return ""
    try:
        value = source.get(name, "")
    except Exception:
        return ""
    return str(value or "").strip()


def resolve_brand_key(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    environ = environ or {}
    raw = (
        _setting(secrets, "APP_BRAND")
        or _setting(secrets, "GETEXPERT_BRAND")
        or str(environ.get("APP_BRAND", "") or environ.get("GETEXPERT_BRAND", "")).strip()
        or "getexpert"
    )
    key = raw.lower().replace("-", "_")
    return key if key in BRANDS else "getexpert"


def get_brand(
    secrets: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    key = resolve_brand_key(secrets, environ)
    return {"key": key, **BRANDS[key]}

