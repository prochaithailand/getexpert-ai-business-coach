from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from models import AppUser, MemberProfile
from services.progress_service import member_progress_key
from services.supabase_service import SupabaseService


AUTH_USER_KEY = "authenticated_user"
USER_STORE_KEY = "prototype_users"
PBKDF2_ITERATIONS = 210_000


class SessionUserStore:
    def __init__(self, state: Any, supabase: SupabaseService | None = None) -> None:
        self.state = state
        self.supabase = supabase

    def register(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str = "Member",
    ) -> AppUser:
        normalized_email = _normalize_email(email)
        if role != "Member":
            raise ValueError("ผู้สมัครใหม่สามารถใช้บทบาทสมาชิกเท่านั้น")
        _validate_registration(normalized_email, password, full_name)
        if self.supabase and self.supabase.enabled:
            payload = self.supabase.sign_up(normalized_email, password, full_name.strip())
            auth_user = payload.get("user", {})
            user = AppUser(normalized_email, full_name.strip(), "Member", "")
            users = dict(self.state.get(USER_STORE_KEY, {}))
            users[normalized_email] = user.to_dict()
            self.state[USER_STORE_KEY] = users
            if payload.get("access_token"):
                authenticated = {
                    **user.public_dict(), "user_id": auth_user.get("id", ""),
                    "access_token": payload.get("access_token", ""),
                    "refresh_token": payload.get("refresh_token", ""),
                }
                self.state[AUTH_USER_KEY] = authenticated
                self.supabase.load_user_data(self.state, authenticated)
            return user
        users = dict(self.state.get(USER_STORE_KEY, {}))
        if normalized_email in users:
            raise ValueError("อีเมลนี้มีบัญชีอยู่แล้ว")
        user = AppUser(
            email=normalized_email,
            full_name=full_name.strip(),
            role="Member",
            password_hash=_hash_password(password),
        )
        users[normalized_email] = user.to_dict()
        self.state[USER_STORE_KEY] = users
        return user

    def authenticate(self, email: str, password: str) -> AppUser | None:
        if self.supabase and self.supabase.enabled:
            authenticated = self.supabase.sign_in(_normalize_email(email), password)
            user = AppUser(
                authenticated["email"], authenticated["full_name"], authenticated["role"], ""
            )
            users = dict(self.state.get(USER_STORE_KEY, {}))
            users[user.email] = user.to_dict()
            self.state[USER_STORE_KEY] = users
            self.state[AUTH_USER_KEY] = authenticated
            self.supabase.load_user_data(self.state, authenticated)
            return user
        user = self.get(email)
        if not user or not _verify_password(password, user.password_hash):
            return None
        self.state[AUTH_USER_KEY] = user.public_dict()
        return user

    def current_user(self) -> AppUser | None:
        authenticated = self.state.get(AUTH_USER_KEY)
        if not authenticated:
            return None
        user = self.get(str(authenticated.get("email", "")))
        if not user:
            self.logout()
            return None
        self.state[AUTH_USER_KEY] = {**dict(authenticated), **user.public_dict()}
        return user

    def logout(self) -> None:
        self.state.pop(AUTH_USER_KEY, None)
        for key in (
            "member_profile", "action_plan", "action_plan_signature", "coach_messages",
            "content_output", "dashboard_pdf_success",
        ):
            self.state.pop(key, None)

    def get(self, email: str) -> AppUser | None:
        raw = self.state.get(USER_STORE_KEY, {}).get(_normalize_email(email))
        return AppUser.from_dict(raw) if raw else None

    def list_users(self) -> list[AppUser]:
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if self.supabase and self.supabase.enabled and authenticated.get("access_token"):
            rows = self.supabase.list_users(authenticated["access_token"])
            users = [
                AppUser(str(row["email"]), str(row.get("full_name", "")), str(row.get("role", "Member")))
                for row in rows
            ]
            cache = dict(self.state.get(USER_STORE_KEY, {}))
            cache.update({user.email: user.to_dict() for user in users})
            self.state[USER_STORE_KEY] = cache
            return sorted(users, key=lambda user: user.full_name.casefold())
        return sorted(
            (AppUser.from_dict(raw) for raw in self.state.get(USER_STORE_KEY, {}).values()),
            key=lambda user: user.full_name.casefold(),
        )

    def list_users_by_role(self, role: str) -> list[AppUser]:
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if self.supabase and self.supabase.enabled and authenticated.get("access_token"):
            rows = self.supabase.list_users_by_role(role, authenticated["access_token"])
            users = [
                AppUser(
                    str(row["email"]),
                    str(row.get("full_name", "")),
                    str(row.get("role", "Member")),
                )
                for row in rows
            ]
            cache = dict(self.state.get(USER_STORE_KEY, {}))
            cache.update({user.email: user.to_dict() for user in users})
            self.state[USER_STORE_KEY] = cache
            return sorted(users, key=lambda user: user.full_name.casefold())
        return [user for user in self.list_users() if user.role == role]

    def promote(self, actor_email: str, target_email: str) -> AppUser:
        actor = self.get(actor_email)
        if not actor or actor.role != "Admin":
            raise PermissionError("คุณไม่มีสิทธิ์เปลี่ยนบทบาทผู้ใช้")
        target = self.get(target_email)
        if not target:
            raise KeyError("ไม่พบบัญชีผู้ใช้")
        next_role = {"Member": "Leader", "Leader": "Admin"}.get(target.role)
        if not next_role:
            raise ValueError("บัญชีนี้เป็นผู้ดูแลระบบอยู่แล้ว")
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if self.supabase and self.supabase.enabled:
            token = str(authenticated.get("access_token", ""))
            if not token:
                raise PermissionError("กรุณาเข้าสู่ระบบใหม่ก่อนเปลี่ยนบทบาท")
            self.supabase.promote_user(target.email, next_role, token)
        promoted = AppUser(target.email, target.full_name, next_role, target.password_hash)
        users = dict(self.state.get(USER_STORE_KEY, {}))
        users[target.email] = promoted.to_dict()
        self.state[USER_STORE_KEY] = users
        user_profiles = dict(self.state.get("member_profiles_by_user", {}))
        raw_profile = user_profiles.get(target.email)
        if raw_profile:
            profile = MemberProfile.from_dict(raw_profile)
            updated_profile = MemberProfile.from_dict({**profile.to_dict(), "role": next_role})
            user_profiles[target.email] = updated_profile.to_dict()
            self.state["member_profiles_by_user"] = user_profiles
            registry = dict(self.state.get("member_profiles_by_key", {}))
            registry[member_progress_key(updated_profile)] = updated_profile.to_dict()
            self.state["member_profiles_by_key"] = registry
        if target.email == actor.email:
            self.state[AUTH_USER_KEY] = promoted.public_dict()
        return promoted

    def set_role(
        self,
        actor_email: str,
        target_email: str,
        next_role: str,
    ) -> AppUser:
        actor = self.get(actor_email)
        if not actor or actor.role != "Admin":
            raise PermissionError("คุณไม่มีสิทธิ์เปลี่ยนบทบาทผู้ใช้")
        if next_role not in {"Member", "Leader", "Partner", "Admin"}:
            raise ValueError("บทบาทไม่ถูกต้อง")
        target = self.get(target_email)
        if not target:
            raise KeyError("ไม่พบบัญชีผู้ใช้")
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if self.supabase and self.supabase.enabled:
            token = str(authenticated.get("access_token", ""))
            if not token:
                raise PermissionError("กรุณาเข้าสู่ระบบใหม่ก่อนเปลี่ยนบทบาท")
            self.supabase.promote_user(target.email, next_role, token)
        updated = AppUser(target.email, target.full_name, next_role, target.password_hash)
        users = dict(self.state.get(USER_STORE_KEY, {}))
        users[target.email] = updated.to_dict()
        self.state[USER_STORE_KEY] = users
        user_profiles = dict(self.state.get("member_profiles_by_user", {}))
        raw_profile = user_profiles.get(target.email)
        if raw_profile:
            profile = MemberProfile.from_dict(raw_profile)
            approval_time = datetime.now(timezone.utc).isoformat()
            updated_profile = MemberProfile.from_dict({
                **profile.to_dict(),
                "role": next_role,
                "partner_status": "approved" if next_role == "Partner" else "",
                "partner_approved_by": actor.email if next_role == "Partner" else "",
                "partner_approved_at": approval_time if next_role == "Partner" else "",
            })
            user_profiles[target.email] = updated_profile.to_dict()
            self.state["member_profiles_by_user"] = user_profiles
            registry = dict(self.state.get("member_profiles_by_key", {}))
            registry.pop(member_progress_key(profile), None)
            registry[member_progress_key(updated_profile)] = updated_profile.to_dict()
            self.state["member_profiles_by_key"] = registry
            if self.supabase and self.supabase.enabled:
                self.supabase.assign_user_to_team(
                    authenticated, target.email, updated_profile, None
                )
        if target.email == actor.email:
            self.state[AUTH_USER_KEY] = {**dict(authenticated), **updated.public_dict()}
        return updated

    def create_admin_internally(self, email: str, password: str, full_name: str) -> AppUser:
        normalized_email = _normalize_email(email)
        _validate_registration(normalized_email, password, full_name)
        existing = self.get(normalized_email)
        if existing:
            return existing
        admin = AppUser(normalized_email, full_name.strip(), "Admin", _hash_password(password))
        users = dict(self.state.get(USER_STORE_KEY, {}))
        users[normalized_email] = admin.to_dict()
        self.state[USER_STORE_KEY] = users
        return admin


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _validate_registration(email: str, password: str, full_name: str) -> None:
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("กรุณาระบุอีเมลให้ถูกต้อง")
    if len(password) < 8:
        raise ValueError("รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร")
    if not full_name.strip():
        raise ValueError("กรุณาระบุชื่อ-นามสกุล")


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (TypeError, ValueError):
        return False
