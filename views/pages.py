from __future__ import annotations

import base64
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


def _page_header(title: str, description: str) -> None:
    st.title(title)
    st.markdown(f"<p class='section-lead'>{description}</p>", unsafe_allow_html=True)


def _require_profile(profile: MemberProfile | None) -> bool:
    if profile and profile.is_complete:
        return True
    st.warning("กรุณากรอกโปรไฟล์สมาชิกก่อน เพื่อให้ระบบจัดทำคำแนะนำที่เหมาะสมกับคุณ")
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
    statuses = build_onboarding_status(st.session_state, profile)
    steps = (
        (
            "profile", "1️⃣ โปรไฟล์สมาชิก",
            "กรอกข้อมูลพื้นฐานและเป้าหมายรายได้",
            "ไปกรอกโปรไฟล์", "โปรไฟล์สมาชิก",
        ),
        (
            "action_plan", "2️⃣ สร้างแผนปฏิบัติการ 30 วัน",
            "ให้ AI สร้างแผนงานที่เหมาะกับเป้าหมายของคุณ แล้วทำเครื่องหมายเมื่อได้ทำภารกิจ",
            "สร้างแผน 30 วัน", "แผนปฏิบัติการ 30 วัน",
        ),
        (
            "workplan", "3️⃣ บันทึกข้อมูลผู้มุ่งหวังและเป้าหมายใน Workplan",
            "เพิ่มรายชื่อผู้มุ่งหวัง บันทึกสถานะการติดตาม และกำหนดเป้าหมายการทำงาน",
            "ไปที่ Workplan", "Workplan ธุรกิจ",
        ),
        (
            "ai_coach", "4️⃣ ใช้โค้ช AI",
            "ถามคำถามเกี่ยวกับการตลาด การสร้างทีม และการพัฒนาธุรกิจ",
            "ถามโค้ช AI", "โค้ช AI",
        ),
        (
            "dashboard", "5️⃣ ลงมือปฏิบัติและติดตามผล",
            "อัปเดตความคืบหน้าใน Dashboard อย่างสม่ำเสมอ",
            "ดู Dashboard", "Dashboard สมาชิก",
        ),
    )
    completed = sum(statuses.values())
    with st.container(key="onboarding_sticky_summary"):
        st.markdown(
            "<div class='onboarding-title'>"
            "<span class='onboarding-title-desktop'>🚀 เริ่มต้นใช้งาน GetExpert</span>"
            "<span class='onboarding-title-mobile'>🚀 เริ่มต้นใช้งาน</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.progress(completed / len(steps), text=f"{completed}/5 ขั้นตอนสำเร็จ")

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
    _render_getting_started(profile)
    st.write("")
    greeting = f"ยินดีต้อนรับกลับมา คุณ{profile.name.split()[0]}" if profile and profile.name else "วางเป้าหมายให้ชัดเจน และเติบโตอย่างมั่นใจ"
    st.markdown(
        f"""
        <section class="hero">
            <div class="hero-kicker">ระบบ AI เพื่อความสำเร็จของสมาชิก</div>
            <h1>GetExpert โค้ชธุรกิจ AI</h1>
            <p>{greeting} เปลี่ยนเป้าหมายให้เป็นแผนลงมือทำที่สม่ำเสมอ สร้างคอนเทนต์ที่มีคุณภาพ และพัฒนาการสื่อสารทางธุรกิจอย่างมืออาชีพ</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.subheader("พื้นที่พัฒนาธุรกิจของคุณ")
    cols = st.columns(5)
    cards = (
        ("01", "โปรไฟล์สมาชิก", "กำหนดเป้าหมาย ประสบการณ์ และเวลาที่พร้อมลงมือทำ"),
        ("02", "แผน 30 วัน", "ดำเนินกิจกรรมพัฒนาธุรกิจอย่างเป็นขั้นตอนในแต่ละวัน"),
        ("03", "สร้างคอนเทนต์", "จัดทำข้อความพร้อมใช้สำหรับช่องทางสื่อสารสำคัญ"),
        ("04", "คลังความรู้", "ค้นหาและเปิดคู่มือพัฒนาธุรกิจของบริษัท"),
        ("05", "โค้ช AI", "รับคำแนะนำจากข้อมูลในคลังความรู้ของระบบ"),
    )
    for col, (number, title, copy) in zip(cols, cards):
        col.markdown(
            f"<div class='feature-card'><div class='feature-number'>{number}</div><h3>{title}</h3><p>{copy}</p></div>",
            unsafe_allow_html=True,
        )


def render_member_profile(repository: ProfileRepository) -> None:
    _page_header("โปรไฟล์สมาชิก", "ให้ข้อมูลพื้นฐานเพื่อช่วยให้ระบบวางแผนพัฒนาธุรกิจได้ตรงกับเป้าหมายของคุณ")
    authenticated = st.session_state.get("authenticated_user", {})
    raw_role = str(authenticated.get("role", "Member")).strip()
    authenticated_role = raw_role if raw_role in {"Member", "Leader", "Admin"} else "Member"
    current = repository.get() or MemberProfile(
        name=str(authenticated.get("full_name", "")),
        role=authenticated_role,
    )
    experience_index = EXPERIENCE_LEVELS.index(current.online_marketing_experience) if current.online_marketing_experience in EXPERIENCE_LEVELS else 0
    with st.form("member_profile_form"):
        left, right = st.columns(2)
        name = left.text_input("ชื่อ-นามสกุล", value=current.name, placeholder="ตัวอย่าง: สมชาย ใจดี")
        age = right.number_input("อายุ", min_value=18, max_value=100, value=current.age)
        occupation = left.text_input("อาชีพ", value=current.occupation, placeholder="ตัวอย่าง: ผู้จัดการฝ่ายขาย")
        daily_time = right.number_input("เวลาที่พร้อมทำงานต่อวัน (ชั่วโมง)", min_value=0.25, max_value=12.0, value=current.daily_available_time, step=0.25)
        income_goal = left.number_input("เป้าหมายรายได้ต่อเดือน (บาท)", min_value=0.0, value=current.income_goal, step=1000.0)
        experience = right.selectbox("ประสบการณ์ด้านการตลาดออนไลน์", EXPERIENCE_LEVELS, index=experience_index)
        sponsor = left.text_input(
            "ผู้แนะนำ",
            value=current.sponsor,
            placeholder="ไม่บังคับ",
            help="ระบุชื่อผู้แนะนำได้ตามต้องการ",
        )
        if authenticated_role == "Leader":
            st.markdown("**ข้อมูลทีมที่ได้รับมอบหมาย**")
            left.text_input("ชื่อทีม", value=current.team_name or "ยังไม่ได้รับมอบหมาย", disabled=True)
            right.text_input("รหัสทีม", value=current.team_id or "ยังไม่ได้รับมอบหมาย", disabled=True)
            left.text_input("หัวหน้าทีม", value=current.team_leader or "ยังไม่ได้รับมอบหมาย", disabled=True)
            right.text_input("บทบาทในทีม", value="ผู้นำ", disabled=True)
            st.caption("ข้อมูลทีมกำหนดโดยผู้ดูแลระบบและไม่สามารถแก้ไขจากหน้าโปรไฟล์ได้")
        elif authenticated_role == "Admin":
            st.markdown("**การจัดการทีม**")
            st.info("กำหนดหัวหน้าทีมและสมาชิกได้จากเมนูจัดการทีม")
        submitted = st.form_submit_button("บันทึกโปรไฟล์สมาชิก", type="primary", width="stretch")
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
        )
        repository.save(profile)
        if profile.is_complete:
            st.success("บันทึกโปรไฟล์เรียบร้อย ระบบพร้อมจัดทำคำแนะนำเฉพาะบุคคลให้คุณแล้ว")
            st.markdown("### ขั้นตอนถัดไปที่แนะนำ")
            st.info("เลือกดำเนินการต่อได้ทันที โดยเฉพาะบนมือถือให้แตะปุ่มด้านล่างเพื่อไปหน้าถัดไป")
            first, second, third = st.columns(3)
            first.button(
                "สร้างแผน 30 วัน",
                type="primary",
                on_click=_navigate_to,
                args=("แผนปฏิบัติการ 30 วัน",),
                use_container_width=True,
            )
            second.button(
                "บันทึกผู้มุ่งหวัง",
                on_click=_navigate_to,
                args=("ผู้มุ่งหวัง",),
                use_container_width=True,
            )
            third.button(
                "ไปที่ Dashboard",
                on_click=_navigate_to,
                args=("Dashboard สมาชิก",),
                use_container_width=True,
            )
        else:
            st.warning("บันทึกข้อมูลแล้ว กรุณาระบุชื่อและอาชีพเพื่อให้ระบบจัดทำคำแนะนำได้สมบูรณ์")


def render_action_plan(profile: MemberProfile | None, coach: CoachService) -> None:
    _page_header("แผนปฏิบัติการ 30 วัน", "แผนพัฒนาธุรกิจรายวัน ตั้งแต่การวางรากฐานจนถึงการติดตามผลและต่อยอด")
    if not _require_profile(profile):
        return
    assert profile is not None
    a, b, c = st.columns(3)
    a.markdown(f"<div class='metric-card'><div class='metric-label'>เวลาลงมือทำต่อวัน</div><div class='metric-value'>{profile.daily_available_time:g} ชม.</div></div>", unsafe_allow_html=True)
    b.markdown(f"<div class='metric-card'><div class='metric-label'>เป้าหมายรายได้ต่อเดือน</div><div class='metric-value'>{profile.income_goal:,.0f} บาท</div></div>", unsafe_allow_html=True)
    c.markdown("<div class='metric-card'><div class='metric-label'>ระยะเวลาแผนงาน</div><div class='metric-value'>30 วัน</div></div>", unsafe_allow_html=True)
    st.write("")
    if getattr(coach, "is_api_enabled", False):
        st.success("ระบบจะใช้ OpenAI เพื่อสร้างแผนเฉพาะบุคคลจากข้อมูลโปรไฟล์ทั้ง 6 ด้าน")
    else:
        st.warning("ยังไม่ได้ตั้งค่า OPENAI_API_KEY ระบบจึงใช้แผนพื้นฐานที่ปรับตามโปรไฟล์สมาชิก")
    signature = _profile_signature(profile)
    plan = st.session_state.get("action_plan")
    saved_signature = tuple(st.session_state.get("action_plan_signature", ()))
    if plan:
        _persist_existing_action_plan_once(plan, saved_signature)
        st.info("ระบบโหลดแผนปฏิบัติการที่บันทึกไว้ล่าสุดแล้ว")
        profile_changed = saved_signature not in {signature, signature[:6]}
        confirmed = True
        if profile_changed:
            st.warning("ข้อมูลโปรไฟล์มีการเปลี่ยนแปลง แผนเดิมยังคงแสดงอยู่และจะไม่ถูกแทนที่จนกว่าคุณจะยืนยันสร้างแผนใหม่")
            confirmed = st.checkbox("ยืนยันสร้างแผนใหม่จากข้อมูลโปรไฟล์ล่าสุด")
        if st.button(
            "สร้างแผนใหม่",
            disabled=not confirmed,
            use_container_width=True,
        ):
            plan = _generate_and_save_action_plan(profile, coach, signature)
    elif st.button(
        "สร้างแผนปฏิบัติการ 30 วันของฉัน",
        type="primary",
        use_container_width=True,
    ):
        plan = _generate_and_save_action_plan(profile, coach, signature)
    if not plan:
        st.info("กดปุ่มสร้างแผน เพื่อดูภารกิจประจำวันและตัวชี้วัดความสำเร็จ")
        return
    member_key = member_progress_key(profile)
    completion_store = st.session_state.get("plan_completion_by_member", {})
    member_statuses = dict(completion_store.get(member_key, {}))
    progress = calculate_plan_progress(member_statuses)

    st.subheader("สรุปความก้าวหน้า")
    card_columns = st.columns(4)
    card_values = (
        ("แผนทั้งหมด", f"{progress.total_days} วัน"),
        ("ทำสำเร็จแล้ว", f"{progress.completed_days} วัน"),
        ("คงเหลือ", f"{progress.remaining_days} วัน"),
        ("คะแนน PP", f"{progress.pp_score} PP"),
    )
    for column, (label, value) in zip(card_columns, card_values):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")
    st.markdown(
        f"**ระดับสถานะ:** {progress.status_level} &nbsp;&nbsp; | &nbsp;&nbsp; "
        f"**ความก้าวหน้า:** {progress.percentage:.0f}%"
    )
    st.progress(
        progress.percentage / 100,
        text=f"ทำสำเร็จ {progress.completed_days} วัน จากทั้งหมด {progress.total_days} วัน",
    )
    st.write("")

    phases = list(dict.fromkeys(item.phase for item in plan))
    tabs = st.tabs(phases)
    for tab, phase in zip(tabs, phases):
        with tab:
            for item in (entry for entry in plan if entry.phase == phase):
                tasks = " | ".join(item.tasks)
                st.markdown(
                    f"<div class='plan-day'><strong>วันที่ {item.day}: {item.focus}</strong><br>"
                    f"<small>{tasks}<br><b>ตัวชี้วัดความสำเร็จ:</b> {item.success_metric}</small></div>",
                    unsafe_allow_html=True,
                )
                widget_key = f"plan_day_complete_{member_key}_{item.day}"
                completed = st.checkbox(
                    "ทำกิจกรรมวันนี้สำเร็จแล้ว",
                    value=bool(member_statuses.get(str(item.day), False)),
                    key=widget_key,
                    on_change=_update_day_completion,
                    args=(member_key, item.day, widget_key),
                )
                st.caption("สถานะ: ทำสำเร็จแล้ว" if completed else "สถานะ: ยังไม่สำเร็จ")


def _generate_and_save_action_plan(
    profile: MemberProfile,
    coach: CoachService,
    signature: tuple[Any, ...],
) -> list[ActionItem]:
    with st.spinner("กำลังสร้างแผนเฉพาะบุคคล..."):
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
    _page_header("เครื่องมือสร้างคอนเทนต์", "สร้างข้อความสื่อสารที่มีคุณค่า เหมาะสำหรับช่องทางที่สมาชิกและลูกค้าใช้งานทุกวัน")
    if not _require_profile(profile):
        return
    assert profile is not None
    platforms = ("โพสต์ Facebook", "สคริปต์ TikTok", "ข้อความบรอดแคสต์ LINE OA")
    goals = ("สร้างการรับรู้", "เพิ่มผู้สนใจใหม่", "เชิญเข้าร่วมกิจกรรม", "ติดตามลูกค้า", "พัฒนาทีม")
    first, second = st.columns(2)
    platform = first.selectbox("แพลตฟอร์ม", platforms, key="content_platform")
    goal = second.selectbox("เป้าหมายของคอนเทนต์", goals, key="content_goal")
    topic = st.text_input(
        "หัวข้อที่ต้องการสื่อสาร",
        value="การเริ่มต้นธุรกิจเครือข่าย",
        placeholder="ตัวอย่าง: วิธีสร้างรายชื่อผู้มุ่งหวัง",
        key="content_topic",
    ).strip()
    if getattr(coach, "is_api_enabled", False):
        st.success("ระบบจะใช้ OpenAI โปรไฟล์สมาชิก และบริบทจากคลังความรู้เพื่อสร้างคอนเทนต์")
    else:
        st.warning("ยังไม่ได้ตั้งค่า OPENAI_API_KEY ระบบจึงใช้เทมเพลตพื้นฐานที่ปรับตามโปรไฟล์")
    input_signature = (*_profile_signature(profile), platform, goal, topic)
    if st.button("สร้างคอนเทนต์เฉพาะบุคคล", type="primary", use_container_width=True, disabled=not topic):
        with st.spinner("กำลังสร้างคอนเทนต์จากโปรไฟล์และคลังความรู้..."):
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
        st.text_area("ร่างคอนเทนต์ที่สร้างแล้ว", value=content, height=330, key=content_key)
        st.caption("กรุณาตรวจสอบข้อความกล่าวอ้าง รายละเอียดผลิตภัณฑ์ และข้อกำหนดของบริษัทก่อนเผยแพร่ทุกครั้ง")
    else:
        st.info("เลือกช่องทางที่ต้องการ เพื่อให้ระบบสร้างร่างคอนเทนต์ฉบับแรก")


def render_knowledge_base() -> None:
    _page_header("คลังความรู้", "ค้นหาและเปิดคู่มือฝึกอบรม เอกสารพัฒนาทักษะ และแหล่งความรู้ทางธุรกิจ")
    knowledge_dir = Path(__file__).resolve().parents[1] / "knowledge"
    service = KnowledgeService(knowledge_dir)
    documents = service.list_documents()

    if not documents:
        st.info(f"ไม่พบเอกสาร PDF ในโฟลเดอร์ {knowledge_dir.name}/ กรุณาเพิ่มไฟล์ PDF เพื่อแสดงในคลังความรู้")
        return

    search_col, category_col = st.columns([2, 1])
    query = search_col.text_input(
        "ค้นหาเอกสาร",
        placeholder="ค้นหาจากชื่อเอกสารหรือหมวดหมู่...",
        key="knowledge_search",
    )
    categories = ["ทุกหมวดหมู่", *sorted({document.category for document in documents})]
    category = category_col.selectbox("หมวดหมู่", categories, key="knowledge_category")
    matches = service.search(documents, query, category)

    st.caption(f"แสดงเอกสาร {len(matches)} จากทั้งหมด {len(documents)} รายการ")
    if not matches:
        st.warning("ไม่พบเอกสารที่ตรงกับการค้นหา กรุณาลองใช้คำค้นหรือเลือกหมวดหมู่อื่น")
        return

    header = st.columns([4.2, 1.8, 1.2, 2.4])
    header[0].markdown("**ชื่อเอกสาร**")
    header[1].markdown("**หมวดหมู่**")
    header[2].markdown("**ขนาดไฟล์**")
    header[3].markdown("**ดำเนินการ**")

    for index, document in enumerate(matches):
        row = st.columns([4.2, 1.8, 1.2, 2.4])
        row[0].markdown(f"**{document.name}**")
        row[1].write(document.category)
        row[2].write(document.display_size)
        action_cols = row[3].columns(2)
        document_path = Path(document.path)
        if action_cols[0].button("เปิดอ่าน", key=f"open_pdf_{document_path.name}", use_container_width=True):
            st.session_state.selected_knowledge_document = str(document_path)
        try:
            pdf_bytes = document_path.read_bytes()
            action_cols[1].download_button(
                "ดาวน์โหลด",
                data=pdf_bytes,
                file_name=document_path.name,
                mime="application/pdf",
                key=f"download_pdf_{document_path.name}",
                use_container_width=True,
            )
        except OSError:
            action_cols[1].button(
                "ดาวน์โหลด",
                key=f"download_unavailable_{document_path.name}",
                disabled=True,
                use_container_width=True,
            )
        if index < len(matches) - 1:
            st.divider()

    selected_path = st.session_state.get("selected_knowledge_document")
    selected = next((document for document in documents if str(document.path) == selected_path), None)
    if selected:
        st.divider()
        title_col, close_col = st.columns([5, 1])
        title_col.subheader(selected.name)
        if close_col.button("ปิดเอกสาร", use_container_width=True):
            del st.session_state.selected_knowledge_document
            st.rerun()
        st.caption(f"{selected.category} | {selected.display_size}")
        selected_path = Path(selected.path)
        try:
            pdf_bytes = selected_path.read_bytes()
        except OSError:
            st.error("ไม่สามารถเปิดไฟล์ PDF นี้ได้ กรุณาตรวจสอบว่าไฟล์ยังอยู่ในโฟลเดอร์ knowledge/")
            return
        st.download_button(
            "ดาวน์โหลดเอกสารนี้",
            data=pdf_bytes,
            file_name=selected_path.name,
            mime="application/pdf",
            key=f"download_selected_pdf_{selected_path.name}",
        )
        try:
            st.pdf(pdf_bytes, height=760, key=f"pdf_viewer_{selected_path.name}")
        except Exception:
            encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            st.markdown(
                f"""
                <iframe
                    src="data:application/pdf;base64,{encoded_pdf}"
                    width="100%"
                    height="760"
                    style="border: 1px solid #D7DEE8; border-radius: 12px;"
                    title="{selected.name}">
                </iframe>
                """,
                unsafe_allow_html=True,
            )


def render_ai_coach(profile: MemberProfile | None, coach: CoachService) -> None:
    _page_header("โค้ช AI จากคลังความรู้", "ถามคำถามจากคู่มือในคลังความรู้ และรับคำแนะนำภาษาไทยพร้อมชื่อเอกสารอ้างอิง")
    if "coach_messages" not in st.session_state:
        st.session_state.coach_messages = [
            {
                "role": "assistant",
                "content": "สวัสดีครับ โค้ชพร้อมช่วยค้นคำตอบจากฐานความรู้ของคุณ วันนี้อยากพัฒนาเรื่องไหนเป็นพิเศษครับ",
                "sources": [],
            }
        ]
    if getattr(coach, "is_api_enabled", False):
        semantic_status = getattr(getattr(coach, "knowledge_service", None), "semantic_enabled", False)
        if semantic_status:
            st.success("เชื่อมต่อ OpenAI API และระบบค้นหาความหมายแล้ว โค้ชพร้อมให้คำแนะนำเฉพาะบุคคล")
        else:
            st.success("เชื่อมต่อ OpenAI API แล้ว โค้ชพร้อมให้คำแนะนำเฉพาะบุคคล")
    else:
        st.warning("ยังไม่ได้ตั้งค่า OPENAI_API_KEY ระบบจึงใช้โหมดค้นหาพื้นฐาน")
    top_left, top_right = st.columns([4, 1])
    top_left.caption("ประวัติการสนทนาจะถูกเก็บไว้ตลอดการใช้งานในครั้งนี้")
    if top_right.button("ล้างประวัติ", use_container_width=True):
        st.session_state.coach_messages = []
        st.rerun()
    for message in st.session_state.coach_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if prompt := st.chat_input("ถามเกี่ยวกับ 5 โมดูล แผนงาน MLM, LINE OA, TikTok, Canva หรือคู่มืออื่น ๆ..."):
        st.session_state.coach_messages.append({"role": "user", "content": prompt})
        supabase = get_supabase_service(st.session_state)
        authenticated = get_authenticated_supabase_user(st.session_state)
        if supabase and authenticated:
            run_supabase_sync(st.session_state, supabase.save_chat_message, authenticated, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        result = coach.answer_question(
            prompt,
            profile,
            st.session_state.coach_messages[:-1],
            build_member_activity_context(st.session_state, profile),
        )
        response = result.answer
        st.session_state.coach_messages.append(
            {"role": "assistant", "content": response, "sources": list(result.sources)}
        )
        if supabase and authenticated:
            run_supabase_sync(
                st.session_state, supabase.save_chat_message,
                authenticated, "assistant", response, list(result.sources),
            )
        record_member_usage(st.session_state, profile, "ai_coach")
        with st.chat_message("assistant"):
            st.markdown(response)
