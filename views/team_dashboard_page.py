from __future__ import annotations

from copy import deepcopy
from html import escape
from typing import Any

import streamlit as st

from models import AppUser, MemberProfile
from services.coach_service import CoachService
from services.permissions import UNAUTHORIZED_MESSAGE, can_access_team_dashboard
from services.team_dashboard_service import (
    EMPTY_TEAM_MESSAGE,
    build_team_dashboard,
    rule_based_team_insight,
    rule_based_team_coach_answer,
    team_dashboard_context,
    team_dashboard_signature,
)
from services.team_service import SessionTeamRepository
from services.supabase_service import get_authenticated_supabase_user, get_supabase_service, run_supabase_sync


def render_team_dashboard(
    profile: MemberProfile | None,
    coach: CoachService,
    authenticated_user: AppUser | None = None,
) -> None:
    st.title("Team Dashboard")
    if not can_access_team_dashboard(authenticated_user or profile):
        st.warning(UNAUTHORIZED_MESSAGE)
        return
    st.markdown(
        "<p class='section-lead'>ภาพรวมผลงานสมาชิกจากระบบจัดการทีม ผู้มุ่งหวัง แผนธุรกิจ และแผนปฏิบัติการ 30 วัน</p>",
        unsafe_allow_html=True,
    )
    selected_team_id = _select_team(profile, authenticated_user)
    snapshot = build_team_dashboard(st.session_state, profile, selected_team_id)
    if snapshot is None:
        st.info(EMPTY_TEAM_MESSAGE)
        return
    _render_summary(snapshot)
    _render_member_table(snapshot)
    _render_pipeline(snapshot)
    _render_progress_distribution(snapshot)
    _render_rankings(snapshot)
    _render_team_insights(coach, snapshot)


def _select_team(
    profile: MemberProfile | None,
    authenticated_user: AppUser | None,
) -> str | None:
    if not authenticated_user or authenticated_user.role != "Admin":
        return profile.team_id if profile else None
    teams = SessionTeamRepository(st.session_state).list()
    if not teams:
        return None
    labels = {f"{team.name} ({team.team_id})": team.team_id for team in teams}
    selected = st.selectbox("เลือกทีม", tuple(labels), key="admin_team_dashboard_team")
    return labels[selected]


def _render_summary(snapshot: dict[str, Any]) -> None:
    grades = snapshot["grades"]
    st.subheader("สรุปภาพรวมทีม")
    _card_row((
        ("ชื่อทีม", escape(snapshot["team_name"] or "ยังไม่ระบุ")),
        ("รหัสทีม", escape(snapshot["team_id"])),
        ("หัวหน้าทีม", escape(snapshot["team_leader"] or "ยังไม่ระบุ")),
    ))
    _card_row((
        ("จำนวนสมาชิกทั้งหมด", f"{snapshot['total_members']} คน"),
        ("สมาชิกที่ใช้งานอยู่", f"{snapshot['active_members']} คน"),
        ("คะแนน PP รวม", f"{snapshot['total_pp']} PP"),
        ("ค่าเฉลี่ยความคืบหน้าแผน 30 วัน", f"{snapshot['average_completion']:.1f}%"),
    ))
    _card_row((("จำนวนผู้มุ่งหวังทั้งหมด", f"{snapshot['total_prospects']} ราย"),))
    _card_row(tuple((f"ผู้มุ่งหวังเกรด {grade}", f"{grades[grade]} ราย") for grade in ("A", "B", "C", "D")))
    _card_row((("นัดหมายแล้ว", f"{snapshot['appointments']} ราย"), ("สมัครแล้ว", f"{snapshot['signed_up']} ราย")))


def _card_row(cards: tuple[tuple[str, str], ...]) -> None:
    columns = st.columns(len(cards))
    for column, (label, value) in zip(columns, cards):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")


def _render_member_table(snapshot: dict[str, Any]) -> None:
    st.subheader("ตารางสมาชิกทีม")
    rows = [
        {
            "ชื่อสมาชิก": member["name"],
            "บทบาท": {"Member": "สมาชิก", "Leader": "ผู้นำ", "Admin": "ผู้ดูแลระบบ"}.get(member["role"], member["role"]),
            "คะแนน PP": member["pp"],
            "จำนวนผู้มุ่งหวัง": member["prospects"],
        }
        for member in snapshot["members"]
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def _render_pipeline(snapshot: dict[str, Any]) -> None:
    st.subheader("สรุป Prospect Pipeline")
    pipeline = snapshot["pipeline"]
    _card_row(tuple((label, f"{pipeline[label]} ราย") for label in (
        "ยังไม่ติดต่อ", "ติดต่อแล้ว", "นัดหมาย", "นำเสนอ", "สมัครสมาชิก",
    )))


def _render_progress_distribution(snapshot: dict[str, Any]) -> None:
    st.subheader("ความคืบหน้าแผน 30 วันของทีม")
    progress = snapshot["progress_distribution"]
    _card_row((
        ("Completed 100%", f"{progress['completed_100']} คน"),
        ("Above 80%", f"{progress['above_80']} คน"),
        ("Above 50%", f"{progress['above_50']} คน"),
        ("Below 50%", f"{progress['below_50']} คน"),
    ))


def _render_rankings(snapshot: dict[str, Any]) -> None:
    st.subheader("อันดับผลงานทีม")
    rankings = (
        ("อันดับตามคะแนน PP", "pp", "PP", lambda value: f"{value:.0f}"),
        ("อันดับตามจำนวนผู้มุ่งหวัง", "prospects", "ราย", lambda value: f"{value:.0f}"),
        ("อันดับตามความคืบหน้าแผน 30 วัน", "progress", "%", lambda value: f"{value:.1f}"),
    )
    for column, (title, key, unit, formatter) in zip(st.columns(3), rankings):
        with column:
            st.markdown(f"**{title}**")
            ranked = sorted(snapshot["members"], key=lambda member: (-member[key], member["name"]))[:5]
            for rank, member in enumerate(ranked, start=1):
                st.markdown(f"{rank}. {escape(member['name'])} - {formatter(member[key])} {unit}")


def _render_team_insights(coach: CoachService, snapshot: dict[str, Any]) -> None:
    st.subheader("โค้ช AI สำหรับทีม")
    st.caption("วิเคราะห์ผลงานเด่น สมาชิกที่ต้องการการสนับสนุน และงานสำคัญประจำสัปดาห์")
    signature = team_dashboard_signature(snapshot)
    store = deepcopy(st.session_state.get("team_insights_by_team", {}))
    saved = store.get(snapshot["team_id"], {})
    insight = saved.get("insight") if saved.get("signature") == signature else None
    refresh = st.button("อัปเดตข้อมูลเชิงลึกของทีม", width="stretch")
    if insight is None or refresh:
        with st.spinner("กำลังวิเคราะห์ผลงานของทีม..."):
            insight = (
                coach.generate_team_insight(team_dashboard_context(snapshot))
                if getattr(coach, "is_api_enabled", False)
                else rule_based_team_insight(snapshot)
            )
        store[snapshot["team_id"]] = {"signature": signature, "insight": insight}
        st.session_state.team_insights_by_team = store
    st.markdown(insight)
    if getattr(coach, "is_api_enabled", False):
        st.caption("วิเคราะห์โดย GetExpert AI Business Coach จากข้อมูลทีมล่าสุด")
    else:
        st.caption("วิเคราะห์ด้วยกฎพื้นฐาน เนื่องจากยังไม่ได้ตั้งค่า OPENAI_API_KEY")

    st.markdown("**ถามโค้ชเกี่ยวกับผลงานทีม**")
    st.caption("ตัวอย่าง: ทีมของผมควรทำอะไรวันนี้, สมาชิกคนใดต้องการความช่วยเหลือ, ใครมีโอกาสปิดการสมัครสูง")
    history_store = deepcopy(st.session_state.get("team_coach_messages_by_team", {}))
    history = list(history_store.get(snapshot["team_id"], []))
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        "ถามคำถามเกี่ยวกับทีมของคุณ",
        key=f"team_coach_input_{snapshot['team_id']}",
    )
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.spinner("โค้ช AI กำลังวิเคราะห์ข้อมูลทีม..."):
            answer = (
                coach.answer_team_question(prompt, team_dashboard_context(snapshot), history)
                if getattr(coach, "is_api_enabled", False)
                else rule_based_team_coach_answer(snapshot, prompt)
            )
        with st.chat_message("assistant"):
            st.markdown(answer)
        history.extend((
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ))
        history_store[snapshot["team_id"]] = history[-20:]
        st.session_state.team_coach_messages_by_team = history_store
        supabase = get_supabase_service(st.session_state)
        authenticated = get_authenticated_supabase_user(st.session_state)
        if supabase and authenticated:
            run_supabase_sync(
                st.session_state, supabase.save_chat_message, authenticated, "user", prompt,
                chat_type="team", team_id=snapshot["team_id"],
            )
            run_supabase_sync(
                st.session_state, supabase.save_chat_message, authenticated, "assistant", answer,
                chat_type="team", team_id=snapshot["team_id"],
            )
