from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from config import EXPERIENCE_LEVELS
from models import ActionItem, MemberProfile
from services.coach_service import CoachService
from services.dashboard_service import record_member_usage
from services.knowledge_service import KnowledgeService
from services.member_activity_service import build_member_activity_context
from services.onboarding_service import build_onboarding_status
from services.profile_repository import ProfileRepository
from services.progress_service import calculate_plan_progress, member_progress_key
from services.supabase_service import get_authenticated_supabase_user, get_supabase_service, run_supabase_sync
from translations import translate
from ui.ai_coaching_pipeline import render_ai_coaching_pipeline


def _active_brand() -> dict[str, str]:
    return st.session_state.get("_active_brand", {})


def _language() -> str:
    return str(st.session_state.get("language", "th"))


def _t(key: str, **values: object) -> str:
    text = translate(key, _language())
    return text.format(**values) if values else text


def _page_header(title: str, description: str) -> None:
    st.title(title)
    st.markdown(f"<p class='section-lead'>{description}</p>", unsafe_allow_html=True)


def _require_profile(profile: MemberProfile | None) -> bool:
    if profile and profile.is_complete:
        return True
    st.warning(_t("Profile Required Warning"))
    return False


def _profile_signature(profile: MemberProfile) -> tuple[object, ...]:
    return (
        profile.name,
        profile.age,
        profile.occupation,
        profile.daily_available_time,
        profile.income_goal,
        profile.online_marketing_experience,
        profile.team_name,
        profile.team_id,
        profile.team_leader,
        profile.sponsor,
        profile.role,
    )


def _update_day_completion(member_key: str, day: int, widget_key: str) -> None:
    store = dict(st.session_state.get("plan_completion_by_member", {}))
    member_statuses = dict(store.get(member_key, {}))
    member_statuses[str(day)] = bool(st.session_state.get(widget_key, False))
    store[member_key] = member_statuses
    st.session_state.plan_completion_by_member = store
    supabase = get_supabase_service(st.session_state)
    authenticated = get_authenticated_supabase_user(st.session_state)
    if supabase and authenticated:
        run_supabase_sync(st.session_state, supabase.save_progress, authenticated, member_statuses)


def _navigate_to(page: str) -> None:
    st.session_state["main_navigation"] = page


def _render_getting_started(profile: MemberProfile | None) -> None:
    brand = _active_brand()
    short_name = brand.get("short_name", "GetExpert")
    statuses = build_onboarding_status(st.session_state, profile)
    steps = (
        (
            "profile", _t("Onboarding Step Profile Title"),
            _t("Onboarding Step Profile Description"),
            _t("Onboarding CTA Profile"), "โปรไฟล์สมาชิก",
        ),
        (
            "action_plan", _t("Onboarding Step Plan Title"),
            _t("Onboarding Step Plan Description"),
            _t("Onboarding CTA Plan"), "แผนปฏิบัติการ 30 วัน",
        ),
        (
            "workplan", _t("Onboarding Step Workplan Title"),
            _t("Onboarding Step Workplan Description"),
            _t("Onboarding CTA Workplan"), "Workplan ธุรกิจ",
        ),
        (
            "ai_coach", _t("Onboarding Step AI Title"),
            _t("Onboarding Step AI Description"),
            _t("Onboarding CTA AI"), "โค้ช AI",
        ),
        (
            "dashboard", _t("Onboarding Step Dashboard Title"),
            _t("Onboarding Step Dashboard Description"),
            _t("Onboarding CTA Dashboard"), "Dashboard สมาชิก",
        ),
    )
    completed = sum(statuses.values())
    with st.container(key="onboarding_sticky_summary"):
        st.markdown(
            "<div class='onboarding-title'>"
            f"<span class='onboarding-title-desktop'>{_t('Onboarding Title', short_name=short_name)}</span>"
            f"<span class='onboarding-title-mobile'>{_t('Onboarding Title Mobile')}</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.progress(completed / len(steps), text=_t("Onboarding Progress", completed=completed))

    with st.container(border=True, key="onboarding_steps_card"):
        columns = st.columns(5)
        for column, (key, title, description, button_label, destination) in zip(columns, steps):
            marker = "✓" if statuses[key] else "○"
            status_class = "is-complete" if statuses[key] else "is-pending"
            column.markdown(
                f"<div class='onboarding-step {status_class}'>"
                f"<div class='onboarding-step-title'><span>{marker}</span> {title}</div>"
                f"<p>{description}</p></div>",
                unsafe_allow_html=True,
            )
            column.button(
                button_label,
                key=f"onboarding_{key}",
                on_click=_navigate_to,
                args=(destination,),
                use_container_width=True,
            )


def render_home(profile: MemberProfile | None) -> None:
    brand = _active_brand()
    short_name = brand.get("short_name", "GetExpert")
    hero_title = brand.get("hero_title", "GetExpert โค้ชธุรกิจ AI")
    powered_by = brand.get("powered_by", "")
    _render_getting_started(profile)
    st.write("")
    greeting = (
        _t("Home Welcome Back", name=profile.name.split()[0])
        if profile and profile.name
        else _t("Home Default Greeting")
    )
    powered_html = f"<div class='hero-powered'>{powered_by}</div>" if powered_by else ""
    st.markdown(
        f"""
        <section class="hero">
            <div class="hero-kicker">{_t("Home Hero Kicker")}</div>
            <h1>{hero_title}</h1>
            {powered_html}
            <p>{greeting} {_t("Home Hero Description")}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.subheader(_t("Home Business Area Title", short_name=short_name))
    cols = st.columns(5)
    cards = (
        ("01", _t("Home Feature Profile Title"), _t("Home Feature Profile Description")),
        ("02", _t("Home Feature Plan Title"), _t("Home Feature Plan Description")),
        ("03", _t("Home Feature Content Title"), _t("Home Feature Content Description")),
        ("04", _t("Home Feature Knowledge Title"), _t("Home Feature Knowledge Description")),
        ("05", _t("Home Feature AI Title"), _t("Home Feature AI Description")),
    )
    for col, (number, title, copy) in zip(cols, cards):
        col.markdown(
            f"<div class='feature-card'><div class='feature-number'>{number}</div><h3>{title}</h3><p>{copy}</p></div>",
            unsafe_allow_html=True,
        )


def render_member_profile(repository: ProfileRepository) -> None:
    _page_header(_t("Profile Page Title"), _t("Profile Page Description"))
    authenticated = st.session_state.get("authenticated_user", {})
    raw_role = str(authenticated.get("role", "Member")).strip()
    authenticated_role = raw_role if raw_role in {"Member", "Leader", "Partner", "Admin"} else "Member"
    current = repository.get() or MemberProfile(
        name=str(authenticated.get("full_name", "")),
        role=authenticated_role,
    )
    experience_index = EXPERIENCE_LEVELS.index(current.online_marketing_experience) if current.online_marketing_experience in EXPERIENCE_LEVELS else 0
    with st.form("member_profile_form"):
        left, right = st.columns(2)
        name = left.text_input(_t("Full Name"), value=current.name, placeholder=_t("Full Name Placeholder"))
        age = right.number_input(_t("Age"), min_value=18, max_value=100, value=current.age)
        occupation = left.text_input(_t("Occupation"), value=current.occupation, placeholder=_t("Occupation Placeholder"))
        daily_time = right.number_input(_t("Daily Available Time"), min_value=0.25, max_value=12.0, value=current.daily_available_time, step=0.25)
        income_goal = left.number_input(_t("Monthly Income Goal"), min_value=0.0, value=current.income_goal, step=1000.0)
        experience = right.selectbox(
            _t("Online Marketing Experience"),
            EXPERIENCE_LEVELS,
            index=experience_index,
            format_func=lambda option: _t(str(option)),
        )
        sponsor = left.text_input(
            _t("Sponsor"),
            value=current.sponsor,
            placeholder=_t("Optional"),
            help=_t("Sponsor Help"),
        )
        if authenticated_role in {"Leader", "Partner"}:
            st.markdown(f"**{_t('Assigned Team Info')}**")
            left.text_input(_t("Team Name"), value=current.team_name or _t("Not Assigned"), disabled=True)
            right.text_input(_t("Team ID"), value=current.team_id or _t("Not Assigned"), disabled=True)
            left.text_input(_t("Team Leader"), value=current.team_leader or _t("Not Assigned"), disabled=True)
            right.text_input(
                _t("Team Role"),
                value="Partner" if authenticated_role == "Partner" else _t("Leader Role Label"),
                disabled=True,
            )
            if authenticated_role == "Partner":
                st.caption(_t("Partner Referral Caption"))
            st.caption(_t("Team Info Locked Caption"))
        elif authenticated_role == "Admin":
            st.markdown(f"**{_t('Team Management Section')}**")
            st.info(_t("Team Management Info"))
        submitted = st.form_submit_button(_t("Save Member Profile"), type="primary", width="stretch")
    if submitted:
        profile = MemberProfile(
            name=name.strip(),
            age=int(age),
            occupation=occupation.strip(),
            daily_available_time=float(daily_time),
            income_goal=float(income_goal),
            online_marketing_experience=experience,
            team_name=current.team_name,
            team_id=current.team_id,
            team_leader=current.team_leader,
            sponsor=sponsor.strip(),
            role=authenticated_role,
            invited_by=current.invited_by,
            joined_at=current.joined_at,
            referrer_user_id=current.referrer_user_id,
            referrer_role_at_signup=current.referrer_role_at_signup,
            referral_rate_at_signup=current.referral_rate_at_signup,
            referral_source=current.referral_source,
            partner_status=current.partner_status,
            partner_approved_by=current.partner_approved_by,
            partner_approved_at=current.partner_approved_at,
        )
        repository.save(profile)
        if profile.is_complete:
            st.success(_t("Profile Saved Success"))
            st.markdown(f"### {_t('Recommended Next Steps')}")
            st.info(_t("Next Step Mobile Hint"))
            first, second, third = st.columns(3)
            first.button(
                _t("Onboarding CTA Plan"),
                type="primary",
                on_click=_navigate_to,
                args=("แผนปฏิบัติการ 30 วัน",),
                use_container_width=True,
            )
            second.button(
                _t("Save Prospect CTA"),
                on_click=_navigate_to,
                args=("ผู้มุ่งหวัง",),
                use_container_width=True,
            )
            third.button(
                _t("Go To Dashboard CTA"),
                on_click=_navigate_to,
                args=("Dashboard สมาชิก",),
                use_container_width=True,
            )
        else:
            st.warning(_t("Profile Incomplete Warning"))


def render_action_plan(profile: MemberProfile | None, coach: CoachService) -> None:
    _page_header(_t("30-Day Plan Page Title"), _t("30-Day Plan Page Description"))
    if not _require_profile(profile):
        return
    assert profile is not None
    a, b, c = st.columns(3)
    a.markdown(f"<div class='metric-card'><div class='metric-label'>{_t('Action Plan Daily Time')}</div><div class='metric-value'>{profile.daily_available_time:g} {_t('Hours Short')}</div></div>", unsafe_allow_html=True)
    b.markdown(f"<div class='metric-card'><div class='metric-label'>{_t('Action Plan Monthly Goal')}</div><div class='metric-value'>{profile.income_goal:,.0f} {_t('Currency Baht')}</div></div>", unsafe_allow_html=True)
    c.markdown(f"<div class='metric-card'><div class='metric-label'>{_t('Action Plan Duration')}</div><div class='metric-value'>30 {_t('Days Unit')}</div></div>", unsafe_allow_html=True)
    st.write("")
    if getattr(coach, "is_api_enabled", False):
        st.success(_t("Action Plan OpenAI Notice"))
    else:
        st.warning(_t("Action Plan Fallback Notice"))
    signature = _profile_signature(profile)
    plan = st.session_state.get("action_plan")
    saved_signature = tuple(st.session_state.get("action_plan_signature", ()))
    if plan:
        _persist_existing_action_plan_once(plan, saved_signature)
        st.info(_t("Action Plan Loaded Notice"))
        profile_changed = saved_signature not in {signature, signature[:6]}
        confirmed = True
        if profile_changed:
            st.warning(_t("Action Plan Profile Changed Warning"))
            confirmed = st.checkbox(_t("Action Plan Confirm Regenerate"))
        if st.button(
            _t("Action Plan Regenerate Button"),
            disabled=not confirmed,
            use_container_width=True,
        ):
            plan = _generate_and_save_action_plan(profile, coach, signature)
    elif st.button(
        _t("Action Plan Generate Button"),
        type="primary",
        use_container_width=True,
    ):
        plan = _generate_and_save_action_plan(profile, coach, signature)
    if not plan:
        st.info(_t("Action Plan Empty Hint"))
        return
    member_key = member_progress_key(profile)
    completion_store = st.session_state.get("plan_completion_by_member", {})
    member_statuses = dict(completion_store.get(member_key, {}))
    progress = calculate_plan_progress(member_statuses)

    st.subheader(_t("Progress Summary"))
    card_columns = st.columns(4)
    card_values = (
        (_t("Total Plan Days"), f"{progress.total_days} {_t('Days Unit')}"),
        (_t("Completed Days"), f"{progress.completed_days} {_t('Days Unit')}"),
        (_t("Remaining Days"), f"{progress.remaining_days} {_t('Days Unit')}"),
        (_t("PP Score"), f"{progress.pp_score} PP"),
    )
    for column, (label, value) in zip(card_columns, card_values):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")
    st.markdown(
        f"**{_t('Status Level')}:** {_t(progress.status_level)} &nbsp;&nbsp; | &nbsp;&nbsp; "
        f"**{_t('Progress')}:** {progress.percentage:.0f}%"
    )
    st.progress(
        progress.percentage / 100,
        text=_t("Progress Bar Text", completed=progress.completed_days, total=progress.total_days),
    )
    st.write("")

    phases = list(dict.fromkeys(item.phase for item in plan))
    tabs = st.tabs(phases)
    for tab, phase in zip(tabs, phases):
        with tab:
            for item in (entry for entry in plan if entry.phase == phase):
                tasks = " | ".join(item.tasks)
                st.markdown(
                    f"<div class='plan-day'><strong>{_t('Day Label')} {item.day}: {item.focus}</strong><br>"
                    f"<small>{tasks}<br><b>{_t('Success Metric')}:</b> {item.success_metric}</small></div>",
                    unsafe_allow_html=True,
                )
                widget_key = f"plan_day_complete_{member_key}_{item.day}"
                completed = st.checkbox(
                    _t("Mark Day Complete"),
                    value=bool(member_statuses.get(str(item.day), False)),
                    key=widget_key,
                    on_change=_update_day_completion,
                    args=(member_key, item.day, widget_key),
                )
                st.caption(_t("Day Completed Status") if completed else _t("Day Pending Status"))


def _generate_and_save_action_plan(
    profile: MemberProfile,
    coach: CoachService,
    signature: tuple[Any, ...],
) -> list[ActionItem]:
    with st.spinner(_t("Generating Action Plan")):
        plan = coach.generate_action_plan(profile)
        st.session_state.action_plan = plan
        st.session_state.action_plan_signature = signature
        supabase = get_supabase_service(st.session_state)
        authenticated = get_authenticated_supabase_user(st.session_state)
        if supabase and authenticated:
            persisted = run_supabase_sync(
                st.session_state,
                supabase.save_action_plan,
                authenticated,
                plan,
                signature,
            )
            if persisted:
                st.session_state.action_plan_persisted_signature = signature
        return plan


def _persist_existing_action_plan_once(
    plan: list[ActionItem],
    signature: tuple[Any, ...],
) -> None:
    if not signature or tuple(st.session_state.get("action_plan_persisted_signature", ())) == signature:
        return
    supabase = get_supabase_service(st.session_state)
    authenticated = get_authenticated_supabase_user(st.session_state)
    if supabase and authenticated and run_supabase_sync(
        st.session_state,
        supabase.save_action_plan,
        authenticated,
        plan,
        signature,
    ):
        st.session_state.action_plan_persisted_signature = signature


def render_content_creator(profile: MemberProfile | None, coach: CoachService) -> None:
    _page_header(_t("Content Creator"), _t("Content Creator Description"))
    if not _require_profile(profile):
        return
    assert profile is not None
    platforms = ("โพสต์ Facebook", "สคริปต์ TikTok", "ข้อความบรอดแคสต์ LINE OA")
    goals = ("สร้างการรับรู้", "เพิ่มผู้สนใจใหม่", "เชิญเข้าร่วมกิจกรรม", "ติดตามลูกค้า", "พัฒนาทีม")
    first, second = st.columns(2)
    platform = first.selectbox(_t("Platform"), platforms, key="content_platform")
    goal = second.selectbox(_t("Content Goal"), goals, key="content_goal")
    topic = st.text_input(
        _t("Content Topic"),
        value="การเริ่มต้นธุรกิจเครือข่าย",
        placeholder=_t("Content Topic Placeholder"),
        key="content_topic",
    ).strip()
    if getattr(coach, "is_api_enabled", False):
        st.success(_t("Content OpenAI Notice"))
    else:
        st.warning(_t("Content Fallback Notice"))
    input_signature = (*_profile_signature(profile), platform, goal, topic)
    if st.button(_t("Generate Content Button"), type="primary", use_container_width=True, disabled=not topic):
        with st.spinner(_t("Generating Content")):
            st.session_state.generated_channel = platform
            st.session_state.generated_content = coach.generate_content(platform, profile, goal, topic)
            st.session_state.generated_content_signature = input_signature
            record_member_usage(st.session_state, profile, "content_creator")
            supabase = get_supabase_service(st.session_state)
            authenticated = get_authenticated_supabase_user(st.session_state)
            if supabase and authenticated:
                run_supabase_sync(
                    st.session_state, supabase.save_content,
                    authenticated, platform, st.session_state.generated_content,
                )
    content = (
        st.session_state.get("generated_content")
        if st.session_state.get("generated_content_signature") == input_signature
        else None
    )
    if content:
        st.subheader(platform)
        content_key = f"content_{abs(hash(input_signature))}"
        st.text_area(_t("Generated Content Draft"), value=content, height=330, key=content_key)
        st.caption(_t("Content Review Warning"))
    else:
        st.info(_t("Content Empty Hint"))


def render_knowledge_base() -> None:
    _page_header(_t("Knowledge Hub"), _t("Knowledge Hub Description"))
    knowledge_dir = Path(__file__).resolve().parents[1] / "knowledge"
    service = KnowledgeService(knowledge_dir)
    documents = service.list_documents()

    if not documents:
        st.info(_t("Knowledge No PDFs", folder=knowledge_dir.name))
        return

    search_col, category_col = st.columns([2, 1])
    query = search_col.text_input(
        _t("Search Documents"),
        placeholder=_t("Search Documents Placeholder"),
        key="knowledge_search",
    )
    categories = [_t("All Categories"), *sorted({document.category for document in documents})]
    category = category_col.selectbox(_t("Category"), categories, key="knowledge_category")
    matches = service.search(documents, query, category)

    st.caption(_t("Knowledge Result Count", shown=len(matches), total=len(documents)))
    if not matches:
        st.warning(_t("Knowledge No Match"))
        return

    header = st.columns([5, 2, 1.4, 1])
    header[0].markdown(f"**{_t('Document Name')}**")
    header[1].markdown(f"**{_t('Category')}**")
    header[2].markdown(f"**{_t('File Size')}**")
    header[3].markdown(f"**{_t('Action')}**")

    for index, document in enumerate(matches):
        row = st.columns([5, 2, 1.4, 1])
        row[0].markdown(f"**{document.name}**")
        row[1].write(document.category)
        row[2].write(document.display_size)
        if row[3].button(_t("Open Document"), key=f"open_pdf_{document.path}", use_container_width=True):
            st.session_state.selected_knowledge_document = str(document.path)
        if index < len(matches) - 1:
            st.divider()

    selected_path = st.session_state.get("selected_knowledge_document")
    selected = next((document for document in documents if str(document.path) == selected_path), None)
    if selected:
        st.divider()
        title_col, close_col = st.columns([5, 1])
        title_col.subheader(selected.name)
        if close_col.button(_t("Close Document"), use_container_width=True):
            del st.session_state.selected_knowledge_document
            st.rerun()
        st.caption(f"{selected.category} | {selected.display_size}")
        if selected.path.suffix.casefold() in {".md", ".markdown"}:
            st.markdown(selected.path.read_text(encoding="utf-8", errors="ignore"))
        else:
            st.pdf(selected.path, height=760, key=f"pdf_viewer_{selected.path.name}")


def render_ai_coach(profile: MemberProfile | None, coach: CoachService) -> None:
    brand = _active_brand()
    coach_title = (
        "TG Life AI Business Coach"
        if brand.get("key") == "tglife"
        else "โค้ช AI จากคลังความรู้"
    )
    coach_description = (
        _t("AI Coach TG Life Description")
        if brand.get("key") == "tglife"
        else _t("AI Coach Description")
    )
    _page_header(coach_title, coach_description)
    if "coach_messages" not in st.session_state:
        greeting = (
            _t("AI Coach TG Life Greeting")
            if brand.get("key") == "tglife"
            else _t("AI Coach Greeting")
        )
        st.session_state.coach_messages = [
            {
                "role": "assistant",
                "content": greeting,
                "sources": [],
            }
        ]
    if getattr(coach, "is_api_enabled", False):
        semantic_status = getattr(getattr(coach, "knowledge_service", None), "semantic_enabled", False)
        if semantic_status:
            st.success(_t("AI Coach Semantic Ready"))
        else:
            st.success(_t("AI Coach Ready"))
    else:
        st.warning(_t("AI Coach Basic Mode"))
    top_left, top_right = st.columns([4, 1])
    top_left.caption(_t("Chat History Notice"))
    if top_right.button(_t("Clear History"), use_container_width=True):
        st.session_state.coach_messages = []
        st.rerun()
    for message in st.session_state.coach_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _render_answer_source(message.get("metadata", {}))
    placeholder = (
        _t("AI Coach TG Life Placeholder")
        if brand.get("key") == "tglife"
        else _t("AI Coach Placeholder")
    )
    if prompt := st.chat_input(placeholder):
        st.session_state.coach_messages.append({"role": "user", "content": prompt})
        supabase = get_supabase_service(st.session_state)
        authenticated = get_authenticated_supabase_user(st.session_state)
        if supabase and authenticated:
            run_supabase_sync(st.session_state, supabase.save_chat_message, authenticated, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        with render_ai_coaching_pipeline():
            result = coach.answer_question(
                prompt,
                profile,
                st.session_state.coach_messages[:-1],
                build_member_activity_context(st.session_state, profile, _language()),
            )
        response = result.answer
        st.session_state.coach_messages.append(
            {
                "role": "assistant",
                "content": response,
                "sources": list(result.sources),
                "metadata": dict(result.metadata),
            }
        )
        if supabase and authenticated:
            run_supabase_sync(
                st.session_state, supabase.save_chat_message,
                authenticated, "assistant", response, list(result.sources),
            )
        record_member_usage(st.session_state, profile, "ai_coach")
        with st.chat_message("assistant"):
            st.markdown(response)
            _render_answer_source(result.metadata)


def _render_answer_source(metadata: dict[str, object]) -> None:
    source = str(metadata.get("answer_source", "") or "")
    if not source:
        return
    if source == "openai":
        model = str(metadata.get("model", "") or "")
        label = _t("Answer Source OpenAI")
        if model:
            label += f" ({model})"
        st.caption(label)
        return
    category = str(metadata.get("error_category", "") or "")
    category_labels = {
        "authentication_error": "การยืนยันตัวตน",
        "permission_error": "สิทธิ์การใช้งาน",
        "rate_limit": "จำนวนคำขอหนาแน่น",
        "billing_or_quota": "โควตาการใช้งาน",
        "timeout": "ตอบกลับช้าเกินกำหนด",
        "connection_error": "การเชื่อมต่อ",
        "server_error": "บริการ AI ขัดข้องชั่วคราว",
        "invalid_model_or_request": "การตั้งค่าโมเดล",
        "response_validation": "รูปแบบคำตอบ",
        "unknown": "ไม่ทราบประเภท",
    }
    label = _t("Answer Source Fallback")
    if category:
        label += f" | {_t('Answer Source Reason')}: {category_labels.get(category, category)}"
    st.caption(label)
