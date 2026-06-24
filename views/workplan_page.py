from __future__ import annotations

from typing import Any

import streamlit as st

from models import MemberProfile
from services.progress_service import member_progress_key
from services.workplan_service import (
    SessionWorkplanRepository,
    goal_summary,
    replace_weekly_goals,
    weekly_rows_with_percentage,
)


def _records(data: Any) -> list[dict[str, Any]]:
    """Normalize Streamlit's supported table return types to row dictionaries."""
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    return list(data)


def _navigate_to_prospects() -> None:
    st.session_state["main_navigation"] = "ผู้มุ่งหวัง"


def render_business_workplan(profile: MemberProfile | None) -> None:
    st.title("Workplan ธุรกิจ")
    st.markdown(
        "<p class='section-lead'>กำหนดเป้าหมาย แผนงาน กิจกรรมรายสัปดาห์ และติดตามความคืบหน้าทางธุรกิจ</p>",
        unsafe_allow_html=True,
    )
    if not profile or not profile.is_complete:
        st.warning("กรุณากรอกโปรไฟล์สมาชิกก่อนเริ่มใช้งาน Workplan ธุรกิจ")
        return

    repository = SessionWorkplanRepository(st.session_state)
    workplan = repository.get(profile)
    _render_dashboard(workplan)
    st.info("จัดการ เพิ่ม และติดตามรายชื่อทั้งหมดได้จากเมนูผู้มุ่งหวัง")
    st.button(
        "ไปจัดการผู้มุ่งหวัง",
        type="primary",
        on_click=_navigate_to_prospects,
        width="stretch",
    )
    tabs = st.tabs(("เป้าหมายสปอนเซอร์", "เป้าหมายคะแนนทีม", "เป้าหมายรายได้"))
    with tabs[0]:
        _render_weekly_goal(profile, repository, workplan, "sponsor", "เป้าหมายสปอนเซอร์", "คน")
    with tabs[1]:
        _render_weekly_goal(profile, repository, workplan, "team_points", "เป้าหมายคะแนนทีม", "คะแนน")
    with tabs[2]:
        _render_weekly_goal(profile, repository, workplan, "income", "เป้าหมายรายได้", "บาท")


def _render_dashboard(workplan: dict[str, Any]) -> None:
    sponsor = goal_summary(workplan["goals"]["sponsor"])
    points = goal_summary(workplan["goals"]["team_points"])
    income = goal_summary(workplan["goals"]["income"])
    cards = (
        ("สปอนเซอร์สำเร็จ", f"{sponsor['percentage']:.0f}%"),
        ("คะแนนทีมสำเร็จ", f"{points['percentage']:.0f}%"),
        ("รายได้สำเร็จ", f"{income['percentage']:.0f}%"),
    )
    columns = st.columns(3)
    for column, (label, value) in zip(columns, cards):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")

def _render_weekly_goal(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
    goal_key: str,
    title: str,
    unit: str,
) -> None:
    st.subheader(title)
    rows = weekly_rows_with_percentage(workplan["goals"][goal_key])
    summary = goal_summary(rows)
    first, second, third = st.columns(3)
    first.metric(f"เป้าหมายรวม ({unit})", f"{summary['target']:,.0f}")
    second.metric(f"ทำได้จริง ({unit})", f"{summary['actual']:,.0f}")
    third.metric("ความสำเร็จ", f"{summary['percentage']:.0f}%")
    st.progress(summary["percentage"] / 100, text=f"ความสำเร็จรวม {summary['percentage']:.0f}%")

    edited = st.data_editor(
        rows,
        key=f"workplan_goal_{member_progress_key(profile)}_{goal_key}",
        hide_index=True,
        width="stretch",
        column_config={
            "week": st.column_config.NumberColumn("สัปดาห์ที่", format="%d"),
            "target": st.column_config.NumberColumn(f"เป้าหมาย ({unit})", min_value=0, step=1),
            "actual": st.column_config.NumberColumn(f"ทำได้จริง ({unit})", min_value=0, step=1),
            "percentage": st.column_config.ProgressColumn("ความสำเร็จ (%)", min_value=0, max_value=100, format="%.0f%%"),
        },
        disabled=("week", "percentage"),
    )
    if st.button(f"บันทึก{title}", key=f"save_{goal_key}", type="primary", width="stretch"):
        updated = replace_weekly_goals(workplan, goal_key, _records(edited))
        repository.save(profile, updated)
        st.rerun()
