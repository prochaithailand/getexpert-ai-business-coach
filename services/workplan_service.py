from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from models import MemberProfile
from services.progress_service import member_progress_key
from services.supabase_service import get_authenticated_supabase_user, get_supabase_service, run_supabase_sync


CONTACT_TYPES = ("A", "B", "C", "D")
CONTACT_STATUSES = (
    "ยังไม่ติดต่อ",
    "ติดต่อแล้ว",
    "ส่งข้อมูลแล้ว",
    "นัดหมายแล้ว",
    "นำเสนอแล้ว",
    "กำลังตัดสินใจ",
    "สมัครแล้ว",
    "ไม่สนใจ",
)
LEGACY_STATUS_MAP = {
    "ติดตามผล": "กำลังตัดสินใจ",
    "สมัครสมาชิก": "สมัครแล้ว",
}
WEEK_COUNT = 12


def create_default_workplan() -> dict[str, Any]:
    return {
        "contacts": [],
        "goals": {
            "sponsor": _default_weekly_rows(),
            "team_points": _default_weekly_rows(),
            "income": _default_weekly_rows(),
        },
        "editor_version": 0,
    }


def _default_weekly_rows() -> list[dict[str, float | int]]:
    return [
        {"week": week, "target": 0.0, "actual": 0.0}
        for week in range(1, WEEK_COUNT + 1)
    ]


class SessionWorkplanRepository:
    KEY = "workplan_by_member"

    def __init__(self, state: Any) -> None:
        self.state = state

    def get(self, profile: MemberProfile) -> dict[str, Any]:
        member_key = member_progress_key(profile)
        store = dict(self.state.get(self.KEY, {}))
        if member_key not in store:
            store[member_key] = create_default_workplan()
            self.state[self.KEY] = store
        workplan = deepcopy(store[member_key])
        normalized_contacts = [normalize_contact(contact) for contact in workplan.get("contacts", [])]
        if normalized_contacts != workplan.get("contacts", []):
            workplan["contacts"] = normalized_contacts
            store[member_key] = deepcopy(workplan)
            self.state[self.KEY] = store
        return workplan

    def save(self, profile: MemberProfile, workplan: dict[str, Any]) -> None:
        store = dict(self.state.get(self.KEY, {}))
        store[member_progress_key(profile)] = deepcopy(workplan)
        self.state[self.KEY] = store
        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if supabase and authenticated:
            run_supabase_sync(self.state, supabase.save_workplan, authenticated, workplan)


def add_contact(workplan: dict[str, Any], contact: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(workplan)
    normalized = normalize_contact(contact)
    normalized["id"] = str(contact.get("id") or uuid4().hex)
    updated["contacts"].append(normalized)
    updated["editor_version"] = int(updated.get("editor_version", 0)) + 1
    return updated


def replace_contacts(workplan: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    updated = deepcopy(workplan)
    updated["contacts"] = [
        normalize_contact(contact)
        for contact in contacts
        if not bool(contact.get("delete", False)) and str(contact.get("name", "")).strip()
    ]
    updated["editor_version"] = int(updated.get("editor_version", 0)) + 1
    return updated


def update_contact(
    workplan: dict[str, Any],
    contact_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(workplan)
    for index, contact in enumerate(updated["contacts"]):
        if str(contact.get("id")) != str(contact_id):
            continue
        merged = {**contact, **changes, "id": str(contact_id)}
        updated["contacts"][index] = normalize_contact(merged)
        updated["editor_version"] = int(updated.get("editor_version", 0)) + 1
        return updated
    raise KeyError("ไม่พบผู้มุ่งหวังที่ต้องการแก้ไข")


def delete_contact(workplan: dict[str, Any], contact_id: str) -> dict[str, Any]:
    updated = deepcopy(workplan)
    remaining = [
        contact
        for contact in updated["contacts"]
        if str(contact.get("id")) != str(contact_id)
    ]
    if len(remaining) == len(updated["contacts"]):
        raise KeyError("ไม่พบผู้มุ่งหวังที่ต้องการลบ")
    updated["contacts"] = remaining
    updated["editor_version"] = int(updated.get("editor_version", 0)) + 1
    return updated


def update_contact_status(
    workplan: dict[str, Any],
    contact_id: str,
    status: str,
) -> dict[str, Any]:
    if status not in CONTACT_STATUSES:
        raise ValueError("สถานะผู้มุ่งหวังไม่ถูกต้อง")
    return update_contact(workplan, contact_id, {"status": status})


def normalize_contact(contact: dict[str, Any]) -> dict[str, Any]:
    category = str(contact.get("category", "D")).upper()
    status = LEGACY_STATUS_MAP.get(
        str(contact.get("status", CONTACT_STATUSES[0])),
        str(contact.get("status", CONTACT_STATUSES[0])),
    )
    return {
        "id": str(contact.get("id") or uuid4().hex),
        "name": str(contact.get("name", "")).strip(),
        "age": max(0, int(contact.get("age", 0) or 0)),
        "occupation": str(contact.get("occupation", "")).strip(),
        "status": status if status in CONTACT_STATUSES else CONTACT_STATUSES[0],
        "income": max(0.0, float(contact.get("income", 0) or 0)),
        "phone": str(contact.get("phone", "")).strip(),
        "category": category if category in CONTACT_TYPES else "D",
        "province": str(contact.get("province", "")).strip(),
        "notes": str(contact.get("notes", "")).strip(),
        "next_follow_up": _normalize_date(contact.get("next_follow_up")),
    }


def _normalize_date(value: Any) -> str:
    if value in {None, ""}:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return ""


def contact_counts(contacts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {category: 0 for category in CONTACT_TYPES}
    for contact in contacts:
        category = str(contact.get("category", "D")).upper()
        if category in counts:
            counts[category] += 1
    return {"total": len(contacts), **counts}


def prospect_summary(contacts: list[dict[str, Any]]) -> dict[str, int]:
    counts = contact_counts(contacts)
    return {
        **counts,
        "signed_up": sum(1 for contact in contacts if contact.get("status") == "สมัครแล้ว"),
        "appointments": sum(1 for contact in contacts if contact.get("status") == "นัดหมายแล้ว"),
    }


def priority_contacts(
    contacts: list[dict[str, Any]],
    today: date | None = None,
) -> list[dict[str, Any]]:
    reference_date = today or date.today()
    grade_score = {"A": 40, "B": 30, "C": 20, "D": 10}
    status_score = {
        "กำลังตัดสินใจ": 22,
        "นัดหมายแล้ว": 20,
        "นำเสนอแล้ว": 18,
        "ส่งข้อมูลแล้ว": 14,
        "ติดต่อแล้ว": 12,
        "ยังไม่ติดต่อ": 10,
        "สมัครแล้ว": -100,
        "ไม่สนใจ": -100,
    }
    prioritized = []
    for contact in contacts:
        normalized = normalize_contact(contact)
        if normalized["status"] in {"สมัครแล้ว", "ไม่สนใจ"}:
            continue
        follow_up = normalized["next_follow_up"]
        due_score = 5
        days_until = None
        if follow_up:
            days_until = (date.fromisoformat(follow_up) - reference_date).days
            if days_until < 0:
                due_score = 30
            elif days_until == 0:
                due_score = 28
            elif days_until <= 3:
                due_score = 22
            elif days_until <= 7:
                due_score = 15
            else:
                due_score = 0
        normalized["priority_score"] = (
            grade_score[normalized["category"]]
            + status_score.get(normalized["status"], 0)
            + due_score
        )
        normalized["days_until_follow_up"] = days_until
        prioritized.append(normalized)
    return sorted(
        prioritized,
        key=lambda item: (-item["priority_score"], item["next_follow_up"] or "9999-12-31", item["name"]),
    )


def replace_weekly_goals(
    workplan: dict[str, Any],
    goal_key: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if goal_key not in {"sponsor", "team_points", "income"}:
        raise ValueError("ประเภทเป้าหมายไม่ถูกต้อง")
    updated = deepcopy(workplan)
    by_week = {int(row.get("week", 0)): row for row in rows}
    updated["goals"][goal_key] = [
        {
            "week": week,
            "target": max(0.0, float(by_week.get(week, {}).get("target", 0) or 0)),
            "actual": max(0.0, float(by_week.get(week, {}).get("actual", 0) or 0)),
        }
        for week in range(1, WEEK_COUNT + 1)
    ]
    return updated


def completion_percentage(target: float, actual: float) -> float:
    if target <= 0:
        return 0.0
    return min(100.0, max(0.0, actual / target * 100))


def weekly_rows_with_percentage(rows: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    return [
        {
            "week": int(row.get("week", 0)),
            "target": float(row.get("target", 0)),
            "actual": float(row.get("actual", 0)),
            "percentage": completion_percentage(
                float(row.get("target", 0)),
                float(row.get("actual", 0)),
            ),
        }
        for row in rows
    ]


def goal_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    target = sum(float(row.get("target", 0)) for row in rows)
    actual = sum(float(row.get("actual", 0)) for row in rows)
    return {
        "target": target,
        "actual": actual,
        "percentage": completion_percentage(target, actual),
    }
