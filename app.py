from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from config import (
    APP_SUBTITLE,
    APP_TITLE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_PASSWORD_RESET_REDIRECT_URL,
    NAV_ITEMS,
)
from services.coach_service import LocalCoachService
from services.auth_service import SessionUserStore, recovery_params_from_query
from services.knowledge_service import KnowledgeService
from services.openai_coach_service import OpenAICoachService
from services.profile_repository import SessionProfileRepository
from services.permissions import visible_navigation
from services.subscription_service import LOCKED_MESSAGE, has_active_subscription
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
from views.team_dashboard_page import render_team_dashboard, render_team_invite_confirmation
from views.auth_pages import (
    render_account_settings,
    render_forgot_password,
    render_login,
    render_logout,
    render_register,
    render_reset_password,
    render_user_management,
)
from views.payment_page import render_payment_page


st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()


def capture_supabase_recovery_redirect() -> None:
    components.html(
        """
        <script>
        const parentWindow = window.parent;
        const hash = parentWindow.location.hash;
        if (hash && hash.length > 1) {
          const values = new URLSearchParams(hash.slice(1));
          const type = values.get("type");
          const accessToken = values.get("access_token");
          const errorDescription = values.get("error_description");
          if (type === "recovery" && accessToken) {
            const url = new URL(parentWindow.location.href);
            url.hash = "";
            url.searchParams.set("type", "recovery");
            url.searchParams.set("access_token", accessToken);
            parentWindow.history.replaceState({}, "", url.toString());
            parentWindow.location.reload();
          } else if (errorDescription) {
            const url = new URL(parentWindow.location.href);
            url.hash = "";
            url.searchParams.set("recovery_error", errorDescription);
            parentWindow.history.replaceState({}, "", url.toString());
            parentWindow.location.reload();
          }
        }
        </script>
        """,
        height=0,
        width=0,
    )


capture_supabase_recovery_redirect()


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
        const legacyButtonIds = ["getexpert-mobile-menu-toggle", "getexpert-mobile-menu-toggle-v2", "getexpert-mobile-menu-toggle-v3"];
        const legacyCloseButtonIds = ["getexpert-mobile-sidebar-close", "getexpert-mobile-sidebar-close-v2", "getexpert-mobile-sidebar-close-v3"];
        const buttonId = "getexpert-mobile-menu-toggle-v4";
        const closeButtonId = "getexpert-mobile-sidebar-close-v4";
        const styleId = "getexpert-mobile-menu-toggle-style-v4";
        const sidebarOpenClass = "getexpert-mobile-sidebar-open";
        const sidebarClosedClass = "getexpert-mobile-sidebar-closed";
        const desktopBreakpoint = "(min-width: 769px)";

        [...legacyButtonIds, ...legacyCloseButtonIds, buttonId, closeButtonId].forEach((legacyId) => {
          const legacyElement = doc.getElementById(legacyId);
          if (legacyElement) legacyElement.remove();
        });

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
            #${closeButtonId} {
              position: fixed;
              top: max(0.65rem, env(safe-area-inset-top));
              left: min(72vw, 17rem);
              z-index: 2147483001;
              display: none;
              align-items: center;
              justify-content: center;
              min-width: 2.5rem;
              min-height: 2.45rem;
              padding: 0.45rem 0.65rem;
              border: 2px solid #FFFFFF;
              border-radius: 999px;
              background: #0B2E59;
              color: #FFFFFF;
              font: 900 1rem/1 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
              box-shadow: 0 8px 22px rgba(11, 46, 89, 0.28);
              cursor: pointer;
            }
            #${closeButtonId}:focus-visible {
              outline: 3px solid #F4C95D;
              outline-offset: 2px;
            }
            @media (max-width: 768px) {
              #${buttonId} { display: inline-flex; }
              #${closeButtonId} { display: inline-flex; }
              body.${sidebarClosedClass} #${closeButtonId} { display: none !important; }
              .block-container { padding-top: 4.35rem !important; }
              body.${sidebarClosedClass} [data-testid="stSidebar"] {
                transform: translateX(-100%) !important;
                visibility: hidden !important;
                opacity: 0 !important;
                min-width: 0 !important;
                width: 0 !important;
                max-width: 0 !important;
                left: -100vw !important;
                box-shadow: none !important;
              }
              body.${sidebarClosedClass} [data-testid="stSidebar"] > div {
                transform: translateX(-100%) !important;
                visibility: hidden !important;
                opacity: 0 !important;
                width: 0 !important;
              }
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
              #${closeButtonId} { display: none !important; }
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

        let button = doc.createElement("button");
        button.id = buttonId;
        button.type = "button";
        button.textContent = "☰ เมนู";
        button.setAttribute("aria-label", "เปิดเมนูหลัก");
        button.setAttribute("data-getexpert-menu-toggle", "true");
        doc.body.appendChild(button);

        let closeButton = doc.createElement("button");
        closeButton.id = closeButtonId;
        closeButton.type = "button";
        closeButton.textContent = "<<";
        closeButton.setAttribute("aria-label", "ปิดเมนูหลัก");
        closeButton.setAttribute("data-getexpert-menu-close", "true");
        doc.body.appendChild(closeButton);

        const isDesktop = () => window.parent.matchMedia(desktopBreakpoint).matches;

        const closeMobileSidebar = () => {
          doc.body.classList.remove(sidebarOpenClass);
          doc.body.classList.add(sidebarClosedClass);
        };

        const syncMobileSidebarState = () => {
          if (isDesktop()) {
            doc.body.classList.remove(sidebarClosedClass);
            return;
          }
          const sidebar = doc.querySelector('[data-testid="stSidebar"]');
          if (!sidebar) return;
          const rect = sidebar.getBoundingClientRect();
          if (rect.width <= 10 || rect.x < -10) {
            doc.body.classList.add(sidebarClosedClass);
          }
        };

        const toggleSidebarFromMenu = () => {
          const sidebar = doc.querySelector('[data-testid="stSidebar"]');
          const isOpen = sidebar && sidebar.getBoundingClientRect().width > 10;

          if (isDesktop() && doc.body.classList.contains(sidebarOpenClass)) {
            doc.body.classList.remove(sidebarOpenClass);
            doc.body.classList.remove(sidebarClosedClass);
            return;
          }

          if (isDesktop() && isOpen) {
            const collapseButton = doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
            if (collapseButton && typeof collapseButton.click === "function") {
              collapseButton.click();
            } else {
              doc.body.classList.remove(sidebarOpenClass);
            }
            doc.body.classList.remove(sidebarClosedClass);
            return;
          }

          if (!isDesktop() && isOpen && !doc.body.classList.contains(sidebarClosedClass)) return;

          doc.body.classList.remove(sidebarClosedClass);
          doc.body.classList.add(sidebarOpenClass);

          const openButton =
            doc.querySelector('[data-testid="stSidebarCollapsedControl"] button') ||
            doc.querySelector('[data-testid="stSidebarCollapsedControl"]') ||
            doc.querySelector('[data-testid="stExpandSidebarButton"] button') ||
            doc.querySelector('[data-testid="stExpandSidebarButton"]');
          if (openButton && typeof openButton.click === "function") {
            openButton.click();
          }
        };

        button.addEventListener("click", (event) => {
          event.preventDefault();
          if (event.stopImmediatePropagation) event.stopImmediatePropagation();
          event.stopPropagation();
          toggleSidebarFromMenu();
        });
        button.setAttribute(
          "onclick",
          `event.preventDefault(); event.stopPropagation(); (function(){
            const openClass = "${sidebarOpenClass}";
            const closedClass = "${sidebarClosedClass}";
            const isDesktop = window.matchMedia("${desktopBreakpoint}").matches;
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            const isOpen = sidebar && sidebar.getBoundingClientRect().width > 10;
            if (isDesktop && document.body.classList.contains(openClass)) {
              document.body.classList.remove(openClass);
              document.body.classList.remove(closedClass);
              return;
            }
            if (isDesktop && isOpen) {
              const collapseButton = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
              if (collapseButton && typeof collapseButton.click === "function") collapseButton.click();
              document.body.classList.remove(closedClass);
              return;
            }
            if (!isDesktop && isOpen && !document.body.classList.contains(closedClass)) return;
            document.body.classList.remove(closedClass);
            document.body.classList.add(openClass);
            const openButton =
              document.querySelector('[data-testid="stSidebarCollapsedControl"] button') ||
              document.querySelector('[data-testid="stSidebarCollapsedControl"]') ||
              document.querySelector('[data-testid="stExpandSidebarButton"] button') ||
              document.querySelector('[data-testid="stExpandSidebarButton"]');
            if (openButton && typeof openButton.click === "function") window.setTimeout(() => openButton.click(), 50);
          })();`
        );
        closeButton.onclick = (event) => {
          event.preventDefault();
          if (event.stopImmediatePropagation) event.stopImmediatePropagation();
          event.stopPropagation();
          closeMobileSidebar();
        };
        closeButton.addEventListener("click", (event) => {
          event.preventDefault();
          if (event.stopImmediatePropagation) event.stopImmediatePropagation();
          event.stopPropagation();
          closeMobileSidebar();
        });
        closeButton.setAttribute(
          "onclick",
          `event.preventDefault(); event.stopPropagation(); document.body.classList.remove("${sidebarOpenClass}"); document.body.classList.add("${sidebarClosedClass}");`
        );

        if (!window.parent.__getExpertMobileMenuListenerAttached) {
          window.parent.__getExpertMobileMenuListenerAttached = true;
          doc.addEventListener("click", (event) => {
            const target = event.target;
            if (!target || !target.closest) return;
            const clickedMenu = target.closest(`#${buttonId}`);
            if (clickedMenu) {
              event.preventDefault();
              if (event.stopImmediatePropagation) event.stopImmediatePropagation();
              event.stopPropagation();
              toggleSidebarFromMenu();
              return;
            }

            const clickedClose = target.closest(`#${closeButtonId}`);
            if (!isDesktop() && clickedClose) {
              event.preventDefault();
              if (event.stopImmediatePropagation) event.stopImmediatePropagation();
              event.stopPropagation();
              closeMobileSidebar();
              return;
            }

            const clickedCollapse =
              target.closest('[data-testid="stSidebarCollapseButton"] button') ||
              target.closest('[data-testid="stSidebarCollapseButton"]');
            if (!isDesktop() && clickedCollapse) {
              event.preventDefault();
              event.stopPropagation();
              closeMobileSidebar();
              return;
            }

            const clickedNavigation =
              target.closest('[data-testid="stSidebar"] [role="radiogroup"] label') ||
              target.closest('[data-testid="stSidebar"] input[type="radio"]');
            if (clickedNavigation) {
              window.setTimeout(() => {
                doc.body.classList.remove(sidebarOpenClass);
                if (!isDesktop()) {
                  doc.body.classList.add(sidebarClosedClass);
                }
              }, 220);
            }
          }, true);
        }
        window.setTimeout(syncMobileSidebarState, 250);
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
invite_code = str(st.query_params.get("invite_code", "")).strip()
if invite_code:
    st.session_state["pending_invite_code"] = invite_code
recovery_type, recovery_access_token = recovery_params_from_query(st.query_params)
if recovery_type == "recovery" and recovery_access_token:
    st.session_state["password_recovery_access_token"] = recovery_access_token
    st.query_params.pop("type", None)
    st.query_params.pop("access_token", None)
    st.query_params.pop("refresh_token", None)
    st.query_params.pop("recovery_type", None)
    st.query_params.pop("recovery_access_token", None)
recovery_error = str(st.query_params.get("recovery_error", "")).strip()
if recovery_error:
    st.session_state["password_recovery_error"] = recovery_error
    st.query_params.pop("recovery_error", None)

pending_recovery_token = str(
    st.session_state.get("password_recovery_access_token", "")
).strip()
if pending_recovery_token:
    render_mobile_menu_toggle()
    render_reset_password(user_store, pending_recovery_token)
    st.stop()

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
        auth_page = st.radio(
            "เมนูบัญชี",
            ("เข้าสู่ระบบ", "สมัครสมาชิก", "ลืมรหัสผ่าน"),
            label_visibility="collapsed",
        )
    render_mobile_menu_toggle()
    if recovery_message := st.session_state.pop("password_recovery_error", None):
        st.error("ลิงก์รีเซ็ตรหัสผ่านไม่ถูกต้องหรือหมดอายุ กรุณาขอลิงก์ใหม่")
    if st.session_state.pop("password_reset_completed", False):
        st.success(
            "ตั้งรหัสผ่านใหม่เรียบร้อยแล้ว กรุณาเข้าสู่ระบบด้วยรหัสผ่านใหม่"
        )
    if st.session_state.get("pending_invite_code"):
        st.info("กรุณาเข้าสู่ระบบหรือสมัครสมาชิกก่อนยืนยันคำเชิญเข้าร่วมทีม")
    if auth_page == "เข้าสู่ระบบ":
        render_login(user_store)
    elif auth_page == "สมัครสมาชิก":
        render_register(user_store)
    else:
        render_forgot_password(
            user_store,
            get_setting(
                "PASSWORD_RESET_REDIRECT_URL",
                DEFAULT_PASSWORD_RESET_REDIRECT_URL,
            ),
        )
    st.stop()

repository = SessionProfileRepository(st.session_state)
profile = repository.get()
if profile and profile.role != authenticated_user.role:
    repository.save(replace(profile, role=authenticated_user.role))
    profile = repository.get()
coach = get_coach_service()
pending_invite_code = str(st.session_state.get("pending_invite_code", "")).strip()
if pending_invite_code:
    render_team_invite_confirmation(authenticated_user, pending_invite_code)

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
        st.session_state["main_navigation"] = (
            "ชำระเงิน / เปิดใช้งาน"
            if (
                not has_active_subscription(authenticated_user)
                and "ชำระเงิน / เปิดใช้งาน" in navigation_items
            )
            else navigation_items[0]
        )
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

if not has_active_subscription(authenticated_user):
    if page != "ชำระเงิน / เปิดใช้งาน":
        st.warning(LOCKED_MESSAGE)

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
elif page == "ชำระเงิน / เปิดใช้งาน":
    render_payment_page(authenticated_user)
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
    render_prospect_manager(repository.get(), authenticated_user)
elif page == "Workplan ธุรกิจ":
    render_business_workplan(repository.get())
elif page == "คลังความรู้":
    render_knowledge_base()
elif page == "ตั้งค่าบัญชี":
    render_account_settings(user_store, authenticated_user)
elif page == "ออกจากระบบ":
    render_logout(user_store, authenticated_user)
else:
    render_ai_coach(repository.get(), coach)
