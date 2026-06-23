from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from models import MemberProfile
from services.workplan_service import (
    CONTACT_STATUSES,
    CONTACT_TYPES,
    SessionWorkplanRepository,
    add_contact,
    delete_contact,
    priority_contacts,
    prospect_summary,
    update_contact,
    update_contact_status,
)


def render_prospect_manager(profile: MemberProfile | None) -> None:
    st.title("ผู้มุ่งหวัง")
    st.markdown(
        "<p class='section-lead'>จัดการรายชื่อ วางแผนติดตาม และพัฒนาผู้มุ่งหวังอย่างเป็นระบบ</p>",
        unsafe_allow_html=True,
    )
    if not profile or not profile.is_complete:
        st.warning("กรุณากรอกโปรไฟล์สมาชิกก่อนเริ่มจัดการผู้มุ่งหวัง")
        return

    repository = SessionWorkplanRepository(st.session_state)
    workplan = repository.get(profile)
    if message := st.session_state.pop("prospect_flash_message", None):
        st.success(message)
    _render_summary(workplan["contacts"])
    _render_add_form(profile, repository, workplan)
    _render_priority_preview(workplan["contacts"])
    _render_prospect_table(profile, repository, workplan)


def _render_summary(contacts: list[dict[str, Any]]) -> None:
    summary = prospect_summary(contacts)
    cards = (
        ("ผู้มุ่งหวังทั้งหมด", summary["total"]),
        ("จำนวน A", summary["A"]),
        ("จำนวน B", summary["B"]),
        ("จำนวน C", summary["C"]),
        ("จำนวน D", summary["D"]),
        ("สมัครแล้ว", summary["signed_up"]),
        ("นัดหมายแล้ว", summary["appointments"]),
    )
    for group in (cards[:4], cards[4:]):
        columns = st.columns(len(group))
        for column, (label, value) in zip(columns, group):
            column.metric(label, f"{value} ราย")


def _render_add_form(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    st.subheader("เพิ่มผู้มุ่งหวัง")
    with st.form("prospect_add_form", clear_on_submit=True):
        first, second, third, fourth = st.columns(4)
        name = first.text_input("ชื่อ", placeholder="ชื่อ-นามสกุล")
        phone = second.text_input("เบอร์โทร", placeholder="0xx-xxx-xxxx")
        age = third.number_input("อายุ", min_value=0, max_value=120, value=30)
        occupation = fourth.text_input("อาชีพ", placeholder="ตัวอย่าง: พนักงานบริษัท")
        income = first.number_input("รายได้ต่อเดือน (บาท)", min_value=0.0, step=1000.0)
        province = second.text_input("จังหวัด", placeholder="ตัวอย่าง: กรุงเทพมหานคร")
        category = third.selectbox("เกรด A/B/C/D", CONTACT_TYPES)
        status = fourth.selectbox("สถานะ", CONTACT_STATUSES)
        notes = st.text_area("หมายเหตุ", placeholder="บันทึกความสนใจ ข้อกังวล หรือประเด็นที่ต้องติดตาม")
        follow_up = st.date_input(
            "วันที่ติดตามครั้งถัดไป",
            value=None,
            format="DD/MM/YYYY",
        )
        submitted = st.form_submit_button("เพิ่มผู้มุ่งหวัง", type="primary", width="stretch")
    if not submitted:
        return
    if not name.strip():
        st.warning("กรุณาระบุชื่อผู้มุ่งหวังก่อนบันทึก")
        return
    updated = add_contact(
        workplan,
        {
            "name": name,
            "phone": phone,
            "age": age,
            "occupation": occupation,
            "income": income,
            "province": province,
            "category": category,
            "status": status,
            "notes": notes,
            "next_follow_up": follow_up,
        },
    )
    repository.save(profile, updated)
    st.rerun()


def _render_priority_preview(contacts: list[dict[str, Any]]) -> None:
    priorities = priority_contacts(contacts)[:5]
    if not priorities:
        return
    st.subheader("ลำดับแนะนำสำหรับติดตาม")
    for index, prospect in enumerate(priorities, start=1):
        follow_up = prospect["next_follow_up"] or "ยังไม่กำหนดวัน"
        st.markdown(
            f"**{index}. {prospect['name']}** - เกรด {prospect['category']} | "
            f"{prospect['status']} | ติดตาม: {follow_up}"
        )


def _render_prospect_table(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    st.subheader("รายชื่อผู้มุ่งหวัง")
    if not workplan["contacts"]:
        st.info("ยังไม่มีผู้มุ่งหวัง กรุณาเพิ่มรายชื่อจากแบบฟอร์มด้านบน")
        return
    filter_left, filter_right = st.columns(2)
    grade_filter = filter_left.selectbox(
        "กรองตามเกรด",
        ("ทั้งหมด", *CONTACT_TYPES),
        key="prospect_grade_filter",
    )
    status_filter = filter_right.selectbox(
        "กรองตามสถานะ",
        ("ทั้งหมด", *CONTACT_STATUSES),
        key="prospect_status_filter",
    )
    prospects = [
        prospect
        for prospect in workplan["contacts"]
        if (grade_filter == "ทั้งหมด" or prospect["category"] == grade_filter)
        and (status_filter == "ทั้งหมด" or prospect["status"] == status_filter)
    ]
    st.caption(f"แสดง {len(prospects)} จากทั้งหมด {len(workplan['contacts'])} ราย")
    if not prospects:
        st.warning("ไม่พบผู้มุ่งหวังที่ตรงกับตัวกรอง")
        return

    header = st.columns([1.9, 0.95, 0.55, 1.15, 1.15, 1.45, 1.05, 0.65, 0.5])
    for column, label in zip(
        header,
        ("ชื่อ / เบอร์โทร", "จังหวัด", "เกรด", "สถานะปัจจุบัน", "วันติดตาม", "สถานะใหม่", "อัปเดตสถานะ", "แก้ไข", "ลบ"),
    ):
        column.markdown(f"**{label}**")

    for prospect in prospects:
        with st.container(border=True):
            columns = st.columns([1.9, 0.95, 0.55, 1.15, 1.15, 1.45, 1.05, 0.65, 0.5])
            columns[0].markdown(
                f"**{prospect['name']}**<br><small>{prospect['phone'] or 'ไม่ระบุเบอร์โทร'}</small>",
                unsafe_allow_html=True,
            )
            columns[1].write(prospect.get("province") or "ไม่ระบุ")
            columns[2].write(prospect["category"])
            columns[3].write(prospect["status"])
            columns[4].write(prospect.get("next_follow_up") or "ยังไม่กำหนด")
            new_status = columns[5].selectbox(
                f"สถานะใหม่ของ {prospect['name']}",
                CONTACT_STATUSES,
                index=CONTACT_STATUSES.index(prospect["status"]),
                key=f"quick_status_{prospect['id']}",
                label_visibility="collapsed",
            )
            if columns[6].button("อัปเดตสถานะ", key=f"update_status_{prospect['id']}", width="stretch"):
                updated = update_contact_status(workplan, prospect["id"], new_status)
                repository.save(profile, updated)
                st.session_state.prospect_flash_message = f"อัปเดตสถานะของ {prospect['name']} เรียบร้อยแล้ว"
                st.rerun()
            if columns[7].button("แก้ไข", key=f"edit_prospect_{prospect['id']}", width="stretch"):
                st.session_state.prospect_edit_id = prospect["id"]
                st.session_state.pop("prospect_delete_id", None)
            if columns[8].button("ลบ", key=f"delete_prospect_{prospect['id']}", width="stretch"):
                st.session_state.prospect_delete_id = prospect["id"]
                st.session_state.pop("prospect_edit_id", None)

    _render_edit_form(profile, repository, workplan)
    _render_delete_confirmation(profile, repository, workplan)


def _render_edit_form(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    contact_id = st.session_state.get("prospect_edit_id")
    prospect = next((item for item in workplan["contacts"] if item["id"] == contact_id), None)
    if prospect is None:
        return
    st.subheader(f"แก้ไขผู้มุ่งหวัง: {prospect['name']}")
    with st.form(f"prospect_edit_form_{contact_id}"):
        first, second, third, fourth = st.columns(4)
        name = first.text_input("ชื่อ", value=prospect["name"], key=f"edit_name_{contact_id}")
        phone = second.text_input("เบอร์โทร", value=prospect["phone"], key=f"edit_phone_{contact_id}")
        age = third.number_input(
            "อายุ", min_value=0, max_value=120, value=int(prospect["age"]), key=f"edit_age_{contact_id}"
        )
        occupation = fourth.text_input(
            "อาชีพ", value=prospect["occupation"], key=f"edit_occupation_{contact_id}"
        )
        income = first.number_input(
            "รายได้ต่อเดือน (บาท)", min_value=0.0, value=float(prospect["income"]),
            step=1000.0, key=f"edit_income_{contact_id}",
        )
        province = second.text_input(
            "จังหวัด", value=prospect.get("province", ""), key=f"edit_province_{contact_id}"
        )
        category = third.selectbox(
            "เกรด A/B/C/D", CONTACT_TYPES, index=CONTACT_TYPES.index(prospect["category"]),
            key=f"edit_category_{contact_id}",
        )
        status = fourth.selectbox(
            "สถานะ", CONTACT_STATUSES, index=CONTACT_STATUSES.index(prospect["status"]),
            key=f"edit_status_{contact_id}",
        )
        notes = st.text_area(
            "หมายเหตุ", value=prospect.get("notes", ""), key=f"edit_notes_{contact_id}"
        )
        follow_up = st.date_input(
            "วันที่ติดตามครั้งถัดไป",
            value=_date_value(prospect.get("next_follow_up", "")),
            format="DD/MM/YYYY",
            key=f"edit_follow_up_{contact_id}",
        )
        save, cancel = st.columns(2)
        submitted = save.form_submit_button("บันทึกการแก้ไข", type="primary", width="stretch")
        cancelled = cancel.form_submit_button("ยกเลิก", width="stretch")
    if cancelled:
        st.session_state.pop("prospect_edit_id", None)
        st.rerun()
    if not submitted:
        return
    if not name.strip():
        st.warning("กรุณาระบุชื่อผู้มุ่งหวัง")
        return
    updated = update_contact(
        workplan,
        contact_id,
        {
            "name": name,
            "phone": phone,
            "age": age,
            "occupation": occupation,
            "income": income,
            "province": province,
            "category": category,
            "status": status,
            "notes": notes,
            "next_follow_up": follow_up,
        },
    )
    repository.save(profile, updated)
    st.session_state.pop("prospect_edit_id", None)
    st.session_state.prospect_flash_message = f"บันทึกการแก้ไข {name} เรียบร้อยแล้ว"
    st.rerun()


def _render_delete_confirmation(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    contact_id = st.session_state.get("prospect_delete_id")
    prospect = next((item for item in workplan["contacts"] if item["id"] == contact_id), None)
    if prospect is None:
        return
    st.warning(f"ยืนยันการลบผู้มุ่งหวัง {prospect['name']} ข้อมูลที่ลบแล้วไม่สามารถเรียกคืนได้")
    confirm, cancel = st.columns(2)
    if confirm.button("ยืนยันการลบ", type="primary", key=f"confirm_delete_{contact_id}", width="stretch"):
        updated = delete_contact(workplan, contact_id)
        repository.save(profile, updated)
        st.session_state.pop("prospect_delete_id", None)
        st.session_state.prospect_flash_message = f"ลบผู้มุ่งหวัง {prospect['name']} เรียบร้อยแล้ว"
        st.rerun()
    if cancel.button("ยกเลิก", key=f"cancel_delete_{contact_id}", width="stretch"):
        st.session_state.pop("prospect_delete_id", None)
        st.rerun()


def _date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
