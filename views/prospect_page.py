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
from translations import translate


def _language() -> str:
    return str(st.session_state.get("language", "th"))


def _t(key: str, **values: object) -> str:
    text = translate(key, _language())
    return text.format(**values) if values else text


def _option_label(option: object) -> str:
    return _t(str(option))


AI_DRAFT_KEY = "prospect_ai_draft"
AI_INPUT_KEY = "prospect_ai_input"
PROSPECT_SEARCH_FIELDS = (
    "name",
    "phone",
    "province",
    "area",
    "occupation",
    "status",
    "category",
    "notes",
    "line_id",
    "interest",
    "pain_point",
    "previous_experience",
)
PROSPECT_STATUS_FILTERS = {
    "ทั้งหมด": "",
    "ยังไม่ติดต่อ": "ยังไม่ติดต่อ",
    "ติดต่อแล้ว": "ติดต่อแล้ว",
    "นัดหมาย": "นัดหมายแล้ว",
    "สมัครแล้ว": "สมัครแล้ว",
    "ปฏิเสธ": "ไม่สนใจ",
}


def render_prospect_manager(
    profile: MemberProfile | None,
    authenticated_user: AppUser | None = None,
) -> None:
    st.title(_t("Prospects"))
    st.markdown(
        f"<p class='section-lead'>{_t('Prospect Page Description')}</p>",
        unsafe_allow_html=True,
    )
    if not profile or not profile.is_complete:
        st.warning(_t("Prospect Profile Required"))
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
        (_t("Total Prospects"), summary["total"]),
        ("A", summary["A"]),
        ("B", summary["B"]),
        ("C", summary["C"]),
        ("D", summary["D"]),
        (_t("Signed Up"), summary["signed_up"]),
        (_t("Appointment Done"), summary["appointments"]),
    )
    for group in (cards[:4], cards[4:]):
        columns = st.columns(len(group))
        for column, (label, value) in zip(columns, group):
            column.metric(label, f"{value} {_t('Prospect Unit')}")


def _render_ai_add_form(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
    authenticated_user: AppUser | None,
) -> None:
    st.subheader(_t("AI Prospect Entry"))
    st.caption(_t("AI Prospect Entry Description"))
    if not _can_use_ai_prospect_entry(authenticated_user):
        st.warning(_t("AI Prospect Active Only"))
        return
    if st.session_state.pop("_clear_prospect_ai_input", False):
        st.session_state.pop(AI_INPUT_KEY, None)

    raw_text = st.text_area(
        _t("Prospect Data"),
        placeholder=_t("AI Prospect Placeholder"),
        key=AI_INPUT_KEY,
    )
    parse_column, clear_column = st.columns(2)
    if parse_column.button(_t("Parse Prospect Button"), type="primary", width="stretch"):
        if not raw_text.strip():
            st.warning(_t("Prospect Input Required"))
        else:
            st.session_state[AI_DRAFT_KEY] = parse_prospect_text(raw_text).to_dict()
            st.rerun()
    if clear_column.button(_t("Clear Data"), width="stretch", key="clear_ai_prospect"):
        _clear_ai_draft()
        st.rerun()

    draft = st.session_state.get(AI_DRAFT_KEY)
    if not isinstance(draft, dict):
        return
    st.info(_t("Prospect Preview Info"))
    with st.form("prospect_ai_preview_form"):
        first, second, third, fourth = st.columns(4)
        name = first.text_input(_t("Name"), value=str(draft.get("name", "")))
        age = second.number_input(
            _t("Age"), min_value=0, max_value=120, value=int(draft.get("age", 0) or 0)
        )
        occupation = third.text_input(_t("Occupation"), value=str(draft.get("occupation", "")))
        phone = fourth.text_input(_t("Phone"), value=str(draft.get("phone", "")))
        line_id = first.text_input("LINE ID", value=str(draft.get("line_id", "")))
        province = second.text_input(_t("Province"), value=str(draft.get("province", "")))
        area = third.text_input(_t("Area"), value=str(draft.get("area", "")))
        income = fourth.number_input(
            _t("Monthly Income"),
            min_value=0.0,
            value=float(draft.get("income", 0) or 0),
            step=1000.0,
        )
        status_value = str(draft.get("status", CONTACT_STATUSES[0]))
        category_value = str(draft.get("category", "D")).upper()
        status = first.selectbox(
            _t("Status"),
            CONTACT_STATUSES,
            index=CONTACT_STATUSES.index(status_value) if status_value in CONTACT_STATUSES else 0,
            format_func=_option_label,
        )
        category = second.selectbox(
            _t("Grade Label"),
            CONTACT_TYPES,
            index=CONTACT_TYPES.index(category_value) if category_value in CONTACT_TYPES else 3,
        )
        follow_up = third.date_input(
            _t("Next Follow Up"),
            value=_date_value(str(draft.get("next_follow_up", ""))),
            format="DD/MM/YYYY",
        )
        interest = st.text_input(_t("Interest"), value=str(draft.get("interest", "")))
        pain_point = st.text_area(
            _t("Pain Point"), value=str(draft.get("pain_point", ""))
        )
        previous_experience = st.text_area(
            _t("Previous Experience"), value=str(draft.get("previous_experience", ""))
        )
        notes = st.text_area(_t("Notes"), value=str(draft.get("notes", "")))
        confirmed = st.form_submit_button(
            _t("Confirm Save Prospect"), type="primary", width="stretch"
        )
    if not confirmed:
        return
    if not _can_use_ai_prospect_entry(authenticated_user):
        st.error(_t("AI Prospect Active Only"))
        return
    if not name.strip():
        st.warning(_t("Prospect Name Required"))
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
    st.session_state.prospect_flash_message = _t("Prospect Saved", name=name)
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
    st.subheader(_t("Add Prospect"))
    with st.form("prospect_add_form", clear_on_submit=True):
        first, second, third, fourth = st.columns(4)
        name = first.text_input(_t("Name"), placeholder=_t("Full Name"))
        phone = second.text_input(_t("Phone"), placeholder="0xx-xxx-xxxx")
        age = third.number_input(_t("Age"), min_value=0, max_value=120, value=30)
        occupation = fourth.text_input(_t("Occupation"), placeholder=_t("Occupation Placeholder"))
        income = first.number_input(_t("Monthly Income"), min_value=0.0, step=1000.0)
        province = second.text_input(_t("Province"), placeholder=_t("Province Placeholder"))
        category = third.selectbox(_t("Grade Label"), CONTACT_TYPES)
        status = fourth.selectbox(_t("Status"), CONTACT_STATUSES, format_func=_option_label)
        notes = st.text_area(_t("Notes"), placeholder=_t("Notes Placeholder"))
        follow_up = st.date_input(
            _t("Next Follow Up Date"),
            value=None,
            format="DD/MM/YYYY",
        )
        submitted = st.form_submit_button(_t("Add Prospect"), type="primary", width="stretch")
    if not submitted:
        return
    if not name.strip():
        st.warning(_t("Prospect Name Required"))
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
    st.subheader(_t("Follow Up Priority"))
    for index, prospect in enumerate(priorities, start=1):
        follow_up = prospect["next_follow_up"] or _t("No Follow Up Date")
        st.markdown(
            f"**{index}. {prospect['name']}** - {_t('Grade Label')} {prospect['category']} | "
            f"{_t(str(prospect['status']))} | {_t('Follow Up Date')}: {follow_up}"
        )


def _render_prospect_table(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    st.subheader(_t("Prospect List"))
    if not workplan["contacts"]:
        st.info(_t("No Prospects Yet"))
        return
    search_query = st.text_input(
        _t("Search Prospects"),
        placeholder=_t("Search Prospects Placeholder"),
        key="prospect_search_query",
    )
    filter_left, filter_right = st.columns(2)
    grade_filter = filter_left.selectbox(
        _t("Filter By Grade"),
        ("ทั้งหมด", *CONTACT_TYPES),
        key="prospect_grade_filter",
        format_func=_option_label,
    )
    status_filter = filter_right.selectbox(
        _t("Filter By Status"),
        tuple(PROSPECT_STATUS_FILTERS),
        key="prospect_status_filter",
        format_func=_option_label,
    )
    prospects = filter_prospects(
        workplan["contacts"],
        search_query,
        status_filter,
        grade_filter,
    )
    st.caption(_t("Prospect Search Result", shown=len(prospects), total=len(workplan["contacts"])))
    if not prospects:
        st.warning(_t("No Matching Prospects"))
        _render_edit_form(profile, repository, workplan)
        _render_delete_confirmation(profile, repository, workplan)
        return

    header = st.columns([1.9, 0.95, 0.55, 1.15, 1.15, 1.45, 1.05, 0.65, 0.5])
    for column, label in zip(
        header,
        (
            _t("Table Name Phone"),
            _t("Province"),
            _t("Grade Label"),
            _t("Current Status"),
            _t("Follow Up Date"),
            _t("New Status"),
            _t("Update Status"),
            _t("Edit"),
            _t("Delete"),
        ),
    ):
        column.markdown(f"**{label}**")

    for prospect in prospects:
        with st.container(border=True):
            columns = st.columns([1.9, 0.95, 0.55, 1.15, 1.15, 1.45, 1.05, 0.65, 0.5])
            columns[0].markdown(
                f"**{prospect['name']}**<br><small>{prospect['phone'] or _t('No Phone Specified')}</small>",
                unsafe_allow_html=True,
            )
            columns[1].write(prospect.get("province") or _t("Not Specified Short"))
            columns[2].write(prospect["category"])
            columns[3].write(_t(str(prospect["status"])))
            columns[4].write(prospect.get("next_follow_up") or _t("No Follow Up Date"))
            new_status = columns[5].selectbox(
                _t("Prospect New Status Label", name=prospect["name"]),
                CONTACT_STATUSES,
                index=CONTACT_STATUSES.index(prospect["status"]),
                key=f"quick_status_{prospect['id']}",
                label_visibility="collapsed",
                format_func=_option_label,
            )
            if columns[6].button(_t("Update Status"), key=f"update_status_{prospect['id']}", width="stretch"):
                updated = update_contact_status(workplan, prospect["id"], new_status)
                repository.save(profile, updated)
                st.session_state.prospect_flash_message = _t("Prospect Status Updated", name=prospect["name"])
                st.rerun()
            if columns[7].button(_t("Edit"), key=f"edit_prospect_{prospect['id']}", width="stretch"):
                st.session_state.prospect_edit_id = prospect["id"]
                st.session_state.pop("prospect_delete_id", None)
            if columns[8].button(_t("Delete"), key=f"delete_prospect_{prospect['id']}", width="stretch"):
                st.session_state.prospect_delete_id = prospect["id"]
                st.session_state.pop("prospect_edit_id", None)

    _render_edit_form(profile, repository, workplan)
    _render_delete_confirmation(profile, repository, workplan)


def filter_prospects(
    contacts: list[dict[str, Any]],
    query: str = "",
    status_filter: str = "ทั้งหมด",
    category_filter: str = "ทั้งหมด",
) -> list[dict[str, Any]]:
    search = str(query or "").strip().casefold()
    phone_search = "".join(character for character in search if character.isdigit())
    expected_status = PROSPECT_STATUS_FILTERS.get(status_filter, status_filter)
    results: list[dict[str, Any]] = []
    for prospect in contacts:
        if category_filter != "ทั้งหมด" and str(prospect.get("category", "")) != category_filter:
            continue
        if expected_status and str(prospect.get("status", "")) != expected_status:
            continue
        if search:
            values = [
                str(prospect.get(field, "") or "").casefold()
                for field in PROSPECT_SEARCH_FIELDS
            ]
            text_match = any(search in value for value in values)
            prospect_phone = "".join(
                character
                for character in str(prospect.get("phone", ""))
                if character.isdigit()
            )
            phone_match = bool(phone_search and phone_search in prospect_phone)
            if not text_match and not phone_match:
                continue
        results.append(prospect)
    return results


def _render_edit_form(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
) -> None:
    contact_id = st.session_state.get("prospect_edit_id")
    prospect = next((item for item in workplan["contacts"] if item["id"] == contact_id), None)
    if prospect is None:
        return
    st.subheader(_t("Edit Prospect Title", name=prospect["name"]))
    with st.form(f"prospect_edit_form_{contact_id}"):
        first, second, third, fourth = st.columns(4)
        name = first.text_input(_t("Name"), value=prospect["name"], key=f"edit_name_{contact_id}")
        phone = second.text_input(_t("Phone"), value=prospect["phone"], key=f"edit_phone_{contact_id}")
        age = third.number_input(
            _t("Age"), min_value=0, max_value=120, value=int(prospect["age"]), key=f"edit_age_{contact_id}"
        )
        occupation = fourth.text_input(
            _t("Occupation"), value=prospect["occupation"], key=f"edit_occupation_{contact_id}"
        )
        income = first.number_input(
            _t("Edit Monthly Income"), min_value=0.0, value=float(prospect["income"]),
            step=1000.0, key=f"edit_income_{contact_id}",
        )
        province = second.text_input(
            _t("Province"), value=prospect.get("province", ""), key=f"edit_province_{contact_id}"
        )
        category = third.selectbox(
            _t("Grade Label"), CONTACT_TYPES, index=CONTACT_TYPES.index(prospect["category"]),
            key=f"edit_category_{contact_id}",
        )
        status = fourth.selectbox(
            _t("Status"), CONTACT_STATUSES, index=CONTACT_STATUSES.index(prospect["status"]),
            key=f"edit_status_{contact_id}",
            format_func=_option_label,
        )
        notes = st.text_area(
            _t("Notes"), value=prospect.get("notes", ""), key=f"edit_notes_{contact_id}"
        )
        follow_up = st.date_input(
            _t("Next Follow Up Date"),
            value=_date_value(prospect.get("next_follow_up", "")),
            format="DD/MM/YYYY",
            key=f"edit_follow_up_{contact_id}",
        )
        save, cancel = st.columns(2)
        submitted = save.form_submit_button(_t("Save Edit"), type="primary", width="stretch")
        cancelled = cancel.form_submit_button(_t("Cancel"), width="stretch")
    if cancelled:
        st.session_state.pop("prospect_edit_id", None)
        st.rerun()
    if not submitted:
        return
    if not name.strip():
        st.warning(_t("Prospect Name Required"))
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
    st.session_state.prospect_flash_message = _t("Prospect Edit Saved", name=name)
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
    st.warning(_t("Prospect Delete Confirm", name=prospect["name"]))
    confirm, cancel = st.columns(2)
    if confirm.button(_t("Confirm Delete"), type="primary", key=f"confirm_delete_{contact_id}", width="stretch"):
        updated = delete_contact(workplan, contact_id)
        repository.save(profile, updated)
        st.session_state.pop("prospect_delete_id", None)
        st.session_state.prospect_flash_message = _t("Prospect Deleted", name=prospect["name"])
        st.rerun()
    if cancel.button(_t("Cancel"), key=f"cancel_delete_{contact_id}", width="stretch"):
        st.session_state.pop("prospect_delete_id", None)
        st.rerun()


def _date_value(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None
