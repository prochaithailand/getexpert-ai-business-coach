from __future__ import annotations

import streamlit as st

from models import AppUser
from services.auth_service import SessionUserStore
from services.permissions import UNAUTHORIZED_MESSAGE
from services.supabase_service import SupabaseError


def render_login(store: SessionUserStore) -> None:
    st.title("เข้าสู่ระบบ")
    st.markdown("<p class='section-lead'>เข้าสู่ระบบเพื่อใช้งานระบบพัฒนาธุรกิจ GetExpert</p>", unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("อีเมล", placeholder="name@example.com")
        password = st.text_input("รหัสผ่าน", type="password")
        submitted = st.form_submit_button("เข้าสู่ระบบ", type="primary", width="stretch")
    if submitted:
        try:
            user = store.authenticate(email, password)
        except SupabaseError as error:
            st.error(f"ไม่สามารถเข้าสู่ระบบผ่าน Supabase ได้: {error}")
            return
        if user:
            st.success(f"เข้าสู่ระบบสำเร็จ ยินดีต้อนรับคุณ{user.full_name}")
            st.rerun()
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
    if submitted:
        try:
            store.register(email, password, full_name)
        except (ValueError, SupabaseError) as error:
            st.warning(str(error))
            return
        st.success("สมัครสมาชิกสำเร็จ กรุณาเข้าสู่ระบบ")


def render_logout(store: SessionUserStore, user: AppUser) -> None:
    st.title("ออกจากระบบ")
    st.info(f"คุณกำลังใช้งานในชื่อ {user.full_name}")
    if st.button("ยืนยันออกจากระบบ", type="primary", width="stretch"):
        store.logout()
        st.rerun()


def render_user_management(store: SessionUserStore, user: AppUser) -> None:
    st.title("จัดการผู้ใช้")
    if user.role != "Admin":
        st.warning(UNAUTHORIZED_MESSAGE)
        return
    st.markdown("<p class='section-lead'>กำหนดสิทธิ์ผู้นำและผู้ดูแลระบบโดยผู้ดูแลระบบที่มีอยู่แล้ว</p>", unsafe_allow_html=True)
    for account in store.list_users():
        role_label = {
            "Member": "สมาชิก",
            "Leader": "ผู้นำ",
            "Partner": "Partner",
            "Admin": "ผู้ดูแลระบบ",
        }[account.role]
        with st.container(border=True):
            details, action = st.columns([3, 2])
            rate = 15 if account.role == "Partner" else 8 if account.role == "Leader" else 0
            badge = f"  \nReferral Rate: **{rate}%**" if rate else ""
            details.markdown(
                f"**{account.full_name}**  \n{account.email}  \nบทบาท: **{role_label}**{badge}"
            )
            role_options = ("Member", "Leader", "Partner", "Admin")
            selected_role = action.selectbox(
                "กำหนดบทบาท",
                role_options,
                index=role_options.index(account.role),
                key=f"role_select_{account.email}",
            )
            if action.button(
                "บันทึกบทบาท",
                key=f"set_role_{account.email}",
                width="stretch",
                disabled=selected_role == account.role,
            ):
                try:
                    updated = store.set_role(user.email, account.email, selected_role)
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
