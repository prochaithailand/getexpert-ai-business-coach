from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import secrets
from typing import Any

from models import AppUser, MemberProfile, Team
from services.auth_service import USER_STORE_KEY
from services.progress_service import member_progress_key
from services.permissions import can_access_team_management
from services.supabase_service import get_authenticated_supabase_user, get_supabase_service, run_supabase_sync


class SessionTeamRepository:
    KEY = "teams"

    def __init__(self, state: Any) -> None:
        self.state = state

    def list(self) -> list[Team]:
        return sorted(
            (Team.from_dict(team) for team in self.state.get(self.KEY, {}).values()),
            key=lambda team: (team.name.casefold(), team.team_id),
        )

    def get(self, team_id: str) -> Team | None:
        raw = self.state.get(self.KEY, {}).get(_team_id(team_id))
        return Team.from_dict(raw) if raw else None

    def create(self, team: Team) -> Team:
        normalized = normalize_team(team)
        store = dict(self.state.get(self.KEY, {}))
        if normalized.team_id in store:
            raise ValueError("รหัสทีมนี้มีอยู่ในระบบแล้ว")
        store[normalized.team_id] = normalized.to_dict()
        self.state[self.KEY] = store
        self._persist_team(normalized)
        return normalized

    def update(self, original_team_id: str, team: Team) -> Team:
        original_id = _team_id(original_team_id)
        normalized = normalize_team(team)
        store = dict(self.state.get(self.KEY, {}))
        if original_id not in store:
            raise KeyError("ไม่พบทีมที่ต้องการแก้ไข")
        if normalized.team_id != original_id and normalized.team_id in store:
            raise ValueError("รหัสทีมนี้มีอยู่ในระบบแล้ว")
        del store[original_id]
        store[normalized.team_id] = normalized.to_dict()
        self.state[self.KEY] = store
        self._sync_current_profile(original_id, normalized)
        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if supabase and authenticated and normalized.team_id != original_id:
            run_supabase_sync(
                self.state, supabase.rename_team, authenticated, original_id, normalized
            )
        else:
            self._persist_team(normalized)
        return normalized

    def delete(self, team_id: str) -> None:
        normalized_id = _team_id(team_id)
        store = dict(self.state.get(self.KEY, {}))
        if normalized_id not in store:
            raise KeyError("ไม่พบทีมที่ต้องการลบ")
        del store[normalized_id]
        self.state[self.KEY] = store
        self._sync_current_profile(normalized_id, None)
        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if supabase and authenticated:
            run_supabase_sync(self.state, supabase.delete_team, authenticated, normalized_id)

    def assign_leader(self, team_id: str, user: AppUser) -> Team:
        if user.role == "Admin":
            raise ValueError("ไม่สามารถกำหนดบัญชีผู้ดูแลระบบเป็นหัวหน้าทีม")
        team = self.get(team_id)
        if not team:
            raise KeyError("ไม่พบทีมที่ต้องการกำหนดหัวหน้า")
        updated_team = self.update(
            team.team_id,
            Team(
                team.name,
                team.team_id,
                user.full_name,
                team.primary_sponsor,
                team.notes,
                user.email.casefold(),
                team.invite_code,
            ),
        )
        self._assign_user(updated_team, user, "Leader")
        return updated_team

    def assign_members(self, team_id: str, users: list[AppUser]) -> list[MemberProfile]:
        team = self.get(team_id)
        if not team:
            raise KeyError("ไม่พบทีมที่ต้องการกำหนดสมาชิก")
        if any(user.role == "Admin" for user in users):
            raise ValueError("ไม่สามารถกำหนดบัญชีผู้ดูแลระบบเป็นสมาชิกทีม")
        return [self._assign_user(team, user, None) for user in users]

    def remove_member(self, team_id: str, user: AppUser) -> MemberProfile:
        normalized_team_id = _team_id(team_id)
        profile = self.profile_for_user(user.email)
        if not profile or _team_id(profile.team_id) != normalized_team_id:
            raise ValueError("สมาชิกคนนี้ไม่ได้อยู่ในทีมที่เลือก")
        if user.role != "Member" or profile.role != "Member":
            raise ValueError("สามารถนำออกจากทีมได้เฉพาะบัญชีสมาชิก")
        cleared = replace(
            profile,
            team_name="",
            team_id="",
            team_leader="",
            invited_by="",
            joined_at="",
            role="Member",
        )
        self._store_assigned_profile(user, cleared, "Member")
        return cleared

    def remove_member_as_leader(
        self,
        team_id: str,
        user: AppUser,
        leader: AppUser,
    ) -> MemberProfile:
        team = self.get(team_id)
        if not team:
            raise KeyError("ไม่พบทีมที่ต้องการจัดการ")
        if (
            leader.role != "Leader"
            or not team.leader_email
            or team.leader_email.casefold() != leader.email.casefold()
        ):
            raise PermissionError("คุณไม่มีสิทธิ์นำสมาชิกออกจากทีมนี้")
        profile = self.profile_for_user(user.email)
        if (
            not profile
            or profile.role != "Member"
            or _team_id(profile.team_id) != team.team_id
        ):
            raise ValueError("สมาชิกคนนี้ไม่ได้อยู่ในทีมของคุณ")
        cleared = replace(
            profile,
            team_name="",
            team_id="",
            team_leader="",
            invited_by="",
            joined_at="",
            role="Member",
        )
        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if supabase and authenticated:
            saved = run_supabase_sync(
                self.state,
                supabase.remove_team_member,
                authenticated,
                team.team_id,
                user.email,
            )
            if not saved:
                raise RuntimeError("ไม่สามารถนำสมาชิกออกจากทีมได้ กรุณาลองใหม่อีกครั้ง")
        self._store_assigned_profile(user, cleared, "Member", persist=False)
        return cleared

    def profile_for_user(self, email: str) -> MemberProfile | None:
        raw = self.state.get("member_profiles_by_user", {}).get(email.casefold())
        return MemberProfile.from_dict(raw) if raw else None

    def generate_invite_code(self, team_id: str, leader: AppUser) -> Team:
        team = self.get(team_id)
        if not team:
            raise KeyError("ไม่พบทีมที่ต้องการสร้างลิงก์คำเชิญ")
        raw_profile = self.state.get("member_profile", {})
        current_profile = (
            raw_profile
            if isinstance(raw_profile, MemberProfile)
            else MemberProfile.from_dict(raw_profile)
        )
        assigned_by_profile = _team_id(current_profile.team_id) == team.team_id
        if leader.role not in {"Leader", "Admin"} or (
            leader.role != "Admin"
            and (
            team.leader_email
            and team.leader_email.casefold() != leader.email.casefold()
            )
        ) or (
            leader.role != "Admin"
            and not team.leader_email
            and not assigned_by_profile
        ):
            raise PermissionError("คุณไม่มีสิทธิ์สร้างลิงก์คำเชิญสำหรับทีมนี้")
        invite_code = team.invite_code or (
            secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12].upper()
        )
        updated = replace(
            team,
            leader_email=team.leader_email or (
                leader.email.casefold() if leader.role == "Leader" else ""
            ),
            invite_code=invite_code,
        )
        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if supabase and authenticated:
            saved = run_supabase_sync(
                self.state,
                supabase.save_team_invite,
                authenticated,
                team.team_id,
                invite_code,
            )
            if not saved:
                raise RuntimeError("ไม่สามารถบันทึกลิงก์คำเชิญได้ กรุณาลองใหม่อีกครั้ง")
        store = dict(self.state.get(self.KEY, {}))
        store[team.team_id] = updated.to_dict()
        self.state[self.KEY] = store
        return updated

    def find_by_invite_code(self, invite_code: str) -> Team | None:
        normalized = invite_code.strip().casefold()
        if not normalized:
            return None
        return next(
            (team for team in self.list() if team.invite_code.casefold() == normalized),
            None,
        )

    def join_with_invite(self, invite_code: str, user: AppUser) -> MemberProfile:
        if user.role != "Member":
            raise PermissionError("คำเชิญเข้าร่วมทีมใช้ได้สำหรับบัญชีสมาชิกเท่านั้น")
        team = self.find_by_invite_code(invite_code)
        if not team:
            raise KeyError("ไม่พบคำเชิญเข้าร่วมทีม หรือคำเชิญไม่ถูกต้อง")
        assigned = self._assign_user(team, user, "Member")
        joined = replace(
            assigned,
            sponsor=team.leader_email or assigned.sponsor,
            invited_by=team.leader_email,
            joined_at=datetime.now(timezone.utc).isoformat(),
            role="Member",
        )
        self._store_assigned_profile(user, joined, "Member")
        return joined

    def ensure_profile_team(self, profile: MemberProfile | None) -> Team | None:
        if not profile or not profile.team_id:
            return None
        existing = self.get(profile.team_id)
        if existing:
            return existing
        if not profile.team_name:
            return None
        return self.create(
            Team(
                name=profile.team_name,
                team_id=profile.team_id,
                leader=profile.team_leader or "ยังไม่ระบุ",
                primary_sponsor=profile.sponsor,
                notes="นำเข้าจากโปรไฟล์สมาชิกเดิม",
            )
        )

    def _sync_current_profile(self, original_team_id: str, team: Team | None) -> None:
        raw_profile = self.state.get("member_profile")
        if raw_profile:
            profile = raw_profile if isinstance(raw_profile, MemberProfile) else MemberProfile.from_dict(raw_profile)
            if _team_id(profile.team_id) == original_team_id:
                updated = replace(
                    profile,
                    team_name=team.name if team else "",
                    team_id=team.team_id if team else "",
                    team_leader=team.leader if team else "",
                )
                self.state["member_profile"] = updated.to_dict()
        registry = dict(self.state.get("member_profiles_by_key", {}))
        changed = False
        for member_key, raw in registry.items():
            registered = raw if isinstance(raw, MemberProfile) else MemberProfile.from_dict(raw)
            if _team_id(registered.team_id) != original_team_id:
                continue
            registry[member_key] = replace(
                registered,
                team_name=team.name if team else "",
                team_id=team.team_id if team else "",
                team_leader=team.leader if team else "",
            ).to_dict()
            changed = True
        if changed:
            self.state["member_profiles_by_key"] = registry
        user_profiles = dict(self.state.get("member_profiles_by_user", {}))
        user_profiles_changed = False
        for email, raw in user_profiles.items():
            registered = raw if isinstance(raw, MemberProfile) else MemberProfile.from_dict(raw)
            if _team_id(registered.team_id) != original_team_id:
                continue
            user_profiles[email] = replace(
                registered,
                team_name=team.name if team else "",
                team_id=team.team_id if team else "",
                team_leader=team.leader if team else "",
            ).to_dict()
            user_profiles_changed = True
        if user_profiles_changed:
            self.state["member_profiles_by_user"] = user_profiles

    def _persist_team(self, team: Team) -> None:
        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if supabase and authenticated:
            run_supabase_sync(self.state, supabase.save_team, authenticated, team)

    def _assign_user(
        self,
        team: Team,
        user: AppUser,
        role: str | None,
    ) -> MemberProfile:
        email = user.email.casefold()
        raw = self.state.get("member_profiles_by_user", {}).get(email)
        profile = MemberProfile.from_dict(raw) if raw else MemberProfile(
            name=user.full_name,
            occupation="",
            role=user.role,
        )
        current_team_id = _team_id(profile.team_id)
        if user.role == "Member" and current_team_id and current_team_id != team.team_id:
            raise ValueError("สมาชิกคนนี้อยู่ในทีมอื่นแล้ว กรุณาลบออกจากทีมเดิมก่อน")
        assigned = replace(
            profile,
            team_name=team.name,
            team_id=team.team_id,
            team_leader=team.leader,
            role=role or profile.role,
        )
        self._store_assigned_profile(user, assigned, role)
        return assigned

    def _store_assigned_profile(
        self,
        user: AppUser,
        assigned: MemberProfile,
        role: str | None,
        persist: bool = True,
    ) -> None:
        email = user.email.casefold()
        raw = self.state.get("member_profiles_by_user", {}).get(email)
        previous = MemberProfile.from_dict(raw) if raw else None
        profiles_by_user = dict(self.state.get("member_profiles_by_user", {}))
        profiles_by_user[email] = assigned.to_dict()
        self.state["member_profiles_by_user"] = profiles_by_user

        registry = dict(self.state.get("member_profiles_by_key", {}))
        if previous:
            registry.pop(member_progress_key(previous), None)
        registry[member_progress_key(assigned)] = assigned.to_dict()
        self.state["member_profiles_by_key"] = registry

        users = dict(self.state.get(USER_STORE_KEY, {}))
        assigned_user = replace(user, role=role or assigned.role)
        users[email] = assigned_user.to_dict()
        self.state[USER_STORE_KEY] = users
        if str(self.state.get("authenticated_user", {}).get("email", "")).casefold() == email:
            self.state["member_profile"] = assigned.to_dict()

        supabase = get_supabase_service(self.state)
        authenticated = get_authenticated_supabase_user(self.state)
        if persist and supabase and authenticated:
            run_supabase_sync(
                self.state,
                supabase.assign_user_to_team,
                authenticated,
                email,
                assigned,
                role,
            )


def normalize_team(team: Team) -> Team:
    name = team.name.strip()
    team_id = _team_id(team.team_id)
    leader = team.leader.strip()
    if not name:
        raise ValueError("กรุณาระบุชื่อทีม")
    if not team_id:
        raise ValueError("กรุณาระบุรหัสทีม")
    if not leader:
        raise ValueError("กรุณาระบุหัวหน้าทีม")
    return Team(
        name=name,
        team_id=team_id,
        leader=leader,
        primary_sponsor=team.primary_sponsor.strip(),
        notes=team.notes.strip(),
        leader_email=team.leader_email.strip().casefold(),
        invite_code=team.invite_code.strip(),
    )


def resolve_profile_team(state: Any, profile: MemberProfile) -> Team | None:
    if not profile.team_id:
        return None
    return SessionTeamRepository(state).get(profile.team_id)


def can_manage_teams(profile: MemberProfile | None) -> bool:
    return can_access_team_management(profile)


def _team_id(value: str) -> str:
    return value.strip().upper()
