from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from config import APP_SUBTITLE, APP_TITLE, DEFAULT_EMBEDDING_MODEL, DEFAULT_OPENAI_MODEL, NAV_ITEMS
from services.coach_service import LocalCoachService
from services.auth_service import SessionUserStore
from services.knowledge_service import KnowledgeService
from services.openai_coach_service import OpenAICoachService
from services.profile_repository import SessionProfileRepository
from services.permissions import visible_navigation
from services.supabase_service import SupabaseService
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


def render_mobile_menu_toggle() -> None:
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const buttonId = "getexpert-mobile-menu-toggle";
        const styleId = "getexpert-mobile-menu-toggle-style";
        const sidebarOpenClass = "getexpert-mobile-sidebar-open";
        const desktopBreakpoint = "(min-width: 769px)";

        if (!doc.getElementById(styleId)) {
          const style = doc.createElement("style");
          style.id = styleId;
          style.textContent = `
            #${buttonId} {
              position: fixed;
              top: max(0.65rem, env(safe-area-inset-top));
              left: max(0.65rem, env(safe-area-inset-left));
              z-index: 2147483000;
              display: none;
              align-items: center;
              gap: 0.35rem;
              min-height: 2.45rem;
              padding: 0.48rem 0.78rem;
              border: 2px solid #1D4E89;
              border-radius: 999px;
              background: #FFFFFF;
              color: #0B2E59;
              font: 800 0.95rem/1.1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              box-shadow: 0 8px 22px rgba(11, 46, 89, 0.20);
              cursor: pointer;
            }
            #${buttonId}:focus-visible {
              outline: 3px solid #F4C95D;
              outline-offset: 2px;
            }
            @media (max-width: 768px) {
              #${buttonId} { display: inline-flex; }
              .block-container { padding-top: 4.35rem !important; }
              body.${sidebarOpenClass} [data-testid="stSidebar"] {
                transform: translateX(0) !important;
                visibility: visible !important;
                opacity: 1 !important;
                min-width: min(82vw, 20rem) !important;
                width: min(82vw, 20rem) !important;
                max-width: min(82vw, 20rem) !important;
                left: 0 !important;
                z-index: 2147482999 !important;
                box-shadow: 0 18px 40px rgba(11, 46, 89, 0.34) !important;
              }
              body.${sidebarOpenClass} [data-testid="stSidebar"] > div {
                transform: translateX(0) !important;
                visibility: visible !important;
                opacity: 1 !important;
                width: 100% !important;
              }
            }
            @media (min-width: 769px) {
              #${buttonId} {
                display: inline-flex !important;
                top: 0.75rem;
                left: 0.75rem;
                min-height: 2.25rem;
                padding: 0.42rem 0.72rem;
                border-color: #D7DEE8;
                box-shadow: 0 7px 18px rgba(11, 46, 89, 0.16);
              }
              body.${sidebarOpenClass} [data-testid="stSidebar"] {
                transform: translateX(0) !important;
                visibility: visible !important;
                opacity: 1 !important;
                min-width: 20rem !important;
                width: 20rem !important;
                max-width: 20rem !important;
                left: 0 !important;
                z-index: 2147482999 !important;
                box-shadow: 0 18px 40px rgba(11, 46, 89, 0.30) !important;
              }
              body.${sidebarOpenClass} [data-testid="stSidebar"] > div {
                transform: translateX(0) !important;
                visibility: visible !important;
                opacity: 1 !important;
                width: 100% !important;
              }
            }
          `;
          doc.head.appendChild(style);
        }

        let button = doc.getElementById(buttonId);
        if (!button) {
          button = doc.createElement("button");
          button.id = buttonId;
          button.type = "button";
          button.textContent = "☰ เมนู";
          button.setAttribute("aria-label", "เปิดเมนูหลัก");
          button.setAttribute("data-getexpert-menu-toggle", "true");
          doc.body.appendChild(button);
        }

        const isDesktop = () => window.parent.matchMedia(desktopBreakpoint).matches;

        button.onclick = () => {
          const sidebar = doc.querySelector('[data-testid="stSidebar"]');
          const isOpen = sidebar && sidebar.getBoundingClientRect().width > 10;

          if (isDesktop() && doc.body.classList.contains(sidebarOpenClass)) {
            doc.body.classList.remove(sidebarOpenClass);
            return;
          }

          if (isDesktop() && isOpen) {
            const collapseButton = doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
            if (collapseButton && typeof collapseButton.click === "function") {
              collapseButton.click();
            } else {
              doc.body.classList.remove(sidebarOpenClass);
            }
            return;
          }

          if (!isDesktop() && isOpen) return;

          doc.body.classList.add(sidebarOpenClass);

          const openButton =
            doc.querySelector('[data-testid="stSidebarCollapsedControl"] button') ||
            doc.querySelector('[data-testid="stSidebarCollapsedControl"]') ||
            doc.querySelector('[data-testid="stExpandSidebarButton"] button') ||
            doc.querySelector('[data-testid="stExpandSidebarButton"]') ||
            doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
          if (openButton && typeof openButton.click === "function") {
            openButton.click();
          }
        };

        if (!window.parent.__getExpertMobileMenuListenerAttached) {
          window.parent.__getExpertMobileMenuListenerAttached = true;
          doc.addEventListener("click", (event) => {
            const target = event.target;
            if (!target || !target.closest) return;
            const clickedNavigation =
              target.closest('[data-testid="stSidebar"] [role="radiogroup"] label') ||
              target.closest('[data-testid="stSidebar"] input[type="radio"]');
            if (clickedNavigation) {
              window.setTimeout(() => doc.body.classList.remove(sidebarOpenClass), 220);
            }
          }, true);
        }
        </script>
        """,
        height=0,
        width=0,
    )


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
    render_mobile_menu_toggle()
    if auth_page == "เข้าสู่ระบบ":
        render_login(user_store)
    else:
        render_register(user_store)
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
    previous_page = st.session_state.get("_previous_main_navigation")
    should_collapse_sidebar = bool(previous_page and previous_page != page)
    st.session_state["_previous_main_navigation"] = page
    st.markdown("<div class='sidebar-spacer'></div>", unsafe_allow_html=True)

render_mobile_menu_toggle()

if should_collapse_sidebar:
    components.html(
        """
        <script>
        const collapseSidebarOnMobile = () => {
          if (!window.matchMedia("(max-width: 768px)").matches) return;
          const doc = window.parent.document;
          const sidebar = doc.querySelector('[data-testid="stSidebar"]');
          const collapseButton = doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
          if (sidebar && collapseButton && sidebar.getBoundingClientRect().width > 0) {
            collapseButton.click();
          }
        };
        window.setTimeout(collapseSidebarOnMobile, 120);
        </script>
        """,
        height=0,
        width=0,
    )

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
