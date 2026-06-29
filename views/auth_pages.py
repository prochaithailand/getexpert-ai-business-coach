from __future__ import annotations

import os

import streamlit as st

from config import DEFAULT_EMBEDDING_MODEL, DEFAULT_OPENAI_MODEL
from models import AppUser
from services.auth_service import SessionUserStore
from services.permissions import UNAUTHORIZED_MESSAGE
from services.openai_runtime_service import (
    get_openai_diagnostic_health,
    load_openai_config,
)
from services.supabase_service import SupabaseError
from services.subscription_service import (
    effective_subscription_status,
    normalize_subscription_user,
    trial_days_remaining,
)


def _active_brand() -> dict[str, str]:
    return st.session_state.get("_active_brand", {})


def render_login(store: SessionUserStore) -> None:
    brand = _active_brand()
    app_name = brand.get("app_name", "GetExpert AI Business Coach")
    st.title("เข้าสู่ระบบ")
    st.markdown(f"<p class='section-lead'>เข้าสู่ระบบเพื่อใช้งาน {app_name}</p>", unsafe_allow_html=True)
    login_in_progress = bool(st.session_state.get("login_in_progress", False))
    login_error = st.session_state.pop("login_error_message", "")
    if login_in_progress:
        st.info("กำลังเข้าสู่ระบบ กรุณารอสักครู่...")
    elif login_error:
        st.error(login_error)
    with st.form("login_form"):
        email = st.text_input("อีเมล", placeholder="name@example.com")
        password = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button(
            "กำลังเข้าสู่ระบบ..." if login_in_progress else "เข้าสู่ระบบ",
            type="primary",
            width="stretch",
            disabled=login_in_progress,
        )
    if submitted and not login_in_progress:
        st.session_state["login_in_progress"] = True
        st.session_state["pending_login_email"] = email
        st.session_state["pending_login_password"] = password
        st.rerun()

    if login_in_progress:
        pending_email = st.session_state.get("pending_login_email", "")
        pending_password = st.session_state.get("pending_login_password", "")
        if not pending_email and not pending_password:
            st.session_state["login_in_progress"] = False
            return
        try:
            with st.spinner("กำลังเข้าสู่ระบบ กรุณารอสักครู่..."):
                user = store.authenticate(pending_email, pending_password)
        except SupabaseError as error:
            st.session_state["login_in_progress"] = False
            st.session_state["login_error_message"] = f"ไม่สามารถเข้าสู่ระบบผ่าน Supabase ได้: {error}"
            st.session_state.pop("pending_login_email", None)
            st.session_state.pop("pending_login_password", None)
            st.rerun()
        except Exception:
            st.session_state["login_in_progress"] = False
            st.session_state.pop("pending_login_email", None)
            st.session_state.pop("pending_login_password", None)
            raise
        st.session_state.pop("pending_login_email", None)
        st.session_state.pop("pending_login_password", None)
        if user:
            st.session_state["login_in_progress"] = False
            st.success(f"เข้าสู่ระบบสำเร็จ ยินดีต้อนรับคุณ{user.full_name}")
            st.rerun()
        st.session_state["login_in_progress"] = False
        st.session_state["login_error_message"] = "อีเมลหรือรหัสผ่านไม่ถูกต้อง"
        st.rerun()


def render_register(store: SessionUserStore, referral_code: str = "") -> None:
    brand = _active_brand()
    short_name = brand.get("short_name", "GetExpert")
    st.title("สมัครสมาชิก")
    st.markdown(f"<p class='section-lead'>สร้างบัญชีใหม่เพื่อเริ่มต้นใช้งาน {short_name} บัญชีใหม่จะเป็นสมาชิกโดยอัตโนมัติ</p>", unsafe_allow_html=True)
    if referral_code:
        st.info("ลิงก์แนะนำนี้ใช้สำหรับบันทึกสิทธิ์ referral เท่านั้น ไม่ได้เพิ่มคุณเข้าทีมโดยอัตโนมัติ")
    with st.form("register_form"):
        full_name = st.text_input("ชื่อ-นามสกุล", placeholder="ชื่อและนามสกุลของคุณ")
        email = st.text_input("อีเมล", placeholder="name@example.com")
        password = st.text_input("รหัสผ่าน", type="password", help="อย่างน้อย 8 ตัวอักษร")
        st.text_input("บทบาท", value="สมาชิก", disabled=True)
        submitted = st.form_submit_button("สมัครสมาชิก", type="primary", width="stretch")
        st.caption(
            f"เมื่อสมัครใช้งาน {short_name} คุณยินยอมให้ระบบส่งอีเมลที่เกี่ยวข้องกับบัญชีของคุณ "
            "เช่น การยืนยันการสมัคร การแจ้งสถานะทดลองใช้ฟรี การชำระเงิน และการเปิดใช้งานบริการ"
        )
        marketing_email_opt_in = st.checkbox(
            "ฉันต้องการรับบทความ เทคนิคการใช้ AI เพื่อพัฒนาธุรกิจ ข่าวสาร "
            f"และข้อเสนอจาก {short_name} ทางอีเมล",
            value=False,
        )
    if submitted:
        try:
            store.register(
                email,
                password,
                full_name,
                marketing_email_opt_in=marketing_email_opt_in,
            )
        except (ValueError, SupabaseError) as error:
            st.warning(str(error))
            return
        st.success("สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ")


def render_forgot_password(
    store: SessionUserStore,
    redirect_url: str,
) -> None:
    st.title("ลืมรหัสผ่าน")
    st.markdown(
        "<p class='section-lead'>กรอกอีเมลที่ใช้สมัคร ระบบจะส่งลิงก์สำหรับตั้งรหัสผ่านใหม่</p>",
        unsafe_allow_html=True,
    )
    with st.form("forgot_password_form"):
        email = st.text_input("อีเมล", placeholder="name@example.com")
        submitted = st.form_submit_button(
            "ส่งลิงก์รีเซ็ตรหัสผ่าน",
            type="primary",
            width="stretch",
        )
    if not submitted:
        return
    try:
        store.request_password_reset(email, redirect_url)
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
        return
    st.success(
        "หากอีเมลนี้มีบัญชีอยู่ในระบบ ระบบได้ส่งลิงก์รีเซ็ตรหัสผ่านแล้ว "
        "กรุณาตรวจสอบกล่องจดหมายและอีเมลขยะ"
    )


def render_reset_password(
    store: SessionUserStore,
    recovery_access_token: str,
) -> None:
    brand = _active_brand()
    short_name = brand.get("short_name", "GetExpert")
    st.title("ตั้งรหัสผ่านใหม่")
    st.markdown(
        f"<p class='section-lead'>กำหนดรหัสผ่านใหม่สำหรับบัญชี {short_name} ของคุณ</p>",
        unsafe_allow_html=True,
    )
    with st.form("reset_password_form", clear_on_submit=True):
        new_password = st.text_input(
            "รหัสผ่านใหม่",
            type="password",
            help="รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร",
        )
        confirm_password = st.text_input(
            "ยืนยันรหัสผ่านใหม่",
            type="password",
        )
        submitted = st.form_submit_button(
            "บันทึกรหัสผ่านใหม่",
            type="primary",
            width="stretch",
        )
    if not submitted:
        return
    try:
        store.reset_password(
            recovery_access_token,
            new_password,
            confirm_password,
        )
    except (PermissionError, RuntimeError, ValueError) as error:
        st.error(str(error))
        return
    st.session_state.pop("password_recovery_access_token", None)
    st.session_state["password_reset_completed"] = True
    st.rerun()


def render_logout(store: SessionUserStore, user: AppUser) -> None:
    st.title("ออกจากระบบ")
    st.info(f"คุณกำลังใช้งานในชื่อ {user.full_name}")
    if st.button("ยืนยันออกจากระบบ", type="primary", width="stretch"):
        store.logout()
        st.rerun()


def render_account_settings(store: SessionUserStore, user: AppUser | None) -> None:
    st.title("ตั้งค่าบัญชี")
    if user is None:
        st.warning("กรุณาเข้าสู่ระบบก่อนเปลี่ยนรหัสผ่าน")
        return
    user = normalize_subscription_user(user)
    st.markdown(
        "<p class='section-lead'>จัดการความปลอดภัยสำหรับบัญชีของคุณ</p>",
        unsafe_allow_html=True,
    )
    status = effective_subscription_status(user)
    status_label = {
        "active": "ใช้งานอยู่",
        "trialing": "ทดลองใช้ฟรี",
        "pending_payment": "รอชำระเงิน / รออนุมัติ",
        "expired": "หมดอายุ",
        "suspended": "ถูกระงับ",
    }.get(status, status)
    st.subheader("สถานะสมาชิก")
    st.write(f"สถานะสมาชิก: **{status_label}**")
    if user.subscription_expires_at:
        st.write(f"ใช้งานได้ถึง: **{user.subscription_expires_at[:10]}**")
    if user.trial_ends_at:
        if status == "trialing":
            st.write(f"วันหมดอายุทดลองใช้ฟรี: **{user.trial_ends_at[:10]}**")
            st.write(f"เหลือเวลาทดลองใช้ฟรี: **{trial_days_remaining(user)} วัน**")
        elif user.trial_used and status == "expired" and not user.subscription_expires_at:
            st.warning("สิทธิ์ทดลองใช้ฟรีหมดอายุแล้ว กรุณาชำระเงินเพื่อใช้งานระบบต่อ")
    st.subheader("เปลี่ยนรหัสผ่าน")
    st.caption(f"บัญชี: {user.email}")
    with st.form("change_password_form", clear_on_submit=True):
        new_password = st.text_input(
            "รหัสผ่านใหม่",
            type="password",
            help="รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร",
        )
        confirm_password = st.text_input(
            "ยืนยันรหัสผ่านใหม่",
            type="password",
        )
        submitted = st.form_submit_button(
            "บันทึกรหัสผ่านใหม่",
            type="primary",
            width="stretch",
        )
    if not submitted:
        return
    try:
        store.change_password(new_password, confirm_password)
    except (PermissionError, RuntimeError, ValueError) as error:
        st.error(str(error))
        return
    st.success("เปลี่ยนรหัสผ่านเรียบร้อยแล้ว")


def render_user_management(store: SessionUserStore, user: AppUser) -> None:
    st.title("จัดการผู้ใช้")
    if user.role != "Admin":
        st.warning(UNAUTHORIZED_MESSAGE)
        return
    st.markdown(
        "<p class='section-lead'>จัดการสิทธิ์ผู้ใช้ สถานะสมาชิก และการอนุมัติการใช้งานในรูปแบบที่ค้นหาและจัดการได้ง่ายขึ้น</p>",
        unsafe_allow_html=True,
    )
    openai_config = load_openai_config(
        st.secrets,
        os.environ,
        default_responses_model=DEFAULT_OPENAI_MODEL,
        default_embedding_model=DEFAULT_EMBEDDING_MODEL,
    )
    _render_openai_diagnostic(get_openai_diagnostic_health(openai_config))

    accounts = [normalize_subscription_user(account) for account in store.list_users()]
    summary = _user_management_summary(accounts)
    summary_labels = (
        ("ผู้ใช้ทั้งหมด", summary["total"]),
        ("Trialing", summary["trialing"]),
        ("Active", summary["active"]),
        ("Pending Payment", summary["pending_payment"]),
        ("Partner", summary["partner"]),
        ("Leader", summary["leader"]),
        ("Suspended", summary["suspended"]),
    )
    for column, (label, value) in zip(st.columns(len(summary_labels)), summary_labels):
        column.metric(label, value)

    st.markdown("### ค้นหาและกรองผู้ใช้")
    search_query = st.text_input(
        "ค้นหาผู้ใช้",
        placeholder="ค้นหาด้วยชื่อหรืออีเมล",
        key="admin_user_search",
    )
    filter_columns = st.columns(4)
    role_filter = filter_columns[0].selectbox(
        "บทบาท",
        ("ทั้งหมด", "Member", "Leader", "Partner", "Admin"),
        key="admin_user_role_filter",
    )
    status_filter = filter_columns[1].selectbox(
        "สถานะสมาชิก",
        ("ทั้งหมด", "trialing", "active", "pending_payment", "suspended", "expired"),
        key="admin_user_status_filter",
    )
    plan_filter = filter_columns[2].selectbox(
        "แพ็กเกจ",
        ("ทั้งหมด", "Member", "Leader"),
        key="admin_user_plan_filter",
    )
    page_size = int(
        filter_columns[3].selectbox(
            "จำนวนต่อหน้า",
            (20, 50, 100),
            key="admin_user_page_size",
        )
    )

    filter_signature = (
        search_query.strip().casefold(),
        role_filter,
        status_filter,
        plan_filter,
        page_size,
    )
    if st.session_state.get("admin_user_filter_signature") != filter_signature:
        st.session_state["admin_user_page"] = 1
        st.session_state["admin_user_filter_signature"] = filter_signature

    filtered_accounts = _filter_user_accounts(
        accounts,
        search_query=search_query,
        role_filter=role_filter,
        status_filter=status_filter,
        plan_filter=plan_filter,
    )
    current_page = int(st.session_state.get("admin_user_page", 1) or 1)
    page_accounts, current_page, start_index, end_index, total_pages = _paginate_user_accounts(
        filtered_accounts,
        page=current_page,
        page_size=page_size,
    )
    st.session_state["admin_user_page"] = current_page

    st.caption(f"แสดง {start_index}-{end_index} จาก {len(filtered_accounts)} คน")
    previous_column, page_column, next_column = st.columns([1, 2, 1])
    if previous_column.button(
        "ก่อนหน้า",
        key="admin_user_previous_page",
        disabled=current_page <= 1,
        width="stretch",
    ):
        st.session_state["admin_user_page"] = current_page - 1
        st.rerun()
    page_column.markdown(
        f"<p style='text-align:center;margin-top:0.45rem;'>หน้า {current_page} / {total_pages}</p>",
        unsafe_allow_html=True,
    )
    if next_column.button(
        "ถัดไป",
        key="admin_user_next_page",
        disabled=current_page >= total_pages,
        width="stretch",
    ):
        st.session_state["admin_user_page"] = current_page + 1
        st.rerun()

    if not page_accounts:
        st.info("ไม่พบผู้ใช้ที่ตรงกับเงื่อนไข")
        return

    for account in page_accounts:
        with st.container(border=True):
            name_column, role_column, subscription_column, expiry_column = st.columns([2.5, 1.1, 1.8, 1.4])
            name_column.markdown(f"**{account.full_name or '-'}**  \n{account.email}")
            role_column.markdown(
                f"บทบาท: **{_role_label(account.role)}**  \nReferral Rate: **{_referral_rate_for(account)}%**"
            )
            subscription_column.markdown(
                f"สถานะ: **{account.subscription_status or '-'}**  \nแพ็กเกจ: **{account.subscription_plan or '-'}**"
            )
            expiry_column.markdown(_account_expiry_summary(account))

            with st.expander("จัดการผู้ใช้นี้", expanded=False):
                action_columns = st.columns(2)
                action_index = 0
                for label, target_role in _role_actions_for(account, user):
                    column = action_columns[action_index % len(action_columns)]
                    action_index += 1
                    if column.button(
                        label,
                        key=f"set_role_{target_role}_{account.email}",
                        width="stretch",
                        type="primary" if target_role == "Partner" else "secondary",
                    ):
                        _apply_role_change(store, user, account, target_role)
                        return
                for label, action_name in _subscription_actions_for(account):
                    column = action_columns[action_index % len(action_columns)]
                    action_index += 1
                    if column.button(
                        label,
                        key=f"subscription_{action_name}_{account.email}",
                        width="stretch",
                    ):
                        try:
                            store.update_subscription(user.email, account.email, action_name)
                        except (PermissionError, KeyError, ValueError, SupabaseError) as error:
                            st.warning(str(error))
                            return
                        st.success(f"อัปเดตสถานะการใช้งานของ {account.full_name} แล้ว")
                        st.rerun()


def _render_user_management_legacy(store: SessionUserStore, user: AppUser) -> None:
    st.title("จัดการผู้ใช้")
    if user.role != "Admin":
        st.warning(UNAUTHORIZED_MESSAGE)
        return
    st.markdown(
        "<p class='section-lead'>กำหนดสิทธิ์สมาชิก ผู้นำ Partner และผู้ดูแลระบบ "
        "โดยผู้ดูแลระบบที่มีอยู่แล้ว</p>",
        unsafe_allow_html=True,
    )
    openai_config = load_openai_config(
        st.secrets,
        os.environ,
        default_responses_model=DEFAULT_OPENAI_MODEL,
        default_embedding_model=DEFAULT_EMBEDDING_MODEL,
    )
    _render_openai_diagnostic(get_openai_diagnostic_health(openai_config))
    for account in store.list_users():
        account = normalize_subscription_user(account)
        role_label = {
            "Member": "สมาชิก",
            "Leader": "ผู้นำ",
            "Partner": "Partner",
            "Admin": "ผู้ดูแลระบบ",
        }[account.role]
        with st.container(border=True):
            details, action = st.columns([3, 2])
            rate = 15 if account.role == "Partner" else 8 if account.role == "Leader" else 0
            details.markdown(
                f"**{account.full_name}**  \n{account.email}  \n"
                f"บทบาท: **{role_label}**  \nReferral Rate: **{rate}%**  \n"
                f"Subscription: **{account.subscription_status} / {account.subscription_plan}**  \n"
                f"หมดอายุ: **{account.subscription_expires_at[:10] or '-'}**  \n"
                f"อนุมัติโดย: **{account.approved_by or '-'}**  \n"
                f"อนุมัติเมื่อ: **{account.approved_at[:10] or '-'}**"
                f"  \nทดลองใช้ถึง: **{account.trial_ends_at[:10] or '-'}**"
            )
            for label, target_role in _role_actions_for(account, user):
                if action.button(
                    label,
                    key=f"set_role_{target_role}_{account.email}",
                    width="stretch",
                    type="primary" if target_role == "Partner" else "secondary",
                ):
                    _apply_role_change(store, user, account, target_role)
                    return
            for label, action_name in _subscription_actions_for(account):
                if action.button(
                    label,
                    key=f"subscription_{action_name}_{account.email}",
                    width="stretch",
                ):
                    try:
                        store.update_subscription(user.email, account.email, action_name)
                    except (PermissionError, KeyError, ValueError, SupabaseError) as error:
                        st.warning(str(error))
                        return
                    st.success(f"อัปเดตสถานะการใช้งานของ {account.full_name} แล้ว")
                    st.rerun()


def _role_label(role: str) -> str:
    return {
        "Member": "สมาชิก",
        "Leader": "ผู้นำ",
        "Partner": "Partner",
        "Admin": "ผู้ดูแลระบบ",
    }.get(role, role or "-")


def _referral_rate_for(account: AppUser) -> int:
    if account.role == "Partner":
        return 15
    if account.role == "Leader":
        return 8
    return 0


def _safe_date(value: str) -> str:
    return value[:10] if value else "-"


def _account_expiry_summary(account: AppUser) -> str:
    if account.subscription_status == "trialing":
        return f"ทดลองใช้ถึง: **{_safe_date(account.trial_ends_at)}**"
    return f"หมดอายุ: **{_safe_date(account.subscription_expires_at)}**"


def _user_management_summary(accounts: list[AppUser]) -> dict[str, int]:
    return {
        "total": len(accounts),
        "trialing": sum(1 for account in accounts if account.subscription_status == "trialing"),
        "active": sum(1 for account in accounts if account.subscription_status == "active"),
        "pending_payment": sum(1 for account in accounts if account.subscription_status == "pending_payment"),
        "partner": sum(1 for account in accounts if account.role == "Partner"),
        "leader": sum(1 for account in accounts if account.role == "Leader"),
        "suspended": sum(1 for account in accounts if account.subscription_status == "suspended"),
    }


def _filter_user_accounts(
    accounts: list[AppUser],
    *,
    search_query: str = "",
    role_filter: str = "ทั้งหมด",
    status_filter: str = "ทั้งหมด",
    plan_filter: str = "ทั้งหมด",
) -> list[AppUser]:
    query = search_query.strip().casefold()
    results: list[AppUser] = []
    for account in accounts:
        if query and query not in f"{account.full_name} {account.email}".casefold():
            continue
        if role_filter != "ทั้งหมด" and account.role != role_filter:
            continue
        if status_filter != "ทั้งหมด" and account.subscription_status != status_filter:
            continue
        if plan_filter != "ทั้งหมด" and account.subscription_plan != plan_filter:
            continue
        results.append(account)
    return results


def _paginate_user_accounts(
    accounts: list[AppUser],
    *,
    page: int,
    page_size: int = 20,
) -> tuple[list[AppUser], int, int, int, int]:
    safe_page_size = max(1, page_size)
    total_pages = max(1, (len(accounts) + safe_page_size - 1) // safe_page_size)
    current_page = min(max(1, page), total_pages)
    offset = (current_page - 1) * safe_page_size
    page_accounts = accounts[offset:offset + safe_page_size]
    if not accounts:
        return page_accounts, current_page, 0, 0, total_pages
    return page_accounts, current_page, offset + 1, offset + len(page_accounts), total_pages


# Test deployment marker: OpenAI diagnostic success-rate UI.
def _render_openai_diagnostic(health: dict[str, object]) -> None:
    st.subheader("สถานะระบบ OpenAI")
    success_rate = int(
        health.get("success_rate", health.get("response_success_rate", 0)) or 0
    )
    success_count = int(
        health.get("success_count", health.get("response_success_count", 0)) or 0
    )
    failure_count = int(
        health.get("failure_count", health.get("response_failure_count", 0)) or 0
    )
    request_count = int(
        health.get("total_requests", health.get("response_request_count", 0)) or 0
    )
    configured = "ใช่" if health.get("api_key_configured") else "ไม่ใช่"
    labels = (
        ("Success Rate (Last 100 Requests)", f"{success_rate}%"),
        ("Success", success_count),
        ("Failure", failure_count),
        ("Total Requests", request_count),
        ("ตั้งค่า API key แล้ว", configured),
        ("แหล่งการตั้งค่า", health.get("config_source") or "missing"),
        ("API key", health.get("masked_key") or "-"),
        ("Responses model", health.get("responses_model") or "-"),
        ("Embedding model", health.get("embedding_model") or "-"),
        ("ผลล่าสุด", health.get("last_result") or "ยังไม่มีข้อมูล"),
        ("การทำงานล่าสุด", health.get("last_operation") or "-"),
        ("ประเภทข้อผิดพลาดล่าสุด", health.get("last_error_type") or "-"),
        ("OpenAI error code", health.get("last_error_code") or "-"),
        ("OpenAI error type", health.get("last_error_api_type") or "-"),
        ("รายละเอียดแบบย่อ", health.get("last_error_message") or "-"),
        ("Request ID", health.get("last_request_id") or "-"),
        ("HTTP status ล่าสุด", health.get("last_status_code") or "-"),
        ("สำเร็จล่าสุด", health.get("last_success_time") or "-"),
        ("ล้มเหลวล่าสุด", health.get("last_failure_time") or "-"),
        ("จำนวน retry ล่าสุด", health.get("last_retry_count", 0)),
    )
    with st.container(border=True):
        for label, value in labels:
            st.write(f"{label}: **{value}**")


def _role_actions_for(
    account: AppUser,
    current_admin: AppUser,
) -> tuple[tuple[str, str], ...]:
    if account.role == "Member":
        return (
            ("เลื่อนเป็นผู้นำ", "Leader"),
            ("แต่งตั้งเป็น Partner", "Partner"),
            ("เลื่อนเป็นผู้ดูแลระบบ", "Admin"),
        )
    if account.role == "Leader":
        return (
            ("แต่งตั้งเป็น Partner", "Partner"),
            ("เลื่อนเป็นผู้ดูแลระบบ", "Admin"),
            ("ลดเป็นสมาชิก", "Member"),
        )
    if account.role == "Partner":
        return (
            ("ถอด Partner และปรับเป็นผู้นำ", "Leader"),
            ("ถอด Partner และปรับเป็นสมาชิก", "Member"),
        )
    if account.role == "Admin" and account.email != current_admin.email:
        return (
            ("ลดสิทธิ์เป็นผู้นำ", "Leader"),
            ("ลดสิทธิ์เป็นสมาชิก", "Member"),
        )
    return ()


def _subscription_actions_for(account: AppUser) -> tuple[tuple[str, str], ...]:
    if account.role == "Admin":
        return ()
    return (
        ("อนุมัติใช้งาน 30 วัน", "approve"),
        ("ต่ออายุ 30 วัน", "renew"),
        ("ระงับการใช้งาน", "suspend"),
        ("ตั้งเป็นรอชำระเงิน", "pending"),
    )


def _apply_role_change(
    store: SessionUserStore,
    actor: AppUser,
    account: AppUser,
    target_role: str,
) -> None:
    try:
        updated = store.set_role(actor.email, account.email, target_role)
    except (PermissionError, KeyError, ValueError, SupabaseError) as error:
        st.warning(str(error))
        return
    updated_label = {
        "Member": "สมาชิก",
        "Leader": "ผู้นำ",
        "Partner": "Partner",
        "Admin": "ผู้ดูแลระบบ",
    }[updated.role]
    st.success(f"ปรับบทบาทของ {updated.full_name} เป็น {updated_label} แล้ว")
    st.rerun()
