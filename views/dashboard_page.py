from __future__ import annotations

from copy import deepcopy
from html import escape
from typing import Any

import streamlit as st

from models import MemberProfile
from services.coach_service import CoachService, LocalCoachService
from services.dashboard_service import (
    EMPTY_DASHBOARD_MESSAGE,
    build_and_save_dashboard,
    dashboard_context,
    dashboard_signature,
)
from services.pdf_report_service import (
    MISSING_THAI_FONT_MESSAGE,
    generate_member_report_pdf,
    member_report_filename,
    thai_pdf_fonts_available,
    thai_pdf_font_paths,
)


def render_member_dashboard(profile: MemberProfile | None, coach: CoachService) -> None:
    brand = st.session_state.get("_active_brand", {})
    title = "TG Life Member Dashboard" if brand.get("key") == "tglife" else "Dashboard สมาชิก"
    st.title(title)
    st.markdown(
        "<p class='section-lead'>ภาพรวมความสำเร็จส่วนบุคคลจากโปรไฟล์ แผน 30 วัน Workplan และการใช้งานเครื่องมือ AI</p>",
        unsafe_allow_html=True,
    )
    snapshot = build_and_save_dashboard(st.session_state, profile)
    if snapshot is None:
        st.info(EMPTY_DASHBOARD_MESSAGE)
        return

    _render_cards(snapshot)
    _render_team_cards(snapshot)
    _render_status(snapshot)
    _render_charts(snapshot)
    current_insight = _render_ai_insight(profile, coach, snapshot)
    _render_pdf_export(profile, snapshot, current_insight)


def _render_cards(snapshot: dict[str, Any]) -> None:
    plan = snapshot["plan"]
    contacts = snapshot["contacts"]
    goals = snapshot["goals"]
    st.subheader("ภาพรวมสมาชิก")
    _card_row(
        (
            ("ชื่อสมาชิก", escape(snapshot["name"])),
            ("เป้าหมายรายได้", f"{snapshot['income_goal']:,.0f} บาท"),
            ("ความคืบหน้าแผน 30 วัน", f"{plan['percentage']:.0f}%"),
            ("คะแนน PP", f"{plan['pp_score']} PP"),
        )
    )
    _card_row(
        (
            ("จำนวนรายชื่อทั้งหมด", f"{contacts['total']} ราย"),
            ("รายชื่อ A", f"{contacts['A']} ราย"),
            ("รายชื่อ B", f"{contacts['B']} ราย"),
            ("รายชื่อ C", f"{contacts['C']} ราย"),
        )
    )
    _card_row(
        (
            ("รายชื่อ D", f"{contacts['D']} ราย"),
            ("ผู้มุ่งหวังสมัครแล้ว", f"{contacts['signed_up']} ราย"),
            ("ผู้มุ่งหวังนัดหมายแล้ว", f"{contacts['appointments']} ราย"),
        )
    )
    _card_row(
        (
            ("เป้าหมายสปอนเซอร์", f"{goals['sponsor']['percentage']:.0f}%"),
            ("เป้าหมายคะแนนทีม", f"{goals['team_points']['percentage']:.0f}%"),
            ("เป้าหมายรายได้ Workplan", f"{goals['income']['percentage']:.0f}%"),
            ("สร้างคอนเทนต์", f"{snapshot['usage']['content_creator']} ครั้ง"),
            ("ใช้งานโค้ช AI", f"{snapshot['usage']['ai_coach']} คำถาม"),
        )
    )


def _render_team_cards(snapshot: dict[str, Any]) -> None:
    team = snapshot["team"]
    st.subheader("ข้อมูลทีม")
    _card_row(
        (
            ("ชื่อทีม", escape(team["name"] or "ยังไม่ระบุ")),
            ("รหัสทีม", escape(team["id"] or "ยังไม่ระบุ")),
            ("หัวหน้าทีม", escape(team["leader"] or "ยังไม่ระบุ")),
            ("ผู้แนะนำ", escape(team["sponsor"] or "ยังไม่ระบุ")),
            ("บทบาท", escape(team["role"])),
        )
    )


def _card_row(cards: tuple[tuple[str, str], ...]) -> None:
    columns = st.columns(len(cards))
    for column, (label, value) in zip(columns, cards):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")


def _render_status(snapshot: dict[str, Any]) -> None:
    plan = snapshot["plan"]
    st.subheader("ระดับสถานะ")
    st.markdown(f"**{plan['status']}** — ทำสำเร็จ {plan['completed']} จาก {plan['total']} วัน")
    st.progress(plan["percentage"] / 100, text=f"ความก้าวหน้า {plan['percentage']:.0f}%")


def _render_charts(snapshot: dict[str, Any]) -> None:
    st.subheader("กราฟความก้าวหน้า")
    plan = snapshot["plan"]
    goals = snapshot["goals"]
    charts = (
        ("แผนปฏิบัติการ 30 วัน", plan["total"], plan["completed"], "วัน"),
        ("เป้าหมายสปอนเซอร์", goals["sponsor"]["target"], goals["sponsor"]["actual"], "คน"),
        ("เป้าหมายคะแนนทีม", goals["team_points"]["target"], goals["team_points"]["actual"], "คะแนน"),
        ("เป้าหมายรายได้", goals["income"]["target"], goals["income"]["actual"], "บาท"),
    )
    columns = st.columns(2)
    for index, (title, target, actual, unit) in enumerate(charts):
        with columns[index % 2]:
            st.markdown(f"**{title} ({unit})**")
            st.vega_lite_chart(
                {
                    "values": [
                        {"รายการ": "เป้าหมาย", "ค่า": float(target)},
                        {"รายการ": "ผลลัพธ์จริง", "ค่า": float(actual)},
                    ]
                },
                {
                    "height": 230,
                    "mark": {"type": "bar", "cornerRadiusTopLeft": 6, "cornerRadiusTopRight": 6},
                    "encoding": {
                        "x": {
                            "field": "รายการ",
                            "type": "nominal",
                            "axis": {"labelAngle": 0, "title": None},
                        },
                        "y": {
                            "field": "ค่า",
                            "type": "quantitative",
                            "axis": {"title": unit},
                        },
                        "color": {
                            "field": "รายการ",
                            "type": "nominal",
                            "scale": {
                                "domain": ["เป้าหมาย", "ผลลัพธ์จริง"],
                                "range": ["#0B2E59", "#F59E0B"],
                            },
                            "legend": {"title": "คำอธิบาย"},
                        },
                        "tooltip": [
                            {"field": "รายการ", "type": "nominal", "title": "รายการ"},
                            {"field": "ค่า", "type": "quantitative", "title": unit, "format": ",.0f"},
                        ],
                    },
                    "config": {
                        "axis": {"labelColor": "#1F2937", "titleColor": "#1F2937"},
                        "legend": {"labelColor": "#1F2937", "titleColor": "#1F2937"},
                    },
                },
                width="stretch",
            )


def _render_ai_insight(
    profile: MemberProfile | None,
    coach: CoachService,
    snapshot: dict[str, Any],
) -> str | None:
    assert profile is not None
    st.subheader("AI Insight")
    st.caption("วิเคราะห์จุดแข็ง จุดที่ควรปรับปรุง และแผนลงมือทำสำหรับ 7 วันข้างหน้า")
    signature = dashboard_signature(snapshot)
    store = deepcopy(st.session_state.get("dashboard_insights_by_member", {}))
    saved = store.get(snapshot["member_key"], {})
    current_insight = saved.get("insight") if saved.get("signature") == signature else None

    button_label = "อัปเดต AI Insight" if current_insight else "สร้าง AI Insight"
    if st.button(button_label, type="primary", width="stretch"):
        with st.spinner("กำลังวิเคราะห์ข้อมูลความสำเร็จของคุณ..."):
            insight = coach.generate_dashboard_insight(profile, dashboard_context(snapshot))
        store[snapshot["member_key"]] = {"signature": signature, "insight": insight}
        st.session_state.dashboard_insights_by_member = store
        current_insight = insight

    if current_insight:
        st.markdown(current_insight)
    elif getattr(coach, "is_api_enabled", False):
        st.info("กดปุ่มสร้าง AI Insight เพื่อรับคำแนะนำเฉพาะบุคคลจากข้อมูลล่าสุด")
    else:
        st.info("ระบบจะสร้าง Insight ภาษาไทยแบบพื้นฐาน เนื่องจากยังไม่ได้ตั้งค่า OPENAI_API_KEY")
    return current_insight


@st.cache_data(show_spinner=False)
def _pdf_bytes(
    profile: MemberProfile,
    snapshot: dict[str, Any],
    insight: str,
) -> bytes:
    return generate_member_report_pdf(profile, snapshot, insight)


def _mark_pdf_success() -> None:
    st.session_state.dashboard_pdf_success = True


def _render_pdf_export(
    profile: MemberProfile | None,
    snapshot: dict[str, Any],
    current_insight: str | None,
) -> None:
    assert profile is not None
    st.subheader("รายงานสมาชิก")
    if not thai_pdf_fonts_available():
        font_paths = thai_pdf_font_paths()
        st.warning(
            f"{MISSING_THAI_FONT_MESSAGE} "
            f"({font_paths['regular'].as_posix()}, {font_paths['bold'].as_posix()})"
        )
        st.button("ดาวน์โหลดรายงาน PDF", disabled=True, width="stretch")
        return
    fallback_insight = LocalCoachService().generate_dashboard_insight(
        profile,
        dashboard_context(snapshot),
    )
    try:
        pdf_data = _pdf_bytes(profile, snapshot, current_insight or fallback_insight)
    except Exception as error:
        st.error(f"ไม่สามารถสร้างรายงาน PDF ได้: {error}")
        return

    if st.session_state.pop("dashboard_pdf_success", False):
        st.success("สร้างรายงาน PDF สำเร็จ")
    st.download_button(
        "ดาวน์โหลดรายงาน PDF",
        data=pdf_data,
        file_name=member_report_filename(profile.name),
        mime="application/pdf",
        type="primary",
        width="stretch",
        on_click=_mark_pdf_success,
    )
