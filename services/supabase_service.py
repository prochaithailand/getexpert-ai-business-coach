from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from models import ActionItem, AppUser, MemberProfile, Team
from services.progress_service import calculate_plan_progress, member_progress_key


REQUIRED_TABLES = (
    "users", "member_profiles", "teams", "prospects", "workplan_targets",
    "thirty_day_progress", "pp_scores", "content_history", "ai_chat_history",
)


class SupabaseError(RuntimeError):
    pass


class SupabaseService:
    def __init__(
        self,
        url: str,
        anon_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.anon_key = anon_key.strip()
        self.client = client or httpx.Client(timeout=15.0)

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.anon_key)

    def verify_schema(self, access_token: str | None = None) -> tuple[str, ...]:
        missing = []
        for table in REQUIRED_TABLES:
            response = self._request("GET", table, params={"select": "*", "limit": "1"}, access_token=access_token)
            if response.status_code in {404, 406} or "PGRST205" in response.text:
                missing.append(table)
            elif response.status_code >= 400 and response.status_code not in {401, 403}:
                raise SupabaseError(self._error_message(response))
        return tuple(missing)

    def sign_up(self, email: str, password: str, full_name: str) -> dict[str, Any]:
        response = self.client.post(
            f"{self.url}/auth/v1/signup",
            headers=self._headers(),
            json={"email": email, "password": password, "data": {"full_name": full_name}},
        )
        self._raise_for_error(response)
        return response.json()

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        response = self.client.post(
            f"{self.url}/auth/v1/token",
            params={"grant_type": "password"},
            headers=self._headers(),
            json={"email": email, "password": password},
        )
        self._raise_for_error(response)
        payload = response.json()
        auth_user = payload.get("user", {})
        token = str(payload.get("access_token", ""))
        profile_rows = self.select("users", {"email": f"eq.{email.casefold()}"}, token)
        role_row = profile_rows[0] if profile_rows else {}
        return {
            "email": email.casefold(),
            "full_name": role_row.get("full_name") or auth_user.get("user_metadata", {}).get("full_name") or email,
            "role": role_row.get("role", "Member"),
            "user_id": auth_user.get("id", ""),
            "access_token": token,
            "refresh_token": payload.get("refresh_token", ""),
        }

    def list_users(self, access_token: str) -> list[dict[str, Any]]:
        return self.select("users", {}, access_token)

    def list_users_by_role(self, role: str, access_token: str) -> list[dict[str, Any]]:
        return self.select(
            "users",
            {"role": f"eq.{role}", "order": "full_name.asc"},
            access_token,
        )

    def promote_user(self, target_email: str, next_role: str, access_token: str) -> None:
        response = self._request(
            "PATCH", "users", params={"email": f"eq.{target_email.casefold()}"},
            json={"role": next_role, "updated_at": _now()}, access_token=access_token,
        )
        self._raise_for_error(response)

    def select(
        self,
        table: str,
        filters: dict[str, str] | None = None,
        access_token: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {"select": "*", **(filters or {})}
        response = self._request("GET", table, params=params, access_token=access_token)
        self._raise_for_error(response)
        return list(response.json())

    def upsert(
        self,
        table: str,
        rows: dict[str, Any] | list[dict[str, Any]],
        conflict: str,
        access_token: str,
    ) -> None:
        response = self._request(
            "POST", table, params={"on_conflict": conflict}, json=rows, access_token=access_token,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        self._raise_for_error(response)

    def delete(self, table: str, filters: dict[str, str], access_token: str) -> None:
        response = self._request("DELETE", table, params=filters, access_token=access_token)
        self._raise_for_error(response)

    def load_teams(self, state: Any, authenticated: dict[str, Any]) -> None:
        token = str(authenticated.get("access_token", ""))
        if not token:
            return
        teams = self.select("teams", {}, token)
        state["teams"] = {
            str(row["team_id"]).strip().upper(): Team.from_dict({
                **row.get("team_data", {}),
                "team_id": str(row["team_id"]).strip().upper(),
            }).to_dict()
            for row in teams if row.get("team_id") and row.get("team_data")
        }

    def load_user_data(self, state: Any, authenticated: dict[str, Any]) -> None:
        from services.workplan_service import create_default_workplan

        email = str(authenticated["email"]).casefold()
        token = str(authenticated.get("access_token", ""))
        if not token:
            return
        self.load_teams(state, authenticated)
        team_objects = {
            team_id: Team.from_dict(team_data)
            for team_id, team_data in state.get("teams", {}).items()
        }
        profile_rows = self.select("member_profiles", {}, token)
        if not any(str(row.get("email", "")).casefold() == email for row in profile_rows):
            assigned_team = next(
                (
                    team
                    for team in team_objects.values()
                    if (
                        str(authenticated.get("role", "")) == "Leader"
                        and team.leader_email.casefold() == email
                    )
                ),
                None,
            )
            if not assigned_team:
                return
            initial_profile = MemberProfile(
                name=str(authenticated.get("full_name", "")),
                role=str(authenticated.get("role", "Member")),
                team_name=assigned_team.name if assigned_team else "",
                team_id=assigned_team.team_id if assigned_team else "",
                team_leader=assigned_team.leader if assigned_team else "",
            )
            self.upsert("member_profiles", {
                "email": email,
                "team_id": initial_profile.team_id or None,
                "profile_data": initial_profile.to_dict(),
                "updated_at": _now(),
            }, "email", token)
            profile_rows = self.select("member_profiles", {}, token)
        state["member_profiles_by_user"] = {}
        state["member_profiles_by_key"] = {}
        state.setdefault("workplan_by_member", {})
        state.setdefault("plan_completion_by_member", {})
        state.setdefault("pp_scores_by_member", {})
        for row in profile_rows:
            row_email = str(row.get("email", "")).casefold()
            profile = MemberProfile.from_dict(row.get("profile_data", {}))
            if row_email == email:
                profile = replace(profile, role=str(authenticated.get("role", profile.role)))
            canonical_team_id = str(row.get("team_id") or "").strip().upper()
            recovered_leader_team = (
                row_email == email
                and profile.role == "Leader"
                and not canonical_team_id
            )
            if recovered_leader_team:
                assigned_team = next(
                    (
                        team
                        for team in team_objects.values()
                        if team.leader_email.casefold() == email
                    ),
                    None,
                )
                canonical_team_id = assigned_team.team_id if assigned_team else ""
            canonical_team = team_objects.get(canonical_team_id)
            if canonical_team:
                profile = replace(
                    profile, team_id=canonical_team.team_id,
                    team_name=canonical_team.name, team_leader=canonical_team.leader,
                )
                if recovered_leader_team:
                    self.upsert("member_profiles", {
                        "email": email,
                        "team_id": canonical_team.team_id,
                        "profile_data": profile.to_dict(),
                        "updated_at": _now(),
                    }, "email", token)
            elif not canonical_team_id:
                profile = replace(profile, team_id="", team_name="", team_leader="")
            key = member_progress_key(profile)
            state["member_profiles_by_user"][row_email] = profile.to_dict()
            state["member_profiles_by_key"][key] = profile.to_dict()
            if row_email == email:
                state["member_profile"] = profile.to_dict()
            workplan = create_default_workplan()
            workplan["contacts"] = [
                deepcopy(item.get("prospect_data", {}))
                for item in self.select("prospects", {"email": f"eq.{row_email}"}, token)
            ]
            for target in self.select("workplan_targets", {"email": f"eq.{row_email}"}, token):
                target_type = target.get("target_type")
                week = int(target.get("week", 0))
                if target_type in workplan["goals"] and 1 <= week <= 12:
                    workplan["goals"][target_type][week - 1] = {
                        "week": week,
                        "target": float(target.get("target", 0) or 0),
                        "actual": float(target.get("actual", 0) or 0),
                    }
            state["workplan_by_member"][key] = workplan
            progress_rows = self.select(
                "thirty_day_progress", {"email": f"eq.{row_email}"}, token
            )
            state["plan_completion_by_member"][key] = {
                str(item["day"]): bool(item.get("completed", False)) for item in progress_rows
            }
            score_rows = self.select("pp_scores", {"email": f"eq.{row_email}"}, token)
            if score_rows:
                state["pp_scores_by_member"][key] = int(score_rows[0].get("pp_score", 0))
            if row_email == email:
                saved_items = sorted(
                    (item for item in progress_rows if item.get("plan_item")),
                    key=lambda item: int(item.get("day", 0)),
                )
                if saved_items:
                    state["action_plan"] = [
                        ActionItem.from_dict(item["plan_item"]) for item in saved_items
                    ]
                    state["action_plan_signature"] = tuple(
                        saved_items[0].get("profile_signature", [])
                    )
                    state["action_plan_persisted_signature"] = state["action_plan_signature"]

        chats = self.select(
            "ai_chat_history", {"email": f"eq.{email}", "chat_type": "eq.member"}, token
        )
        if chats:
            state["coach_messages"] = [
                {"role": row["role"], "content": row["content"], "sources": row.get("sources", [])}
                for row in sorted(chats, key=lambda item: item.get("created_at", ""))
            ]
        team_chats = self.select(
            "ai_chat_history", {"email": f"eq.{email}", "chat_type": "eq.team"}, token
        )
        by_team: dict[str, list[dict[str, str]]] = {}
        for row in sorted(team_chats, key=lambda item: item.get("created_at", "")):
            if row.get("team_id"):
                by_team.setdefault(str(row["team_id"]), []).append(
                    {"role": row["role"], "content": row["content"]}
                )
        if by_team:
            state["team_coach_messages_by_team"] = by_team
        content_rows = self.select("content_history", {"email": f"eq.{email}"}, token)
        state["content_history"] = sorted(content_rows, key=lambda item: item.get("created_at", ""))

    def save_profile(self, authenticated: dict[str, Any], profile: MemberProfile) -> None:
        self.upsert("member_profiles", {
            "email": authenticated["email"], "team_id": profile.team_id or None,
            "profile_data": profile.to_dict(), "updated_at": _now(),
        }, "email", authenticated["access_token"])

    def save_team(self, authenticated: dict[str, Any], team: Team) -> None:
        self.upsert("teams", {
            "team_id": team.team_id, "team_data": team.to_dict(),
            "updated_by": authenticated["email"], "updated_at": _now(),
        }, "team_id", authenticated["access_token"])

    def save_team_invite(
        self,
        authenticated: dict[str, Any],
        team_id: str,
        invite_code: str,
    ) -> None:
        response = self.client.post(
            f"{self.url}/rest/v1/rpc/getexpert_set_team_invite",
            headers=self._headers(authenticated["access_token"]),
            json={"target_team_id": team_id, "new_invite_code": invite_code},
        )
        self._raise_for_error(response)

    def remove_team_member(
        self,
        authenticated: dict[str, Any],
        team_id: str,
        member_email: str,
    ) -> None:
        response = self.client.post(
            f"{self.url}/rest/v1/rpc/getexpert_remove_team_member",
            headers=self._headers(authenticated["access_token"]),
            json={
                "target_team_id": team_id,
                "target_member_email": member_email.casefold(),
            },
        )
        self._raise_for_error(response)

    def assign_user_to_team(
        self,
        authenticated: dict[str, Any],
        target_email: str,
        profile: MemberProfile,
        role: str | None = None,
    ) -> None:
        token = authenticated["access_token"]
        normalized_email = target_email.casefold()
        if role:
            response = self._request(
                "PATCH", "users", params={"email": f"eq.{normalized_email}"},
                json={"role": role, "updated_at": _now()}, access_token=token,
            )
            self._raise_for_error(response)
        self.upsert("member_profiles", {
            "email": normalized_email,
            "team_id": profile.team_id or None,
            "profile_data": profile.to_dict(),
            "updated_at": _now(),
        }, "email", token)

    def delete_team(self, authenticated: dict[str, Any], team_id: str) -> None:
        self.delete("teams", {"team_id": f"eq.{team_id}"}, authenticated["access_token"])

    def rename_team(self, authenticated: dict[str, Any], original_team_id: str, team: Team) -> None:
        self.save_team(authenticated, team)
        response = self._request(
            "PATCH", "member_profiles", params={"team_id": f"eq.{original_team_id}"},
            json={"team_id": team.team_id, "updated_at": _now()},
            access_token=authenticated["access_token"],
        )
        self._raise_for_error(response)
        self.delete_team(authenticated, original_team_id)

    def save_workplan(self, authenticated: dict[str, Any], workplan: dict[str, Any]) -> None:
        email, token = authenticated["email"], authenticated["access_token"]
        self.delete("prospects", {"email": f"eq.{email}"}, token)
        prospects = [
            {"email": email, "prospect_id": item["id"], "prospect_data": item, "updated_at": _now()}
            for item in workplan.get("contacts", [])
        ]
        if prospects:
            self.upsert("prospects", prospects, "email,prospect_id", token)
        self.delete("workplan_targets", {"email": f"eq.{email}"}, token)
        targets = [
            {"email": email, "target_type": target_type, "week": row["week"],
             "target": row.get("target", 0), "actual": row.get("actual", 0), "updated_at": _now()}
            for target_type, rows in workplan.get("goals", {}).items() for row in rows
        ]
        if targets:
            self.upsert("workplan_targets", targets, "email,target_type,week", token)

    def save_progress(self, authenticated: dict[str, Any], statuses: dict[str, bool]) -> None:
        email, token = authenticated["email"], authenticated["access_token"]
        rows = [
            {"email": email, "day": day, "completed": bool(statuses.get(str(day), False)), "updated_at": _now()}
            for day in range(1, 31)
        ]
        self.upsert("thirty_day_progress", rows, "email,day", token)
        summary = calculate_plan_progress(statuses)
        self.upsert("pp_scores", {
            "email": email, "pp_score": summary.pp_score, "updated_at": _now(),
        }, "email", token)

    def save_action_plan(
        self,
        authenticated: dict[str, Any],
        plan: list[ActionItem],
        profile_signature: tuple[Any, ...],
    ) -> None:
        email, token = authenticated["email"], authenticated["access_token"]
        existing = self.select("thirty_day_progress", {"email": f"eq.{email}"}, token)
        statuses = {int(row["day"]): bool(row.get("completed", False)) for row in existing}
        rows = [
            {
                "email": email,
                "day": item.day,
                "completed": statuses.get(item.day, False),
                "plan_item": item.to_dict(),
                "profile_signature": list(profile_signature),
                "updated_at": _now(),
            }
            for item in plan
        ]
        self.upsert("thirty_day_progress", rows, "email,day", token)

    def save_content(self, authenticated: dict[str, Any], channel: str, content: str) -> None:
        self.upsert("content_history", {
            "id": str(uuid4()), "email": authenticated["email"], "channel": channel,
            "content": content, "created_at": _now(),
        }, "id", authenticated["access_token"])

    def save_chat_message(
        self, authenticated: dict[str, Any], role: str, content: str,
        sources: list[str] | None = None, chat_type: str = "member", team_id: str | None = None,
    ) -> None:
        self.upsert("ai_chat_history", {
            "id": str(uuid4()), "email": authenticated["email"], "role": role,
            "content": content, "sources": sources or [], "chat_type": chat_type,
            "team_id": team_id, "created_at": _now(),
        }, "id", authenticated["access_token"])

    def _request(
        self, method: str, table: str, params: dict[str, str] | None = None,
        json: Any = None, access_token: str | None = None, prefer: str | None = None,
    ) -> httpx.Response:
        headers = self._headers(access_token)
        if prefer:
            headers["Prefer"] = prefer
        return self.client.request(
            method, f"{self.url}/rest/v1/{table}", params=params, json=json, headers=headers,
        )

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        return {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {access_token or self.anon_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            return str(payload.get("message") or payload.get("msg") or payload.get("error_description") or payload)
        except Exception:
            return response.text or f"HTTP {response.status_code}"

    def _raise_for_error(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise SupabaseError(self._error_message(response))


def get_supabase_service(state: Any) -> SupabaseService | None:
    service = state.get("_supabase_service")
    return service if isinstance(service, SupabaseService) and service.enabled else None


def get_authenticated_supabase_user(state: Any) -> dict[str, Any] | None:
    user = state.get("authenticated_user")
    return user if user and user.get("access_token") else None


def run_supabase_sync(state: Any, operation: Any, *args: Any, **kwargs: Any) -> bool:
    try:
        operation(*args, **kwargs)
        state.pop("supabase_sync_error", None)
        return True
    except (SupabaseError, httpx.HTTPError) as error:
        state["supabase_sync_error"] = f"ไม่สามารถบันทึกข้อมูลไปยัง Supabase ได้: {error}"
        return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
