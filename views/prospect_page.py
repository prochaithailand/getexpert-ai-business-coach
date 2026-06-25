from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from models import AppUser, MemberProfile
from services.prospect_parser_service import parse_prospect_text
from services.subscription_service import has_active_subscription
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


AI_DRAFT_KEY = "prospect_ai_draft"
AI_INPUT_KEY = "prospect_ai_input"


def render_prospect_manager(
    profile: MemberProfile | None,
    authenticated_user: AppUser | None = None,
) -> None:
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
    _render_ai_add_form(profile, repository, workplan, authenticated_user)
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


def _render_ai_add_form(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
    authenticated_user: AppUser | None,
) -> None:
    st.subheader("เพิ่มผู้มุ่งหวังด้วย AI")
    st.caption("พิมพ์ข้อมูลตามธรรมชาติ ระบบจะช่วยจัดลงแบบฟอร์มให้ตรวจสอบก่อนบันทึก")
    if not _can_use_ai_prospect_entry(authenticated_user):
        st.warning("ฟีเจอร์นี้ใช้ได้เฉพาะสมาชิกที่เปิดใช้งานแล้ว")
        return
    if st.session_state.pop("_clear_prospect_ai_input", False):
        st.session_state.pop(AI_INPUT_KEY, None)

    raw_text = st.text_area(
        "ข้อมูลผู้มุ่งหวัง",
        placeholder="ตัวอย่าง: ชื่อสมชาย อายุ 42 ปี เป็นเจ้าของร้านกาแฟ อยู่รังสิต สนใจรายได้เสริม นัดคุยวันเสาร์นี้",
        key=AI_INPUT_KEY,
    )
    parse_column, clear_column = st.columns(2)
    if parse_column.button("ให้ AI ช่วยจัดข้อมูล", type="primary", width="stretch"):
        if not raw_text.strip():
            st.warning("กรุณาพิมพ์ข้อมูลผู้มุ่งหวังก่อน")
        else:
            st.session_state[AI_DRAFT_KEY] = parse_prospect_text(raw_text).to_dict()
            st.rerun()
    if clear_column.button("ล้างข้อมูล", width="stretch", key="clear_ai_prospect"):
        _clear_ai_draft()
        st.rerun()

    draft = st.session_state.get(AI_DRAFT_KEY)
    if not isinstance(draft, dict):
        return
    st.info("กรุณาตรวจสอบและแก้ไขข้อมูลให้ถูกต้องก่อนยืนยันบันทึก")
    with st.form("prospect_ai_preview_form"):
        first, second, third, fourth = st.columns(4)
        name = first.text_input("ชื่อ", value=str(draft.get("name", "")))
        age = second.number_input(
            "อายุ", min_value=0, max_value=120, value=int(draft.get("age", 0) or 0)
        )
        occupation = third.text_input("อาชีพ", value=str(draft.get("occupation", "")))
        phone = fourth.text_input("เบอร์โทร", value=str(draft.get("phone", "")))
        line_id = first.text_input("LINE ID", value=str(draft.get("line_id", "")))
        province = second.text_input("จังหวัด", value=str(draft.get("province", "")))
        area = third.text_input("พื้นที่", value=str(draft.get("area", "")))
        income = fourth.number_input(
            "รายได้ต่อเดือน (บาท)",
            min_value=0.0,
            value=float(draft.get("income", 0) or 0),
            step=1000.0,
        )
        status_value = str(draft.get("status", CONTACT_STATUSES[0]))
        category_value = str(draft.get("category", "D")).upper()
        status = first.selectbox(
            "สถานะ",
            CONTACT_STATUSES,
            index=CONTACT_STATUSES.index(status_value) if status_value in CONTACT_STATUSES else 0,
        )
        category = second.selectbox(
            "เกรด A/B/C/D",
            CONTACT_TYPES,
            index=CONTACT_TYPES.index(category_value) if category_value in CONTACT_TYPES else 3,
        )
        follow_up = third.date_input(
            "นัดหมายถัดไป",
            value=_date_value(str(draft.get("next_follow_up", ""))),
            format="DD/MM/YYYY",
        )
        interest = st.text_input("ความสนใจ", value=str(draft.get("interest", "")))
        pain_point = st.text_area(
            "ปัญหา / ความต้องการ", value=str(draft.get("pain_point", ""))
        )
        previous_experience = st.text_area(
            "ประสบการณ์เดิม", value=str(draft.get("previous_experience", ""))
        )
        notes = st.text_area("หมายเหตุ", value=str(draft.get("notes", "")))
        confirmed = st.form_submit_button(
            "ยืนยันบันทึกผู้มุ่งหวัง", type="primary", width="stretch"
        )
    if not confirmed:
        return
    if not _can_use_ai_prospect_entry(authenticated_user):
        st.error("บัญชีของคุณยังไม่พร้อมใช้งานฟีเจอร์นี้")
        return
    if not name.strip():
        st.warning("กรุณาระบุชื่อผู้มุ่งหวังก่อนบันทึก")
        return
    updated = add_contact(
        workplan,
        {
            "name": name,
            "age": age,
            "occupation": occupation,
            "phone": phone,
            "line_id": line_id,
            "province": province,
            "area": area,
            "income": income,
            "status": status,
            "category": category,
            "interest": interest,
            "pain_point": pain_point,
            "previous_experience": previous_experience,
            "next_follow_up": follow_up,
            "notes": notes,
        },
    )
    repository.save(profile, updated)
    _clear_ai_draft()
    st.session_state.prospect_flash_message = f"บันทึกผู้มุ่งหวัง {name} เรียบร้อยแล้ว"
    st.rerun()


def _can_use_ai_prospect_entry(user: AppUser | None) -> bool:
    return bool(user and has_active_subscription(user))


def _clear_ai_draft() -> None:
    st.session_state.pop(AI_DRAFT_KEY, None)
    st.session_state["_clear_prospect_ai_input"] = True


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
