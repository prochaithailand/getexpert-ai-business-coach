from __future__ import annotations

from copy import deepcopy
from typing import Any

from models import MemberProfile
from services.progress_service import calculate_plan_progress, member_progress_key
from services.team_service import resolve_profile_team
from services.workplan_service import goal_summary, normalize_contact, prospect_summary


EMPTY_DASHBOARD_MESSAGE = "ยังไม่มีข้อมูลเพียงพอ กรุณากรอกโปรไฟล์และ Workplan ก่อน"
USAGE_KEY = "member_usage_by_member"
DASHBOARD_KEY = "dashboard_by_member"


def record_member_usage(state: Any, profile: MemberProfile | None, feature: str) -> None:
    if not profile or not profile.is_complete or feature not in {"content_creator", "ai_coach"}:
        return
    member_key = member_progress_key(profile)
    store = deepcopy(state.get(USAGE_KEY, {}))
    usage = dict(store.get(member_key, {}))
    usage[feature] = int(usage.get(feature, 0)) + 1
    store[member_key] = usage
    state[USAGE_KEY] = store


def build_and_save_dashboard(state: Any, profile: MemberProfile | None) -> dict[str, Any] | None:
    if not profile or not profile.is_complete:
        return None
    member_key = member_progress_key(profile)
    workplan = state.get("workplan_by_member", {}).get(member_key)
    if not _has_workplan_data(workplan):
        return None

    contacts = [normalize_contact(contact) for contact in workplan.get("contacts", [])]
    counts = prospect_summary(contacts)
    goals = workplan.get("goals", {})
    progress = calculate_plan_progress(
        dict(state.get("plan_completion_by_member", {}).get(member_key, {}))
    )
    usage = dict(state.get(USAGE_KEY, {}).get(member_key, {}))
    managed_team = resolve_profile_team(state, profile)
    snapshot = {
        "member_key": member_key,
        "name": profile.name,
        "income_goal": float(profile.income_goal),
        "team": {
            "name": managed_team.name if managed_team else profile.team_name,
            "id": managed_team.team_id if managed_team else profile.team_id,
            "leader": managed_team.leader if managed_team else profile.team_leader,
            "sponsor": profile.sponsor,
            "role": profile.role,
        },
        "plan": {
            "completed": progress.completed_days,
            "total": progress.total_days,
            "percentage": progress.percentage,
            "pp_score": progress.pp_score,
            "status": progress.status_level,
        },
        "contacts": counts,
        "goals": {
            "sponsor": goal_summary(list(goals.get("sponsor", []))),
            "team_points": goal_summary(list(goals.get("team_points", []))),
            "income": goal_summary(list(goals.get("income", []))),
        },
        "usage": {
            "content_creator": int(usage.get("content_creator", 0)),
            "ai_coach": int(usage.get("ai_coach", 0)),
        },
    }
    store = deepcopy(state.get(DASHBOARD_KEY, {}))
    store[member_key] = snapshot
    state[DASHBOARD_KEY] = store
    return snapshot


def dashboard_context(snapshot: dict[str, Any]) -> str:
    plan = snapshot["plan"]
    contacts = snapshot["contacts"]
    sponsor = snapshot["goals"]["sponsor"]
    points = snapshot["goals"]["team_points"]
    income = snapshot["goals"]["income"]
    usage = snapshot["usage"]
    team = snapshot["team"]
    return (
        f"สมาชิก: {snapshot['name']}\n"
        f"ทีม: {team['name'] or 'ยังไม่ระบุ'} | รหัสทีม {team['id'] or 'ยังไม่ระบุ'} | "
        f"หัวหน้าทีม {team['leader'] or 'ยังไม่ระบุ'} | ผู้แนะนำ {team['sponsor'] or 'ยังไม่ระบุ'} | "
        f"บทบาท {team['role']}\n"
        f"เป้าหมายรายได้ต่อเดือน: {snapshot['income_goal']:,.0f} บาท\n"
        f"แผน 30 วัน: สำเร็จ {plan['completed']}/{plan['total']} วัน "
        f"({plan['percentage']:.0f}%) | คะแนน PP {plan['pp_score']} | ระดับ {plan['status']}\n"
        f"รายชื่อ: ทั้งหมด {contacts['total']} | A {contacts['A']} | B {contacts['B']} | "
        f"C {contacts['C']} | D {contacts['D']} | สมัครแล้ว {contacts['signed_up']} | "
        f"นัดหมายแล้ว {contacts['appointments']}\n"
        f"สปอนเซอร์: เป้าหมาย {sponsor['target']:,.0f} ทำได้ {sponsor['actual']:,.0f} "
        f"({sponsor['percentage']:.0f}%)\n"
        f"คะแนนทีม: เป้าหมาย {points['target']:,.0f} ทำได้ {points['actual']:,.0f} "
        f"({points['percentage']:.0f}%)\n"
        f"รายได้ Workplan: เป้าหมาย {income['target']:,.0f} บาท ทำได้ {income['actual']:,.0f} บาท "
        f"({income['percentage']:.0f}%)\n"
        f"การใช้งาน: สร้างคอนเทนต์ {usage['content_creator']} ครั้ง | "
        f"ถามโค้ช AI {usage['ai_coach']} ครั้ง"
    )


def dashboard_signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    return (
        snapshot["name"],
        snapshot["income_goal"],
        snapshot["team"]["name"],
        snapshot["team"]["id"],
        snapshot["team"]["leader"],
        snapshot["team"]["sponsor"],
        snapshot["team"]["role"],
        snapshot["plan"]["completed"],
        snapshot["contacts"]["total"],
        *(snapshot["contacts"][category] for category in ("A", "B", "C", "D")),
        snapshot["contacts"]["signed_up"],
        snapshot["contacts"]["appointments"],
        *(snapshot["goals"][key]["target"] for key in ("sponsor", "team_points", "income")),
        *(snapshot["goals"][key]["actual"] for key in ("sponsor", "team_points", "income")),
        snapshot["usage"]["content_creator"],
        snapshot["usage"]["ai_coach"],
    )


def _has_workplan_data(workplan: dict[str, Any] | None) -> bool:
    if not workplan:
        return False
    if workplan.get("contacts"):
        return True
    return any(
        float(row.get("target", 0) or 0) > 0 or float(row.get("actual", 0) or 0) > 0
        for rows in workplan.get("goals", {}).values()
        for row in rows
    )
