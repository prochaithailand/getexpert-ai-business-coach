from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import replace
from typing import Any, Protocol

from models import MemberProfile
from services.progress_service import member_progress_key
from services.supabase_service import get_authenticated_supabase_user, get_supabase_service, run_supabase_sync


class ProfileRepository(Protocol):
    def get(self) -> MemberProfile | None: ...

    def save(self, profile: MemberProfile) -> None: ...


class SessionProfileRepository:
    """Streamlit session adapter; swap for a Supabase repository later."""

    _KEY = "member_profile"
    _REGISTRY_KEY = "member_profiles_by_key"
    _USER_PROFILES_KEY = "member_profiles_by_user"

    def __init__(self, state: MutableMapping[str, Any]) -> None:
        self._state = state

    def get(self) -> MemberProfile | None:
        email = self._authenticated_email()
        if email:
            raw = self._state.get(self._USER_PROFILES_KEY, {}).get(email)
            if raw is not None:
                profile = raw if isinstance(raw, MemberProfile) else MemberProfile.from_dict(raw)
                self._state[self._KEY] = profile.to_dict()
                return profile
            if self._state.get(self._USER_PROFILES_KEY):
                return None
        raw = self._state.get(self._KEY)
        if raw is None:
            return None
        if isinstance(raw, MemberProfile):
            return raw
        return MemberProfile.from_dict(raw)

    def save(self, profile: MemberProfile) -> None:
        current = self.get()
        authenticated_role = str(self._state.get("authenticated_user", {}).get("role", ""))
        if authenticated_role in {"Member", "Leader", "Admin"}:
            profile = replace(profile, role=authenticated_role)
            if authenticated_role in {"Member", "Leader"}:
                profile = replace(
                    profile,
                    team_name=current.team_name if current else "",
                    team_id=current.team_id if current else "",
                    team_leader=current.team_leader if current else "",
                )
        elif profile.role == "Admin" and (not current or current.role != "Admin"):
            profile = replace(profile, role="Member")
        elif profile.role not in {"Member", "Leader", "Admin"}:
            profile = replace(profile, role="Member")
        self._persist(profile)

    def assign_admin_internally(self, profile: MemberProfile) -> None:
        """Privileged system-owner path; this method is never exposed in the member UI."""
        self._persist(replace(profile, role="Admin"))

    def _persist(self, profile: MemberProfile) -> None:
        self._state[self._KEY] = profile.to_dict()
        email = self._authenticated_email()
        if email:
            user_profiles = dict(self._state.get(self._USER_PROFILES_KEY, {}))
            user_profiles[email] = profile.to_dict()
            self._state[self._USER_PROFILES_KEY] = user_profiles
        registry = dict(self._state.get(self._REGISTRY_KEY, {}))
        registry[member_progress_key(profile)] = profile.to_dict()
        self._state[self._REGISTRY_KEY] = registry
        supabase = get_supabase_service(self._state)
        authenticated = get_authenticated_supabase_user(self._state)
        if supabase and authenticated:
            run_supabase_sync(self._state, supabase.save_profile, authenticated, profile)

    def list_all(self) -> list[MemberProfile]:
        registry = dict(self._state.get(self._REGISTRY_KEY, {}))
        current = self.get()
        if current and current.is_complete:
            registry[member_progress_key(current)] = current.to_dict()
        return sorted(
            (MemberProfile.from_dict(raw) for raw in registry.values()),
            key=lambda profile: profile.name.casefold(),
        )

    def list_by_team(self, team_id: str) -> list[MemberProfile]:
        normalized_id = team_id.strip().upper()
        return [
            profile for profile in self.list_all()
            if profile.team_id.strip().upper() == normalized_id
        ]

    def _authenticated_email(self) -> str:
        return str(self._state.get("authenticated_user", {}).get("email", "")).strip().casefold()
