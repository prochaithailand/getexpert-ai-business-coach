from __future__ import annotations

from typing import Any

from models import MemberProfile
from services.progress_service import calculate_plan_progress, member_progress_key


def build_onboarding_status(
    state: Any,
    profile: MemberProfile | None,
) -> dict[str, bool]:
    """สรุปขั้นตอนเริ่มต้นจากข้อมูลสมาชิกที่โหลดอยู่ใน session ปัจจุบัน"""
    profile_complete = bool(profile and profile.is_complete)
    member_key = member_progress_key(profile) if profile_complete and profile else ""
    workplan = dict(state.get("workplan_by_member", {}).get(member_key, {}))
    goals = dict(workplan.get("goals", {}))
    statuses = dict(state.get("plan_completion_by_member", {}).get(member_key, {}))
    progress = calculate_plan_progress(statuses)

    has_workplan = bool(workplan.get("contacts")) or any(
        float(row.get("target", 0) or 0) > 0
        or float(row.get("actual", 0) or 0) > 0
        for rows in goals.values()
        for row in rows
    )
    has_ai_usage = any(
        message.get("role") == "user"
        for message in state.get("coach_messages", [])
    )
    if member_key:
        usage = dict(state.get("member_usage_by_member", {}).get(member_key, {}))
        has_ai_usage = has_ai_usage or int(usage.get("ai_coach", 0)) > 0

    dashboard = dict(state.get("dashboard_by_member", {}).get(member_key, {}))
    saved_completed = int(dashboard.get("plan", {}).get("completed", 0) or 0)
    saved_pp = int(dashboard.get("plan", {}).get("pp_score", 0) or 0)
    persisted_pp = int(state.get("pp_scores_by_member", {}).get(member_key, 0) or 0)
    saved_goals = dict(dashboard.get("goals", {}))
    has_dashboard_progress = (
        progress.completed_days > 0 or saved_completed > 0 or saved_pp > 0 or persisted_pp > 0
    ) or any(
        float(summary.get("actual", 0) or 0) > 0
        for summary in saved_goals.values()
    ) or any(
        float(row.get("actual", 0) or 0) > 0
        for rows in goals.values()
        for row in rows
    )

    return {
        "profile": profile_complete,
        "action_plan": bool(state.get("action_plan")),
        "workplan": has_workplan,
        "ai_coach": has_ai_usage,
        "dashboard": has_dashboard_progress,
    }
