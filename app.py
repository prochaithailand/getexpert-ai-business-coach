from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import streamlit as st
import httpx

from config import APP_SUBTITLE, APP_TITLE, DEFAULT_EMBEDDING_MODEL, DEFAULT_OPENAI_MODEL, NAV_ITEMS
from services.coach_service import LocalCoachService
from services.auth_service import SessionUserStore
from services.knowledge_service import KnowledgeService
from services.openai_coach_service import OpenAICoachService
from services.profile_repository import SessionProfileRepository
from services.permissions import visible_navigation
from services.supabase_service import SupabaseError, SupabaseService
from services.settings_service import load_supabase_config
from ui.styles import apply_global_styles
from views.pages import (
    render_action_plan,
    render_ai_coach,
    render_content_creator,
    render_home,
    render_knowledge_base,
    render_member_profile,
)
from views.workplan_page import render_business_workplan
from views.dashboard_page import render_member_dashboard
from views.prospect_page import render_prospect_manager
from views.team_page import render_team_management
from views.team_dashboard_page import render_team_dashboard
from views.auth_pages import render_login, render_logout, render_register, render_user_management


st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


@st.cache_resource
def get_coach_service() -> LocalCoachService:
    """สร้างบริการโค้ชและเชื่อมต่อคลังความรู้ของระบบ"""
    knowledge_dir = Path(__file__).resolve().parent / "knowledge"
    api_key = get_setting("OPENAI_API_KEY")
    model = get_setting("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    embedding_model = get_setting("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    if api_key:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        knowledge_service = KnowledgeService(
            knowledge_dir,
            embedding_client=client,
            embedding_model=embedding_model,
        )
        return OpenAICoachService(knowledge_service, model=model, client=client)
    knowledge_service = KnowledgeService(knowledge_dir)
    return LocalCoachService(knowledge_service)


supabase_config = load_supabase_config(st.secrets, os.environ)
supabase = (
    SupabaseService(supabase_config.url, supabase_config.anon_key)
    if supabase_config.is_complete
    else None
)
if supabase:
    st.session_state["_supabase_service"] = supabase
user_store = SessionUserStore(st.session_state, supabase)
bootstrap_email = get_setting("PROTOTYPE_ADMIN_EMAIL")
bootstrap_password = get_setting("PROTOTYPE_ADMIN_PASSWORD")
if not supabase and bootstrap_email and bootstrap_password:
    user_store.create_admin_internally(
        bootstrap_email,
        bootstrap_password,
        get_setting("PROTOTYPE_ADMIN_NAME", "ผู้ดูแลระบบ GetExpert"),
    )
authenticated_user = user_store.current_user()

if authenticated_user is None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="brand-block">
                <div class="brand-mark">GE</div>
                <div>
                    <div class="brand-name">{APP_TITLE}</div>
                    <div class="brand-tagline">{APP_SUBTITLE}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        auth_page = st.radio("เมนูบัญชี", ("เข้าสู่ระบบ", "สมัครสมาชิก"), label_visibility="collapsed")
        st.caption(supabase_config.safe_debug_message)
    if auth_page == "เข้าสู่ระบบ":
        render_login(user_store)
    else:
        render_register(user_store)
    if supabase:
        try:
            missing_tables = supabase.verify_schema()
        except (SupabaseError, httpx.HTTPError) as error:
            st.warning(f"ไม่สามารถตรวจสอบโครงสร้าง Supabase ได้: {error}")
        else:
            if missing_tables:
                st.warning("ยังไม่ได้ติดตั้งตาราง Supabase กรุณารันไฟล์ migration ในโฟลเดอร์ supabase/migrations")
    else:
        st.info("ยังไม่ได้ตั้งค่า SUPABASE_URL และ SUPABASE_ANON_KEY ระบบจึงใช้หน่วยความจำชั่วคราว")
    st.stop()

repository = SessionProfileRepository(st.session_state)
profile = repository.get()
if profile and profile.role != authenticated_user.role:
    repository.save(replace(profile, role=authenticated_user.role))
    profile = repository.get()
coach = get_coach_service()

with st.sidebar:
    st.markdown(
        f"""
        <div class="brand-block">
            <div class="brand-mark">GE</div>
            <div>
                <div class="brand-name">{APP_TITLE}</div>
                <div class="brand-tagline">{APP_SUBTITLE}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    navigation_items = visible_navigation(NAV_ITEMS, authenticated_user)
    if st.session_state.get("main_navigation") not in navigation_items:
        st.session_state["main_navigation"] = navigation_items[0]
    page = st.radio(
        "เมนูหลัก",
        navigation_items,
        label_visibility="collapsed",
        key="main_navigation",
    )
    st.caption(supabase_config.safe_debug_message)
    st.markdown("<div class='sidebar-spacer'></div>", unsafe_allow_html=True)
    if profile and profile.is_complete:
        st.success(f"โปรไฟล์พร้อมใช้งาน: {profile.name}")
    else:
        st.info(f"เข้าสู่ระบบในชื่อ {authenticated_user.full_name} กรุณากรอกโปรไฟล์สมาชิก")
    if sync_error := st.session_state.get("supabase_sync_error"):
        st.warning(sync_error)

if page == "หน้าแรก":
    render_home(profile)
elif page == "โปรไฟล์สมาชิก":
    render_member_profile(repository)
elif page == "จัดการทีม":
    render_team_management(repository.get(), authenticated_user, user_store)
elif page == "จัดการผู้ใช้":
    render_user_management(user_store, authenticated_user)
elif page == "Team Dashboard":
    render_team_dashboard(repository.get(), coach, authenticated_user)
elif page == "Dashboard สมาชิก":
    render_member_dashboard(repository.get(), coach)
elif page == "แผนปฏิบัติการ 30 วัน":
    render_action_plan(repository.get(), coach)
elif page == "เครื่องมือสร้างคอนเทนต์":
    render_content_creator(repository.get(), coach)
elif page == "ผู้มุ่งหวัง":
    render_prospect_manager(repository.get())
elif page == "Workplan ธุรกิจ":
    render_business_workplan(repository.get())
elif page == "คลังความรู้":
    render_knowledge_base()
elif page == "ออกจากระบบ":
    render_logout(user_store, authenticated_user)
else:
    render_ai_coach(repository.get(), coach)
