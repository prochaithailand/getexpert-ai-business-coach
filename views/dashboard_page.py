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
from translations import translate


def _language() -> str:
    return str(st.session_state.get("language", "th"))


def _t(key: str, **values: object) -> str:
    text = translate(key, _language())
    return text.format(**values) if values else text


def render_member_dashboard(profile: MemberProfile | None, coach: CoachService) -> None:
    brand = st.session_state.get("_active_brand", {})
    title = "TG Life Member Dashboard" if brand.get("key") == "tglife" else _t("Dashboard")
    st.title(title)
    st.markdown(
        f"<p class='section-lead'>{_t('Dashboard Page Description')}</p>",
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
    plan = snapshot["plan"]
    goals = snapshot["goals"]
    charts = (
        (_t("30-Day Plan Page Title"), plan["total"], plan["completed"], _t("Days Unit")),
        (_t("Sponsor Goal"), goals["sponsor"]["target"], goals["sponsor"]["actual"], _t("People Unit")),
        (_t("Team Points Goal"), goals["team_points"]["target"], goals["team_points"]["actual"], _t("Points Unit")),
        (_t("Income Goal"), goals["income"]["target"], goals["income"]["actual"], _t("Currency Baht")),
    )
    columns = st.columns(2)
    for index, (title, target, actual, unit) in enumerate(charts):
        with columns[index % 2]:
            st.markdown(f"**{title} ({unit})**")
            st.vega_lite_chart(
                {
                    "values": [
                        {_t("Chart Item Field"): _t("Target"), _t("Chart Value Field"): float(target)},
                        {_t("Chart Item Field"): _t("Actual Result"), _t("Chart Value Field"): float(actual)},
                    ]
                },
                {
                    "height": 230,
                    "mark": {"type": "bar", "cornerRadiusTopLeft": 6, "cornerRadiusTopRight": 6},
                    "encoding": {
                        "x": {
                            "field": _t("Chart Item Field"),
                            "type": "nominal",
                            "axis": {"labelAngle": 0, "title": None},
                        },
                        "y": {
                            "field": _t("Chart Value Field"),
                            "type": "quantitative",
                            "axis": {"title": unit},
                        },
                        "color": {
                            "field": _t("Chart Item Field"),
                            "type": "nominal",
                            "scale": {
                                "domain": [_t("Target"), _t("Actual Result")],
                                "range": ["#0B2E59", "#F59E0B"],
                            },
                            "legend": {"title": _t("Legend")},
                        },
                        "tooltip": [
                            {"field": _t("Chart Item Field"), "type": "nominal", "title": _t("Chart Item Field")},
                            {"field": _t("Chart Value Field"), "type": "quantitative", "title": unit, "format": ",.0f"},
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
