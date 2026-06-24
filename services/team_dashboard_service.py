from __future__ import annotations

from copy import deepcopy
from typing import Any

from models import MemberProfile
from services.profile_repository import SessionProfileRepository
from services.progress_service import calculate_plan_progress, member_progress_key
from services.team_service import SessionTeamRepository
from services.workplan_service import goal_summary, normalize_contact, prospect_summary


EMPTY_TEAM_MESSAGE = "ยังไม่มีข้อมูลทีม กรุณาเลือกทีมในโปรไฟล์สมาชิกหรือสร้างทีมในเมนูจัดการทีมก่อน"
TEAM_DASHBOARD_KEY = "team_dashboard_by_team"


def build_team_dashboard(
    state: Any,
    current_profile: MemberProfile | None,
    team_id: str | None = None,
) -> dict[str, Any] | None:
    selected_team_id = (team_id or (current_profile.team_id if current_profile else "")).strip().upper()
    if current_profile and current_profile.role == "Leader":
        leader_team_id = current_profile.team_id.strip().upper()
        if not leader_team_id or selected_team_id != leader_team_id:
            return None
    if not selected_team_id:
        return None
    team = SessionTeamRepository(state).get(selected_team_id)
    profiles = SessionProfileRepository(state).list_by_team(selected_team_id)
    if (
        current_profile
        and current_profile.team_id.strip().upper() == selected_team_id
        and all(profile.name != current_profile.name for profile in profiles)
    ):
        profiles.append(current_profile)
    if not profiles:
        return None

    members = [
        _member_snapshot(state, profile, _profile_email(state, profile))
        for profile in profiles
    ]
    total_pp = sum(member["pp"] for member in members)
    total_prospects = sum(member["prospects"] for member in members)
    grades = {
        grade: sum(member[grade] for member in members)
        for grade in ("A", "B", "C", "D")
    }
    pipeline = {
        "ยังไม่ติดต่อ": sum(member["pipeline"]["ยังไม่ติดต่อ"] for member in members),
        "ติดต่อแล้ว": sum(member["pipeline"]["ติดต่อแล้ว"] for member in members),
        "นัดหมาย": sum(member["pipeline"]["นัดหมาย"] for member in members),
        "นำเสนอ": sum(member["pipeline"]["นำเสนอ"] for member in members),
        "สมัครสมาชิก": sum(member["pipeline"]["สมัครสมาชิก"] for member in members),
    }
    progress_distribution = {
        "completed_100": sum(member["progress"] >= 100 for member in members),
        "above_80": sum(80 <= member["progress"] < 100 for member in members),
        "above_50": sum(50 <= member["progress"] < 80 for member in members),
        "below_50": sum(member["progress"] < 50 for member in members),
    }
    snapshot = {
        "team_id": selected_team_id,
        "team_name": team.name if team else (current_profile.team_name if current_profile else ""),
        "team_leader": team.leader if team else (current_profile.team_leader if current_profile else ""),
        "team_leader_email": team.leader_email if team else "",
        "total_members": len(members),
        "active_members": sum(1 for member in members if member["active"]),
        "total_pp": total_pp,
        "average_completion": round(sum(member["progress"] for member in members) / len(members), 1),
        "total_prospects": total_prospects,
        "appointments": sum(member["appointments"] for member in members),
        "signed_up": sum(member["signed_up"] for member in members),
        "grades": grades,
        "pipeline": pipeline,
        "progress_distribution": progress_distribution,
        "members": members,
    }
    store = deepcopy(state.get(TEAM_DASHBOARD_KEY, {}))
    store[selected_team_id] = snapshot
    state[TEAM_DASHBOARD_KEY] = store
    return snapshot


def _profile_email(state: Any, profile: MemberProfile) -> str:
    profile_key = member_progress_key(profile)
    for email, raw in state.get("member_profiles_by_user", {}).items():
        candidate = raw if isinstance(raw, MemberProfile) else MemberProfile.from_dict(raw)
        if member_progress_key(candidate) == profile_key:
            return str(email).casefold()
    return ""


def _member_snapshot(
    state: Any,
    profile: MemberProfile,
    email: str = "",
) -> dict[str, Any]:
    key = member_progress_key(profile)
    progress = calculate_plan_progress(
        dict(state.get("plan_completion_by_member", {}).get(key, {}))
    )
    workplan = state.get("workplan_by_member", {}).get(key, {})
    statuses = dict(state.get("plan_completion_by_member", {}).get(key, {}))
    contacts = [normalize_contact(contact) for contact in workplan.get("contacts", [])]
    counts = prospect_summary(contacts)
    pipeline = {
        "ยังไม่ติดต่อ": sum(contact["status"] == "ยังไม่ติดต่อ" for contact in contacts),
        "ติดต่อแล้ว": sum(contact["status"] == "ติดต่อแล้ว" for contact in contacts),
        "นัดหมาย": sum(contact["status"] == "นัดหมายแล้ว" for contact in contacts),
        "นำเสนอ": sum(contact["status"] == "นำเสนอแล้ว" for contact in contacts),
        "สมัครสมาชิก": sum(contact["status"] == "สมัครแล้ว" for contact in contacts),
    }
    goals = {
        goal_key: goal_summary(list(workplan.get("goals", {}).get(goal_key, [])))
        for goal_key in ("sponsor", "team_points", "income")
    }
    actual_goals = sum(result["actual"] for result in goals.values())
    usage = state.get("member_usage_by_member", {}).get(key, {})
    active = bool(
        progress.completed_days
        or counts["total"]
        or actual_goals
        or int(usage.get("content_creator", 0))
        or int(usage.get("ai_coach", 0))
    )
    completed_days = sorted(
        int(day) for day, done in statuses.items() if done and str(day).isdigit()
    )
    if completed_days:
        latest_activity = f"ทำแผนปฏิบัติการวันที่ {completed_days[-1]} สำเร็จ"
    elif int(workplan.get("editor_version", 0)) > 0:
        latest_activity = f"อัปเดตรายชื่อผู้มุ่งหวัง {counts['total']} ราย"
    elif actual_goals:
        latest_activity = "บันทึกผล Workplan"
    elif int(usage.get("content_creator", 0)) or int(usage.get("ai_coach", 0)):
        latest_activity = "ใช้งานเครื่องมือพัฒนาธุรกิจ"
    else:
        latest_activity = "ยังไม่มีกิจกรรม"
    closing_statuses = {"นัดหมายแล้ว", "นำเสนอแล้ว", "กำลังตัดสินใจ"}
    closing_opportunities = sorted([
        {
            "name": contact["name"],
            "grade": contact["category"],
            "status": contact["status"],
            "next_follow_up": contact["next_follow_up"],
            "notes": contact["notes"][:120],
        }
        for contact in contacts
        if contact["status"] in closing_statuses
    ], key=lambda item: (
        {"A": 0, "B": 1, "C": 2, "D": 3}.get(item["grade"], 4),
        {"กำลังตัดสินใจ": 0, "นำเสนอแล้ว": 1, "นัดหมายแล้ว": 2}.get(item["status"], 3),
        item["next_follow_up"] or "9999-12-31",
    ))
    return {
        "member_key": key,
        "email": email,
        "name": profile.name,
        "role": profile.role,
        "pp": int(state.get("pp_scores_by_member", {}).get(key, progress.pp_score)),
        "progress": progress.percentage,
        "prospects": counts["total"],
        "A": counts["A"],
        "B": counts["B"],
        "C": counts["C"],
        "D": counts["D"],
        "appointments": counts["appointments"],
        "signed_up": counts["signed_up"],
        "pipeline": pipeline,
        "status": progress.status_level,
        "latest_activity": latest_activity,
        "goals": goals,
        "closing_opportunities": closing_opportunities,
        "active": active,
    }


def team_dashboard_context(snapshot: dict[str, Any]) -> str:
    grades = snapshot["grades"]
    member_lines = "\n".join(
        f"- {member['name']} | บทบาท {member['role']} | PP {member['pp']} | "
        f"แผน 30 วัน {member['progress']:.0f}% | ผู้มุ่งหวัง {member['prospects']} | "
        f"เกรด A {member['A']} | นัดหมาย {member['appointments']} | สมัคร {member['signed_up']} | "
        f"สถานะ {member['status']} | กิจกรรมล่าสุด {member['latest_activity']} | "
        f"Workplan สปอนเซอร์ {member['goals']['sponsor']['actual']:.0f}/{member['goals']['sponsor']['target']:.0f} | "
        f"คะแนนทีม {member['goals']['team_points']['actual']:.0f}/{member['goals']['team_points']['target']:.0f} | "
        f"รายได้ {member['goals']['income']['actual']:.0f}/{member['goals']['income']['target']:.0f}"
        for member in snapshot["members"]
    )
    opportunity_lines = [
        f"- เจ้าของรายชื่อ {member['name']}: {prospect['name']} | เกรด {prospect['grade']} | "
        f"สถานะ {prospect['status']} | ติดตาม {prospect['next_follow_up'] or 'ยังไม่กำหนด'} | "
        f"หมายเหตุ {prospect['notes'] or 'ไม่มี'}"
        for member in snapshot["members"]
        for prospect in member["closing_opportunities"]
    ]
    return (
        f"ทีม: {snapshot['team_name']} | รหัสทีม {snapshot['team_id']} | หัวหน้าทีม {snapshot['team_leader']}\n"
        f"สมาชิกทั้งหมด {snapshot['total_members']} | สมาชิกที่ใช้งานอยู่ {snapshot['active_members']} | "
        f"PP รวม {snapshot['total_pp']} | ความคืบหน้าเฉลี่ย {snapshot['average_completion']:.1f}%\n"
        f"ผู้มุ่งหวังทั้งหมด {snapshot['total_prospects']} | A {grades['A']} | B {grades['B']} | "
        f"C {grades['C']} | D {grades['D']} | นัดหมายแล้ว {snapshot['appointments']} | "
        f"สมัครแล้ว {snapshot['signed_up']}\nรายสมาชิก:\n{member_lines}\n"
        f"ผู้มุ่งหวังที่มีโอกาสปิดการสมัคร:\n{chr(10).join(opportunity_lines) if opportunity_lines else '- ยังไม่มีข้อมูลเพียงพอ'}"
    )


def team_dashboard_signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
    return (
        snapshot["team_id"],
        snapshot["team_name"],
        snapshot["team_leader"],
        *(
            value
            for member in snapshot["members"]
            for value in (
                member["member_key"], member["role"], member["pp"], member["progress"],
                member["prospects"], member["A"], member["appointments"], member["signed_up"],
                member["status"], member["latest_activity"], member["active"],
            )
        ),
    )


def rule_based_team_insight(snapshot: dict[str, Any]) -> str:
    members = snapshot["members"]
    best = max(members, key=lambda item: (item["pp"], item["prospects"], item["progress"]))
    support = min(members, key=lambda item: (item["progress"], item["pp"], item["prospects"]))
    return (
        "**สมาชิกที่ทำผลงานดีที่สุด**\n"
        f"- {best['name']} มี {best['pp']} PP ความคืบหน้า {best['progress']:.0f}% "
        f"และผู้มุ่งหวัง {best['prospects']} ราย\n\n"
        "**สมาชิกที่ต้องการความช่วยเหลือ**\n"
        f"- {support['name']} ควรได้รับการติดตามใกล้ชิด โดยเริ่มจากภารกิจรายวันและการเพิ่มรายชื่อคุณภาพ\n\n"
        "**ความคืบหน้าของทีม**\n"
        f"- ทีมมีสมาชิกที่ใช้งานอยู่ {snapshot['active_members']} จาก {snapshot['total_members']} คน "
        f"PP รวม {snapshot['total_pp']} และความคืบหน้าเฉลี่ย {snapshot['average_completion']:.1f}%\n\n"
        "**งานที่ควรโฟกัสในสัปดาห์นี้**\n"
        "- ช่วยสมาชิกที่ความคืบหน้าต่ำกำหนดภารกิจอย่างน้อยวันละ 1 งาน\n"
        "- เพิ่มรายชื่อเกรด A/B และกำหนดวันติดตามให้ครบทุกคน\n"
        "- ทบทวน PP และความคืบหน้าแผน 30 วันร่วมกันเมื่อสิ้นสัปดาห์"
    )


def rule_based_team_coach_answer(snapshot: dict[str, Any], question: str) -> str:
    members = snapshot["members"]
    normalized = " ".join(question.casefold().split())
    if any(term in normalized for term in ("ช่วยเหลือ", "โค้ชเพิ่มเติม", "ต้องการการโค้ช")):
        member = min(members, key=lambda item: (item["progress"], item["pp"], item["prospects"]))
        return (
            "**คำตอบจากโค้ชทีม**\n"
            f"- {member['name']} ควรได้รับการโค้ชเพิ่มเติม เนื่องจากมี {member['pp']} PP "
            f"และความคืบหน้าแผน 30 วัน {member['progress']:.1f}%\n"
            "- เริ่มด้วยการกำหนดงานรายวัน 1 งาน เพิ่มรายชื่อใหม่ และนัดทบทวนผลภายใน 3 วัน"
        )
    if any(term in normalized for term in ("ปิดการสมัคร", "สมัครสูง", "มีโอกาส")):
        opportunities = [
            (member["name"], prospect)
            for member in members
            for prospect in member["closing_opportunities"]
        ]
        if not opportunities:
            return "ขณะนี้ข้อมูล CRM ยังไม่มีผู้มุ่งหวังในสถานะนัดหมาย นำเสนอ หรือกำลังตัดสินใจเพียงพอสำหรับจัดอันดับโอกาสปิดการสมัคร"
        lines = [
            f"- {prospect['name']} ของ {owner}: เกรด {prospect['grade']} สถานะ {prospect['status']}"
            for owner, prospect in opportunities[:5]
        ]
        return "**ผู้มุ่งหวังที่ควรติดตามก่อน**\n" + "\n".join(lines) + "\n- ติดตามตามวันนัดและใช้ข้อมูลจากหมายเหตุเพื่อเตรียมบทสนทนา"
    best = max(members, key=lambda item: (item["pp"], item["prospects"], item["progress"]))
    return (
        "**สิ่งที่ทีมควรทำวันนี้**\n"
        f"- รักษาแรงส่งจาก {best['name']} ซึ่งมี {best['pp']} PP และผู้มุ่งหวัง {best['prospects']} ราย\n"
        "- ให้สมาชิกทุกคนทำภารกิจแผน 30 วันอย่างน้อย 1 งาน\n"
        "- เพิ่มรายชื่อเกรด A/B และติดตามผู้ที่อยู่ในสถานะนัดหมาย นำเสนอ หรือกำลังตัดสินใจ\n"
        f"- ปัจจุบันทีมมี PP รวม {snapshot['total_pp']} และความคืบหน้าเฉลี่ย {snapshot['average_completion']:.1f}%"
    )
