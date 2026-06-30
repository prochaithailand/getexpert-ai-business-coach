from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import MemberProfile
from services.progress_service import calculate_plan_progress, member_progress_key
from services.team_service import resolve_profile_team
from services.workplan_service import (
    goal_summary,
    normalize_contact,
    priority_contacts,
    prospect_summary,
)
from translations import translate


NO_WORKPLAN_MESSAGE = (
    "ตอนนี้ยังไม่มีข้อมูล Workplan ที่บันทึกไว้ในระบบ "
    "กรุณาเพิ่มข้อมูลในเมนู Workplan ธุรกิจก่อน"
)


def no_workplan_message(language: str | None = None) -> str:
    return translate("No Workplan Data Message", language)


@dataclass(frozen=True)
class MemberActivityContext:
    has_data: bool
    summary: str


def is_workplan_question(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    terms = (
        "workplan", "เวิร์คแพลน", "ข้อมูลเข้า", "ทำอะไรต่อ", "ผลงานของผม",
        "ผลงานของฉัน", "วิเคราะห์ผลงาน", "รายชื่อของผม", "รายชื่อของฉัน",
        "เป้าหมายสปอนเซอร์", "คะแนนทีม", "เป้าหมายรายได้ของผม",
        "เป้าหมายรายได้ของฉัน", "คะแนน pp", "ความคืบหน้า 30 วัน",
        "ควรติดตามใครก่อน", "วิเคราะห์ผู้มุ่งหวัง", "ผู้มุ่งหวังของผม",
        "ผู้มุ่งหวังของฉัน",
    )
    return any(term in normalized for term in terms)


def build_member_activity_context(
    state: Any,
    profile: MemberProfile | None,
    language: str | None = None,
) -> MemberActivityContext:
    empty_message = no_workplan_message(language)
    if not profile or not profile.is_complete:
        return MemberActivityContext(False, empty_message)

    member_key = member_progress_key(profile)
    workplan = state.get("workplan_by_member", {}).get(member_key)
    statuses = dict(state.get("plan_completion_by_member", {}).get(member_key, {}))
    progress = calculate_plan_progress(statuses)
    signature = (
        profile.name,
        profile.age,
        profile.occupation,
        profile.daily_available_time,
        profile.income_goal,
        profile.online_marketing_experience,
        profile.team_name,
        profile.team_id,
        profile.team_leader,
        profile.sponsor,
        profile.role,
    )
    has_action_plan = bool(
        state.get("action_plan")
        and state.get("action_plan_signature") in {signature, signature[:6]}
    )
    has_workplan_values = bool(
        workplan
        and (
            workplan.get("contacts")
            or any(
                float(row.get("target", 0) or 0) > 0 or float(row.get("actual", 0) or 0) > 0
                for rows in workplan.get("goals", {}).values()
                for row in rows
            )
        )
    )
    if not has_workplan_values and not has_action_plan and progress.completed_days == 0:
        return MemberActivityContext(False, empty_message)

    workplan = workplan or {"contacts": [], "goals": {}}
    contacts = [normalize_contact(contact) for contact in workplan.get("contacts", [])]
    counts = prospect_summary(contacts)
    contact_lines = [
        f"- {contact.get('name', 'ไม่ระบุชื่อ')} | ประเภท {contact.get('category', 'D')} | "
        f"สถานะ {contact.get('status', 'ยังไม่ติดต่อ')} | อาชีพ {contact.get('occupation', 'ไม่ระบุ')} | "
        f"จังหวัด {contact.get('province') or 'ไม่ระบุ'} | "
        f"ติดตามครั้งถัดไป {contact.get('next_follow_up') or 'ยังไม่กำหนด'} | "
        f"หมายเหตุ {contact.get('notes', '')[:160] or 'ไม่มี'}"
        for contact in contacts[:20]
    ] or ["- ยังไม่มีรายชื่อผู้มุ่งหวัง"]
    if len(contacts) > 20:
        contact_lines.append(f"- และอีก {len(contacts) - 20} ราย")
    priority_lines = []
    for index, contact in enumerate(priority_contacts(contacts)[:5], start=1):
        days_until = contact["days_until_follow_up"]
        if days_until is None:
            due_text = "ยังไม่กำหนดวันติดตาม"
        elif days_until < 0:
            due_text = f"เกินกำหนด {abs(days_until)} วัน"
        elif days_until == 0:
            due_text = "ครบกำหนดวันนี้"
        else:
            due_text = f"ครบกำหนดใน {days_until} วัน"
        priority_lines.append(
            f"- ลำดับ {index}: {contact['name']} | เกรด {contact['category']} | "
            f"สถานะ {contact['status']} | {due_text} | หมายเหตุ {contact['notes'][:160] or 'ไม่มี'}"
        )
    if not priority_lines:
        priority_lines.append("- ไม่มีผู้มุ่งหวังที่ต้องติดตามในขณะนี้")

    goal_lines = []
    for key, label, unit in (
        ("sponsor", "สปอนเซอร์", "คน"),
        ("team_points", "คะแนนทีม", "คะแนน"),
        ("income", "รายได้", "บาท"),
    ):
        rows = list(workplan.get("goals", {}).get(key, []))
        result = goal_summary(rows)
        goal_lines.append(
            f"- {label}: เป้าหมายรวม {result['target']:,.0f} {unit} | "
            f"ทำได้จริง {result['actual']:,.0f} {unit} | สำเร็จ {result['percentage']:.0f}%"
        )
        active = [
            f"สัปดาห์ {int(row.get('week', 0))}: {float(row.get('target', 0)):,.0f}/{float(row.get('actual', 0)):,.0f}"
            for row in rows
            if float(row.get("target", 0) or 0) > 0 or float(row.get("actual", 0) or 0) > 0
        ]
        if active:
            goal_lines.append(f"  รายสัปดาห์ (เป้าหมาย/จริง): {', '.join(active)}")

    managed_team = resolve_profile_team(state, profile)
    team_name = managed_team.name if managed_team else profile.team_name
    team_id = managed_team.team_id if managed_team else profile.team_id
    team_leader = managed_team.leader if managed_team else profile.team_leader

    return MemberActivityContext(
        True,
        "\n".join(
            [
                "ข้อมูล Workplan ปัจจุบันของสมาชิก:",
                f"ข้อมูลทีม: ชื่อทีม {team_name or 'ยังไม่ระบุ'} | รหัสทีม {team_id or 'ยังไม่ระบุ'} | หัวหน้าทีม {team_leader or 'ยังไม่ระบุ'} | ผู้แนะนำ {profile.sponsor or 'ยังไม่ระบุ'} | บทบาท {profile.role}",
                f"จำนวนผู้มุ่งหวังทั้งหมด {counts['total']} ราย | A {counts['A']} | B {counts['B']} | C {counts['C']} | D {counts['D']} | สมัครแล้ว {counts['signed_up']} | นัดหมายแล้ว {counts['appointments']}",
                "สรุปรายชื่อผู้มุ่งหวัง:", *contact_lines,
                "ลำดับแนะนำสำหรับติดตาม (พิจารณาจากเกรด สถานะ และวันที่ติดตาม):", *priority_lines,
                "สรุปเป้าหมายและผลงาน:", *goal_lines,
                "ความคืบหน้าแผนปฏิบัติการ 30 วัน:",
                f"- ทำสำเร็จ {progress.completed_days}/{progress.total_days} วัน | "
                f"คงเหลือ {progress.remaining_days} วัน | ความก้าวหน้า {progress.percentage:.0f}% | "
                f"คะแนน PP {progress.pp_score} | ระดับ {progress.status_level}",
                "กิจกรรมที่ทำสำเร็จ:", *_completed_action_lines(state, statuses, has_action_plan),
            ]
        ),
    )


def _completed_action_lines(
    state: Any,
    statuses: dict[str, bool],
    use_current_plan: bool,
) -> list[str]:
    completed_days = {int(day) for day, done in statuses.items() if done and str(day).isdigit()}
    lines = [
        f"- วันที่ {int(getattr(item, 'day', 0))}: {getattr(item, 'focus', 'ทำกิจกรรมตามแผนสำเร็จ')}"
        for item in ((state.get("action_plan") or []) if use_current_plan else [])
        if int(getattr(item, "day", 0)) in completed_days
    ]
    if not lines and completed_days:
        lines = [f"- วันที่ {day}: ทำกิจกรรมตามแผนสำเร็จ" for day in sorted(completed_days)]
    return lines[:15] or ["- ยังไม่มีกิจกรรมที่ทำสำเร็จ"]
