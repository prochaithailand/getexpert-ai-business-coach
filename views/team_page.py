from __future__ import annotations

import streamlit as st

from models import AppUser, MemberProfile, Team
from services.auth_service import SessionUserStore
from services.team_service import SessionTeamRepository
from services.permissions import UNAUTHORIZED_MESSAGE, can_access_team_management
from services.supabase_service import SupabaseError, get_supabase_service


def render_team_management(
    profile: MemberProfile | None,
    authenticated_user: AppUser | None = None,
    user_store: SessionUserStore | None = None,
) -> None:
    st.title("จัดการทีม")
    if not can_access_team_management(authenticated_user or profile):
        st.warning(UNAUTHORIZED_MESSAGE)
        return
    st.markdown(
        "<p class='section-lead'>สร้างและดูแลข้อมูลทีมจากศูนย์กลาง เพื่อให้สมาชิกใช้ชื่อและรหัสทีมที่ถูกต้องตรงกัน</p>",
        unsafe_allow_html=True,
    )
    repository = SessionTeamRepository(st.session_state)
    repository.ensure_profile_team(profile)
    store = user_store or SessionUserStore(st.session_state, get_supabase_service(st.session_state))
    try:
        accounts = store.list_users()
    except SupabaseError as error:
        st.warning(f"ไม่สามารถโหลดรายชื่อผู้ใช้จาก Supabase ได้: {error}")
        accounts = []
    try:
        leader_accounts = store.list_users_by_role("Leader")
    except SupabaseError as error:
        st.warning(f"ไม่สามารถโหลดรายชื่อหัวหน้าทีมจาก Supabase ได้: {error}")
        leader_accounts = [account for account in accounts if account.role == "Leader"]
    if message := st.session_state.pop("team_flash_message", None):
        st.success(message)

    _render_create_form(repository, leader_accounts)
    _render_team_list(repository, accounts, leader_accounts)


def _render_create_form(repository: SessionTeamRepository, leaders: list[AppUser]) -> None:
    st.subheader("สร้างทีมใหม่")
    with st.form("team_create_form", clear_on_submit=True):
        first, second = st.columns(2)
        name = first.text_input("ชื่อทีม", placeholder="ตัวอย่าง: ทีมพลังดิจิทัล")
        team_id = second.text_input("รหัสทีม", placeholder="ตัวอย่าง: TEAM-001")
        leader_options = _account_options(leaders)
        leader_choice = first.selectbox(
            "หัวหน้าทีม",
            ("ยังไม่กำหนด", *leader_options),
            help="เลือกจากบัญชีสมาชิกในระบบ บทบาทจะเปลี่ยนเป็นผู้นำโดยอัตโนมัติ",
        )
        primary_sponsor = second.text_input("ผู้สนับสนุนหลัก", placeholder="ชื่อผู้สนับสนุนหลัก")
        notes = st.text_area("หมายเหตุ", placeholder="รายละเอียดหรือเป้าหมายของทีม")
        submitted = st.form_submit_button("สร้างทีม", type="primary", width="stretch")
    if submitted:
        selected_leader = _account_from_label(leaders, leader_choice)
        try:
            team = repository.create(Team(
                name, team_id, selected_leader.full_name if selected_leader else "ยังไม่กำหนด",
                primary_sponsor, notes,
            ))
            if selected_leader:
                team = repository.assign_leader(team.team_id, selected_leader)
        except (KeyError, ValueError) as error:
            st.warning(str(error))
            return
        st.session_state.team_flash_message = f"สร้างทีม {team.name} เรียบร้อยแล้ว"
        st.rerun()


def _render_team_list(
    repository: SessionTeamRepository,
    accounts: list[AppUser],
    leaders: list[AppUser],
) -> None:
    st.subheader("รายชื่อทีม")
    teams = repository.list()
    if not teams:
        st.info("ยังไม่มีข้อมูลทีมในระบบ")
        return
    st.caption(f"มีทีมทั้งหมด {len(teams)} ทีม")
    for team in teams:
        with st.container(border=True):
            summary, actions = st.columns([3, 1])
            summary.markdown(f"### {team.name}")
            summary.markdown(
                f"**รหัสทีม:** {team.team_id}  |  **หัวหน้าทีม:** {team.leader}  |  "
                f"**ผู้สนับสนุนหลัก:** {team.primary_sponsor or 'ยังไม่ระบุ'}"
            )
            if team.notes:
                summary.caption(team.notes)
            if actions.button("แก้ไข", key=f"edit_team_{team.team_id}", width="stretch"):
                st.session_state.team_edit_id = team.team_id
                _clear_team_actions("team_edit_id")
            if actions.button("กำหนดหัวหน้า", key=f"leader_team_{team.team_id}", width="stretch"):
                st.session_state.team_leader_id = team.team_id
                _clear_team_actions("team_leader_id")
            if actions.button("กำหนดสมาชิก", key=f"members_team_{team.team_id}", width="stretch"):
                st.session_state.team_members_id = team.team_id
                _clear_team_actions("team_members_id")
            if actions.button("ลบ", key=f"delete_team_{team.team_id}", width="stretch"):
                st.session_state.team_delete_id = team.team_id
                _clear_team_actions("team_delete_id")
    _render_edit_form(repository)
    _render_assign_leader(repository, leaders)
    _render_assign_members(repository, accounts)
    _render_delete_confirmation(repository)


def _render_edit_form(repository: SessionTeamRepository) -> None:
    original_id = st.session_state.get("team_edit_id")
    team = repository.get(original_id or "")
    if not team:
        return
    st.subheader(f"แก้ไขทีม: {team.name}")
    with st.form(f"team_edit_form_{original_id}"):
        first, second = st.columns(2)
        name = first.text_input("ชื่อทีม", value=team.name, key=f"team_edit_name_{original_id}")
        team_id = second.text_input("รหัสทีม", value=team.team_id, key=f"team_edit_id_value_{original_id}")
        first.text_input(
            "หัวหน้าทีมปัจจุบัน", value=team.leader,
            key=f"team_edit_leader_{original_id}", disabled=True,
        )
        primary_sponsor = second.text_input(
            "ผู้สนับสนุนหลัก", value=team.primary_sponsor, key=f"team_edit_sponsor_{original_id}"
        )
        notes = st.text_area("หมายเหตุ", value=team.notes, key=f"team_edit_notes_{original_id}")
        save, cancel = st.columns(2)
        submitted = save.form_submit_button("บันทึกการแก้ไข", type="primary", width="stretch")
        cancelled = cancel.form_submit_button("ยกเลิก", width="stretch")
    if cancelled:
        st.session_state.pop("team_edit_id", None)
        st.rerun()
    if submitted:
        try:
            updated = repository.update(
                original_id,
                Team(
                    name, team_id, team.leader, primary_sponsor, notes,
                    team.leader_email, team.invite_code,
                ),
            )
        except (KeyError, ValueError) as error:
            st.warning(str(error))
            return
        st.session_state.pop("team_edit_id", None)
        st.session_state.team_flash_message = f"อัปเดตทีม {updated.name} เรียบร้อยแล้ว"
        st.rerun()


def _render_assign_leader(repository: SessionTeamRepository, leaders: list[AppUser]) -> None:
    team_id = st.session_state.get("team_leader_id")
    team = repository.get(team_id or "")
    if not team:
        return
    candidates = leaders
    st.subheader(f"กำหนดหัวหน้าทีม: {team.name}")
    if not candidates:
        st.info("ยังไม่มีบัญชีสมาชิกหรือผู้นำที่สามารถกำหนดเป็นหัวหน้าทีมได้")
        return
    options = _account_options(candidates)
    with st.form(f"team_leader_form_{team.team_id}"):
        selected = st.selectbox("เลือกหัวหน้าทีม", options)
        save, cancel = st.columns(2)
        submitted = save.form_submit_button("บันทึกหัวหน้าทีม", type="primary", width="stretch")
        cancelled = cancel.form_submit_button("ยกเลิก", width="stretch")
    if cancelled:
        st.session_state.pop("team_leader_id", None)
        st.rerun()
    if submitted:
        account = _account_from_label(candidates, selected)
        if not account:
            st.warning("กรุณาเลือกหัวหน้าทีม")
            return
        try:
            repository.assign_leader(team.team_id, account)
        except (KeyError, ValueError) as error:
            st.warning(str(error))
            return
        st.session_state.pop("team_leader_id", None)
        st.session_state.team_flash_message = f"กำหนด {account.full_name} เป็นหัวหน้าทีม {team.name} แล้ว"
        st.rerun()


def _render_assign_members(repository: SessionTeamRepository, accounts: list[AppUser]) -> None:
    team_id = st.session_state.get("team_members_id")
    team = repository.get(team_id or "")
    if not team:
        return
    candidates = [account for account in accounts if account.role != "Admin"]
    st.subheader(f"กำหนดสมาชิกเข้าทีม: {team.name}")
    if not candidates:
        st.info("ยังไม่มีบัญชีสมาชิกที่สามารถกำหนดเข้าทีมได้")
        return
    options = _account_options(candidates)
    with st.form(f"team_members_form_{team.team_id}"):
        selected = st.multiselect("เลือกสมาชิก", options)
        st.caption("สมาชิกที่เลือกจะถูกย้ายมาอยู่ทีมนี้ โดยบทบาทเดิมจะไม่เปลี่ยนแปลง")
        save, cancel = st.columns(2)
        submitted = save.form_submit_button("บันทึกสมาชิกทีม", type="primary", width="stretch")
        cancelled = cancel.form_submit_button("ยกเลิก", width="stretch")
    if cancelled:
        st.session_state.pop("team_members_id", None)
        st.rerun()
    if submitted:
        selected_accounts = [
            account for label in selected
            if (account := _account_from_label(candidates, label)) is not None
        ]
        if not selected_accounts:
            st.warning("กรุณาเลือกสมาชิกอย่างน้อย 1 คน")
            return
        try:
            repository.assign_members(team.team_id, selected_accounts)
        except (KeyError, ValueError) as error:
            st.warning(str(error))
            return
        st.session_state.pop("team_members_id", None)
        st.session_state.team_flash_message = f"เพิ่มสมาชิก {len(selected_accounts)} คนเข้าทีม {team.name} แล้ว"
        st.rerun()


def _render_delete_confirmation(repository: SessionTeamRepository) -> None:
    team_id = st.session_state.get("team_delete_id")
    team = repository.get(team_id or "")
    if not team:
        return
    st.warning(f"ยืนยันการลบทีม {team.name} ({team.team_id}) ข้อมูลทีมในโปรไฟล์สมาชิกปัจจุบันจะถูกล้าง")
    confirm, cancel = st.columns(2)
    if confirm.button("ยืนยันการลบทีม", type="primary", width="stretch"):
        repository.delete(team.team_id)
        st.session_state.pop("team_delete_id", None)
        st.session_state.team_flash_message = f"ลบทีม {team.name} เรียบร้อยแล้ว"
        st.rerun()
    if cancel.button("ยกเลิกการลบ", width="stretch"):
        st.session_state.pop("team_delete_id", None)
        st.rerun()


def _account_options(accounts: list[AppUser], roles: set[str] | None = None) -> tuple[str, ...]:
    filtered = [account for account in accounts if roles is None or account.role in roles]
    return tuple(f"{account.full_name} ({account.email})" for account in filtered)


def _account_from_label(accounts: list[AppUser], label: str) -> AppUser | None:
    return next(
        (account for account in accounts if label == f"{account.full_name} ({account.email})"),
        None,
    )


def _clear_team_actions(keep: str) -> None:
    for key in ("team_edit_id", "team_leader_id", "team_members_id", "team_delete_id"):
        if key != keep:
            st.session_state.pop(key, None)
