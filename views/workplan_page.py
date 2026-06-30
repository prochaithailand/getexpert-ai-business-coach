from __future__ import annotations

from typing import Any

import streamlit as st

from models import MemberProfile
from services.progress_service import member_progress_key
from services.workplan_service import (
    SessionWorkplanRepository,
    goal_summary,
    replace_weekly_goals,
    weekly_rows_with_percentage,
)
from translations import translate


def _language() -> str:
    return str(st.session_state.get("language", "th"))


def _t(key: str, **values: object) -> str:
    text = translate(key, _language())
    return text.format(**values) if values else text


def _records(data: Any) -> list[dict[str, Any]]:
    """Normalize Streamlit's supported table return types to row dictionaries."""
    if hasattr(data, "to_dict"):
        return data.to_dict("records")
    return list(data)


def _navigate_to_prospects() -> None:
    st.session_state["main_navigation"] = "ผู้มุ่งหวัง"


def render_business_workplan(profile: MemberProfile | None) -> None:
    st.title(_t("Workplan"))
    st.markdown(
        f"<p class='section-lead'>{_t('Workplan Page Description')}</p>",
        unsafe_allow_html=True,
    )
    if not profile or not profile.is_complete:
        st.warning(_t("Workplan Profile Required"))
        return

    repository = SessionWorkplanRepository(st.session_state)
    workplan = repository.get(profile)
    _render_dashboard(workplan)
    st.info(_t("Workplan Prospect Info"))
    st.button(
        _t("Go To Prospects"),
        type="primary",
        on_click=_navigate_to_prospects,
        width="stretch",
    )
    tabs = st.tabs((_t("Sponsor Goal"), _t("Team Points Goal"), _t("Income Goal")))
    with tabs[0]:
        _render_weekly_goal(profile, repository, workplan, "sponsor", _t("Sponsor Goal"), _t("People Unit"))
    with tabs[1]:
        _render_weekly_goal(profile, repository, workplan, "team_points", _t("Team Points Goal"), _t("Points Unit"))
    with tabs[2]:
        _render_weekly_goal(profile, repository, workplan, "income", _t("Income Goal"), _t("Currency Baht"))


def _render_dashboard(workplan: dict[str, Any]) -> None:
    sponsor = goal_summary(workplan["goals"]["sponsor"])
    points = goal_summary(workplan["goals"]["team_points"])
    income = goal_summary(workplan["goals"]["income"])
    cards = (
        (_t("Sponsor Completion"), f"{sponsor['percentage']:.0f}%"),
        (_t("Team Points Completion"), f"{points['percentage']:.0f}%"),
        (_t("Income Completion"), f"{income['percentage']:.0f}%"),
    )
    columns = st.columns(3)
    for column, (label, value) in zip(columns, cards):
        column.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    st.write("")

def _render_weekly_goal(
    profile: MemberProfile,
    repository: SessionWorkplanRepository,
    workplan: dict[str, Any],
    goal_key: str,
    title: str,
    unit: str,
) -> None:
    st.subheader(title)
    rows = weekly_rows_with_percentage(workplan["goals"][goal_key])
    summary = goal_summary(rows)
    first, second, third = st.columns(3)
    first.metric(f"{_t('Total Target')} ({unit})", f"{summary['target']:,.0f}")
    second.metric(f"{_t('Actual Result')} ({unit})", f"{summary['actual']:,.0f}")
    third.metric(_t("Completion"), f"{summary['percentage']:.0f}%")
    st.progress(summary["percentage"] / 100, text=f"{_t('Total Completion')} {summary['percentage']:.0f}%")

    edited = st.data_editor(
        rows,
        key=f"workplan_goal_{member_progress_key(profile)}_{goal_key}",
        hide_index=True,
        width="stretch",
        column_config={
            "week": st.column_config.NumberColumn(_t("Week Number"), format="%d"),
            "target": st.column_config.NumberColumn(f"{_t('Target')} ({unit})", min_value=0, step=1),
            "actual": st.column_config.NumberColumn(f"{_t('Actual Result')} ({unit})", min_value=0, step=1),
            "percentage": st.column_config.ProgressColumn(f"{_t('Completion')} (%)", min_value=0, max_value=100, format="%.0f%%"),
        },
        disabled=("week", "percentage"),
    )
    if st.button(f"{_t('Save')} {title}", key=f"save_{goal_key}", type="primary", width="stretch"):
        updated = replace_weekly_goals(workplan, goal_key, _records(edited))
        repository.save(profile, updated)
        st.rerun()
