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


def render_login(store: SessionUserStore) -> None:
    st.title("เข้าสู่ระบบ")
    st.markdown("<p class='section-lead'>เข้าสู่ระบบเพื่อใช้งานระบบพัฒนาธุรกิจ GetExpert</p>", unsafe_allow_html=True)
    login_in_progress = bool(st.session_state.get("login_in_progress", False))
    if login_in_progress:
        st.info("กำลังเข้าสู่ระบบ กรุณารอสักครู่...")
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
        st.info("กำลังเข้าสู่ระบบ กรุณารอสักครู่...")
        try:
            user = store.authenticate(email, password)
        except SupabaseError as error:
            st.session_state["login_in_progress"] = False
            st.error(f"ไม่สามารถเข้าสู่ระบบผ่าน Supabase ได้: {error}")
            return
        except Exception:
            st.session_state["login_in_progress"] = False
            raise
        if user:
            st.session_state["login_in_progress"] = False
            st.success(f"เข้าสู่ระบบสำเร็จ ยินดีต้อนรับคุณ{user.full_name}")
            st.rerun()
        st.session_state["login_in_progress"] = False
        st.error("อีเมลหรือรหัสผ่านไม่ถูกต้อง")


def render_register(store: SessionUserStore) -> None:
    st.title("สมัครสมาชิก")
    st.markdown("<p class='section-lead'>สร้างบัญชีใหม่เพื่อเริ่มต้นใช้งานระบบ บัญชีใหม่จะเป็นสมาชิกโดยอัตโนมัติ</p>", unsafe_allow_html=True)
    with st.form("register_form"):
        full_name = st.text_input("ชื่อ-นามสกุล", placeholder="ชื่อและนามสกุลของคุณ")
        email = st.text_input("อีเมล", placeholder="name@example.com")
        password = st.text_input("รหัสผ่าน", type="password", help="อย่างน้อย 8 ตัวอักษร")
        st.text_input("บทบาท", value="สมาชิก", disabled=True)
        submitted = st.form_submit_button("สมัครสมาชิก", type="primary", width="stretch")
        st.caption(
            "เมื่อสมัครใช้งาน GetExpert คุณยินยอมให้ระบบส่งอีเมลที่เกี่ยวข้องกับบัญชีของคุณ "
            "เช่น การยืนยันการสมัคร การแจ้งสถานะทดลองใช้ฟรี การชำระเงิน และการเปิดใช้งานบริการ"
        )
        marketing_email_opt_in = st.checkbox(
            "ฉันต้องการรับบทความ เทคนิคการใช้ AI เพื่อพัฒนาธุรกิจ ข่าวสาร "
            "และข้อเสนอจาก GetExpert ทางอีเมล",
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
    st.title("ตั้งรหัสผ่านใหม่")
    st.markdown(
        "<p class='section-lead'>กำหนดรหัสผ่านใหม่สำหรับบัญชี GetExpert ของคุณ</p>",
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
