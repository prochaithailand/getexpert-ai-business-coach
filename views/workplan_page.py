from __future__ import annotations

from typing import Any
from datetime import date

import streamlit as st

from models import MemberProfile
from services.progress_service import member_progress_key
from services.workplan_service import (
    CONTACT_STATUSES,
    CONTACT_TYPES,
    SessionWorkplanRepository,
    add_contact,
    contact_counts,
    goal_summary,
    replace_contacts,
    replace_weekly_goals,
    weekly_rows_with_percentage,
)


def _records(data: Any) -> list[dict[str, Any]]:
    """Normalize Streamlit's supported table return types to row dictionaries."""
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    return list(data)


def render_business_workplan(profile: MemberProfile | None) -> None:
    st.title("Workplan ธุรกิจ")
    st.markdown(
        "<p class='section-lead'>ติดตามบัญชีรายชื่อและเป้าหมายรายสัปดาห์ตามแนวทาง Workplan ธุรกิจเครือข่าย</p>",
        unsafe_allow_html=True,
    )
    if not profile or not profile.is_complete:
        st.warning("กรุณากรอกโปรไฟล์สมาชิกก่อนเริ่มใช้งาน Workplan ธุรกิจ")
        return

    repository = SessionWorkplanRepository(st.session_state)
    workplan = repository.get(profile)
    _render_dashboard(workplan)
    tabs = st.tabs(("บัญชีรายชื่อ", "เป้าหมายสปอนเซอร์", "เป้าหมายคะแนนทีม", "เป้าหมายรายได้"))
    with tabs[0]:
        _render_contacts(profile, repository, workplan)
    with tabs[1]:
        _render_weekly_goal(profile, repository, workplan, "sponsor", "เป้าหมายสปอนเซอร์", "คน")
    with tabs[2]:
        _render_weekly_goal(profile, repository, workplan, "team_points", "เป้าหมายคะแนนทีม", "คะแนน")
    with tabs[3]:
        _render_weekly_goal(profile, repository, workplan, "income", "เป้าหมายรายได้", "บาท")


def _render_dashboard(workplan: dict[str, Any]) -> None:
    contacts = contact_counts(workplan["contacts"])
    sponsor = goal_summary(workplan["goals"]["sponsor"])
    points = goal_summary(workplan["goals"]["team_points"])
    income = goal_summary(workplan["goals"]["income"])
    cards = (
        ("รายชื่อทั้งหมด", f"{contacts['total']} คน"),
        ("สปอนเซอร์สำเร็จ", f"{sponsor['percentage']:.0f}%"),
        ("คะแนนทีมสำเร็จ", f"{points['percentage']:.0f}%"),
        ("รายได้สำเร็จ", f"{income['percentage']:.0f}%"),
    )
    columns = st.columns(4)
    for column, (label, value) in zip(columns, cards):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")


def _render_contacts(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    st.subheader("เพิ่มรายชื่อผู้มุ่งหวัง")
    with st.form("workplan_add_contact", clear_on_submit=True):
        first, second, third = st.columns(3)
        name = first.text_input("ชื่อ", placeholder="ชื่อ-นามสกุล")
        age = second.number_input("อายุ", min_value=0, max_value=120, value=30)
        occupation = third.text_input("อาชีพ", placeholder="ตัวอย่าง: พนักงานบริษัท")
        status = first.selectbox("สถานะ", CONTACT_STATUSES)
        income = second.number_input("รายได้ต่อเดือน (บาท)", min_value=0.0, step=1000.0)
        phone = third.text_input("เบอร์โทร", placeholder="0xx-xxx-xxxx")
        category = first.selectbox("ประเภท A/B/C/D", CONTACT_TYPES)
        province = second.text_input("จังหวัด", placeholder="ตัวอย่าง: กรุงเทพมหานคร")
        submitted = st.form_submit_button("เพิ่มรายชื่อ", type="primary", width="stretch")
    if submitted:
        if not name.strip():
            st.warning("กรุณาระบุชื่อก่อนเพิ่มรายชื่อ")
        else:
            updated = add_contact(
                workplan,
                {
                    "name": name,
                    "age": age,
                    "occupation": occupation,
                    "status": status,
                    "income": income,
                    "phone": phone,
                    "category": category,
                    "province": province,
                },
            )
            repository.save(profile, updated)
            st.rerun()

    st.caption("ประเภท A: สนใจธุรกิจ | B: สนใจรายได้เสริม | C: สนใจสุขภาพ | D: ยังไม่แน่ใจ")
    counts = contact_counts(workplan["contacts"])
    count_columns = st.columns(5)
    count_cards = (
        ("รายชื่อทั้งหมด", counts["total"]),
        ("รายชื่อ A", counts["A"]),
        ("รายชื่อ B", counts["B"]),
        ("รายชื่อ C", counts["C"]),
        ("รายชื่อ D", counts["D"]),
    )
    for column, (label, value) in zip(count_columns, count_cards):
        column.metric(label, value)

    if not workplan["contacts"]:
        st.info("ยังไม่มีรายชื่อ กรอกแบบฟอร์มด้านบนเพื่อเริ่มต้น")
        return

    editor_rows = [
        {
            "id": contact["id"],
            "name": contact["name"],
            "age": contact["age"],
            "occupation": contact["occupation"],
            "status": contact["status"],
            "income": contact["income"],
            "phone": contact["phone"],
            "category": contact["category"],
            "province": contact.get("province", ""),
            "notes": contact.get("notes", ""),
            "next_follow_up": _date_value(contact.get("next_follow_up", "")),
            "delete": False,
        }
        for contact in workplan["contacts"]
    ]
    edited = st.data_editor(
        editor_rows,
        key=f"workplan_contacts_{member_progress_key(profile)}_{workplan.get('editor_version', 0)}",
        hide_index=True,
        width="stretch",
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("ชื่อ", required=True),
            "age": st.column_config.NumberColumn("อายุ", min_value=0, max_value=120, step=1),
            "occupation": st.column_config.TextColumn("อาชีพ"),
            "status": st.column_config.SelectboxColumn("สถานะ", options=CONTACT_STATUSES),
            "income": st.column_config.NumberColumn("รายได้", min_value=0, format="%.0f บาท"),
            "phone": st.column_config.TextColumn("เบอร์โทร"),
            "category": st.column_config.SelectboxColumn("ประเภท", options=CONTACT_TYPES),
            "province": st.column_config.TextColumn("จังหวัด"),
            "notes": st.column_config.TextColumn("หมายเหตุ", width="large"),
            "next_follow_up": st.column_config.DateColumn("วันที่ติดตามครั้งถัดไป", format="DD/MM/YYYY"),
            "delete": st.column_config.CheckboxColumn("ลบ"),
        },
    )
    if st.button("บันทึกการแก้ไขและลบ", type="primary", width="stretch"):
        updated = replace_contacts(workplan, _records(edited))
        repository.save(profile, updated)
        st.rerun()


def _date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


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
