from __future__ import annotations

from copy import deepcopy
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from models import MemberProfile
from services.coach_service import CoachService, LocalCoachService
from services.dashboard_service import (
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
from translations import translate


def _language() -> str:
    return str(st.session_state.get("language", "th"))


def _t(key: str, **values: object) -> str:
    text = translate(key, _language())
    return text.format(**values) if values else text


def render_member_dashboard(profile: MemberProfile | None, coach: CoachService) -> None:
    brand = st.session_state.get("_active_brand", {})
    title = _t("Member Dashboard Title", short_name=brand.get("short_name", "GetExpert"))
    st.title(title)
    st.markdown(
        f"<p class='section-lead'>{_t('Dashboard Page Description')}</p>",
        unsafe_allow_html=True,
    )
    snapshot = build_and_save_dashboard(st.session_state, profile)
    if snapshot is None:
        st.info(_t("Dashboard Insufficient Data"))
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
    st.subheader(_t("Member Overview"))
    _card_row(
        (
            (_t("Member Name"), escape(snapshot["name"])),
            (_t("Income Goal"), f"{snapshot['income_goal']:,.0f} {_t('Currency Baht')}"),
            (_t("30-Day Plan Progress"), f"{plan['percentage']:.0f}%"),
            (_t("PP Score"), f"{plan['pp_score']} PP"),
        )
    )
    _card_row(
        (
            (_t("Total Prospects"), f"{contacts['total']} {_t('Prospect Unit')}"),
            ("A", f"{contacts['A']} {_t('Prospect Unit')}"),
            ("B", f"{contacts['B']} {_t('Prospect Unit')}"),
            ("C", f"{contacts['C']} {_t('Prospect Unit')}"),
        )
    )
    _card_row(
        (
            ("D", f"{contacts['D']} {_t('Prospect Unit')}"),
            (_t("Signed Up Prospects"), f"{contacts['signed_up']} {_t('Prospect Unit')}"),
            (_t("Appointment Prospects"), f"{contacts['appointments']} {_t('Prospect Unit')}"),
        )
    )
    _card_row(
        (
            (_t("Sponsor Goal"), f"{goals['sponsor']['percentage']:.0f}%"),
            (_t("Team Points Goal"), f"{goals['team_points']['percentage']:.0f}%"),
            (_t("Workplan Income Goal"), f"{goals['income']['percentage']:.0f}%"),
            (_t("Content Created"), f"{snapshot['usage']['content_creator']} {_t('Times Unit')}"),
            (_t("AI Coach Usage"), f"{snapshot['usage']['ai_coach']} {_t('Questions Unit')}"),
        )
    )


def _render_team_cards(snapshot: dict[str, Any]) -> None:
    team = snapshot["team"]
    st.subheader(_t("Team Information"))
    _card_row(
        (
            (_t("Team Name"), escape(team["name"] or _t("Not Specified"))),
            (_t("Team ID"), escape(team["id"] or _t("Not Specified"))),
            (_t("Team Leader"), escape(team["leader"] or _t("Not Specified"))),
            (_t("Sponsor"), escape(team["sponsor"] or _t("Not Specified"))),
            (_t("Role"), escape(team["role"])),
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
    st.subheader(_t("Status Level"))
    st.markdown(f"**{plan['status']}** — {_t('Dashboard Completed Text', completed=plan['completed'], total=plan['total'])}")
    st.progress(plan["percentage"] / 100, text=f"{_t('Progress')} {plan['percentage']:.0f}%")


def _render_charts(snapshot: dict[str, Any]) -> None:
    st.subheader(_t("Progress Charts"))
    charts, goals_empty = _dashboard_chart_entries(
        snapshot,
        plan_title=_t("30-Day Plan Page Title"),
        sponsor_title=_t("Sponsor Goal"),
        team_points_title=_t("Team Points Goal"),
        income_title=_t("Income Goal"),
        days_unit=_t("Days Unit"),
        people_unit=_t("People Unit"),
        points_unit=_t("Points Unit"),
        currency_unit=_t("Currency Baht"),
    )
    if goals_empty:
        st.info(_t("Dashboard Goals Empty State"))
    columns = st.columns(2)
    for index, (title, target, actual, unit) in enumerate(charts):
        with columns[index % 2]:
            st.markdown(f"**{title} ({unit})**")
            records = _chart_records(
                target,
                actual,
                item_field=_t("Chart Item Field"),
                value_field=_t("Chart Value Field"),
                color_field=_t("Legend"),
                target_label=_t("Target"),
                actual_label=_t("Actual Result"),
            )
            st.bar_chart(
                pd.DataFrame.from_records(records),
                x=_t("Chart Item Field"),
                y=_t("Chart Value Field"),
                color=_t("Legend"),
                stack=False,
                height=260,
                width="stretch",
            )


def _dashboard_chart_entries(
    snapshot: dict[str, Any],
    *,
    plan_title: str = "แผนปฏิบัติการ 30 วัน",
    sponsor_title: str = "เป้าหมายสปอนเซอร์",
    team_points_title: str = "เป้าหมายคะแนนทีม",
    income_title: str = "เป้าหมายรายได้",
    days_unit: str = "วัน",
    people_unit: str = "คน",
    points_unit: str = "คะแนน",
    currency_unit: str = "บาท",
) -> tuple[list[tuple[str, Any, Any, str]], bool]:
    plan = snapshot["plan"]
    goals = snapshot["goals"]
    plan_chart = (plan_title, plan["total"], plan["completed"], days_unit)
    goal_charts = (
        (sponsor_title, goals["sponsor"]["target"], goals["sponsor"]["actual"], people_unit),
        (team_points_title, goals["team_points"]["target"], goals["team_points"]["actual"], points_unit),
        (income_title, goals["income"]["target"], goals["income"]["actual"], currency_unit),
    )
    charts = [plan_chart] if _safe_number(plan["total"]) > 0 else []
    visible_goal_charts = [chart for chart in goal_charts if _safe_number(chart[1]) > 0]
    charts.extend(visible_goal_charts)
    return charts, not visible_goal_charts


def _safe_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return max(0.0, float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0.0


def _chart_records(
    target: Any,
    actual: Any,
    *,
    item_field: str = "รายการ",
    value_field: str = "ค่า",
    color_field: str = "คำอธิบาย",
    target_label: str = "เป้าหมาย",
    actual_label: str = "ผลลัพธ์จริง",
) -> list[dict[str, Any]]:
    return [
        {
            item_field: target_label,
            value_field: _safe_number(target),
            color_field: target_label,
        },
        {
            item_field: actual_label,
            value_field: _safe_number(actual),
            color_field: actual_label,
        },
    ]


def _render_ai_insight(
    profile: MemberProfile | None,
    coach: CoachService,
    snapshot: dict[str, Any],
) -> str | None:
    assert profile is not None
    st.subheader("AI Insight")
    st.caption(_t("AI Insight Description"))
    signature = dashboard_signature(snapshot)
    store = deepcopy(st.session_state.get("dashboard_insights_by_member", {}))
    saved = store.get(snapshot["member_key"], {})
    current_insight = saved.get("insight") if saved.get("signature") == signature else None

    button_label = _t("Update AI Insight") if current_insight else _t("Create AI Insight")
    if st.button(button_label, type="primary", width="stretch"):
        with st.spinner(_t("Analyzing Success Data")):
            insight = coach.generate_dashboard_insight(profile, dashboard_context(snapshot))
        store[snapshot["member_key"]] = {"signature": signature, "insight": insight}
        st.session_state.dashboard_insights_by_member = store
        current_insight = insight

    if current_insight:
        st.markdown(current_insight)
    elif getattr(coach, "is_api_enabled", False):
        st.info(_t("AI Insight Empty Hint"))
    else:
        st.info(_t("AI Insight Fallback Hint"))
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
    st.subheader(_t("Member Report"))
    if not thai_pdf_fonts_available():
        font_paths = thai_pdf_font_paths()
        st.warning(
            f"{MISSING_THAI_FONT_MESSAGE} "
            f"({font_paths['regular'].as_posix()}, {font_paths['bold'].as_posix()})"
        )
        st.button(_t("Download PDF Report"), disabled=True, width="stretch")
        return
    fallback_insight = LocalCoachService().generate_dashboard_insight(
        profile,
        dashboard_context(snapshot),
    )
    try:
        pdf_data = _pdf_bytes(profile, snapshot, current_insight or fallback_insight)
    except Exception as error:
        st.error(f"{_t('PDF Generation Error')}: {error}")
        return

    if st.session_state.pop("dashboard_pdf_success", False):
        st.success(_t("PDF Created Success"))
    st.download_button(
        _t("Download PDF Report"),
        data=pdf_data,
        file_name=member_report_filename(profile.name),
        mime="application/pdf",
        type="primary",
        width="stretch",
        on_click=_mark_pdf_success,
    )
