from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from models import AppUser, MemberProfile
from services.progress_service import member_progress_key
from services.supabase_service import SupabaseService
from services.subscription_service import (
    apply_subscription_action,
    effective_subscription_status,
    normalize_subscription_user,
    start_trial,
)


AUTH_USER_KEY = "authenticated_user"
USER_STORE_KEY = "prototype_users"
PBKDF2_ITERATIONS = 210_000


def recovery_params_from_query(query_params: object) -> tuple[str, str]:
    get_value = getattr(query_params, "get", lambda _key, _default="": "")
    recovery_type = str(
        get_value("type", "") or get_value("recovery_type", "")
    ).strip()
    access_token = str(
        get_value("access_token", "")
        or get_value("recovery_access_token", "")
    ).strip()
    return recovery_type, access_token


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
            user = start_trial(AppUser(
                normalized_email, full_name.strip(), "Member", "",
                subscription_status="pending_payment", subscription_plan="Member",
            ))
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
        user = start_trial(AppUser(
            email=normalized_email,
            full_name=full_name.strip(),
            role="Member",
            password_hash=_hash_password(password),
            subscription_status="pending_payment",
            subscription_plan="Member",
        ))
        users[normalized_email] = user.to_dict()
        self.state[USER_STORE_KEY] = users
        return user

    def authenticate(self, email: str, password: str) -> AppUser | None:
        if self.supabase and self.supabase.enabled:
            authenticated = self.supabase.sign_in(_normalize_email(email), password)
            user = AppUser.from_dict(authenticated)
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
        user = normalize_subscription_user(user)
        users = dict(self.state.get(USER_STORE_KEY, {}))
        users[user.email] = user.to_dict()
        self.state[USER_STORE_KEY] = users
        self.state[AUTH_USER_KEY] = {**dict(authenticated), **user.public_dict()}
        status = effective_subscription_status(user)
        if status != getattr(user, "subscription_status", "active"):
            user = AppUser.from_dict({**user.to_dict(), "subscription_status": status})
            users = dict(self.state.get(USER_STORE_KEY, {}))
            users[user.email] = user.to_dict()
            self.state[USER_STORE_KEY] = users
            self.state[AUTH_USER_KEY] = {**dict(authenticated), **user.public_dict()}
        return user

    def logout(self) -> None:
        self.state.pop(AUTH_USER_KEY, None)
        for key in (
            "member_profile", "action_plan", "action_plan_signature", "coach_messages",
            "content_output", "dashboard_pdf_success",
        ):
            self.state.pop(key, None)

    def change_password(self, new_password: str, confirm_password: str) -> None:
        _validate_new_password(new_password, confirm_password)
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if not authenticated:
            raise PermissionError("กรุณาเข้าสู่ระบบก่อนเปลี่ยนรหัสผ่าน")
        if not self.supabase or not self.supabase.enabled:
            raise RuntimeError("การเปลี่ยนรหัสผ่านใช้งานได้เมื่อเชื่อมต่อ Supabase เท่านั้น")
        access_token = str(authenticated.get("access_token", ""))
        if not access_token:
            raise PermissionError("เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่")
        try:
            self.supabase.update_password(access_token, new_password)
        except Exception as error:
            from services.supabase_service import SupabaseError

            if isinstance(error, SupabaseError):
                raise ValueError(_password_error_message(str(error))) from error
            raise

    def request_password_reset(self, email: str, redirect_url: str) -> None:
        normalized_email = _normalize_email(email)
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
            raise ValueError("กรุณาระบุอีเมลให้ถูกต้อง")
        if not self.supabase or not self.supabase.enabled:
            raise RuntimeError("การรีเซ็ตรหัสผ่านใช้งานได้เมื่อเชื่อมต่อ Supabase เท่านั้น")
        try:
            self.supabase.request_password_reset(normalized_email, redirect_url)
        except Exception as error:
            from services.supabase_service import SupabaseError

            if isinstance(error, SupabaseError):
                raise ValueError("ไม่สามารถส่งอีเมลรีเซ็ตรหัสผ่านได้ กรุณาลองใหม่อีกครั้ง") from error
            raise

    def reset_password(
        self,
        recovery_access_token: str,
        new_password: str,
        confirm_password: str,
    ) -> None:
        _validate_new_password(new_password, confirm_password)
        if not recovery_access_token:
            raise PermissionError("ลิงก์รีเซ็ตรหัสผ่านไม่ถูกต้องหรือหมดอายุ")
        if not self.supabase or not self.supabase.enabled:
            raise RuntimeError("การรีเซ็ตรหัสผ่านใช้งานได้เมื่อเชื่อมต่อ Supabase เท่านั้น")
        try:
            self.supabase.update_password(recovery_access_token, new_password)
        except Exception as error:
            from services.supabase_service import SupabaseError

            if isinstance(error, SupabaseError):
                raise ValueError(
                    "ลิงก์รีเซ็ตรหัสผ่านหมดอายุ กรุณาขอลิงก์ใหม่อีกครั้ง"
                ) from error
            raise

    def get(self, email: str) -> AppUser | None:
        raw = self.state.get(USER_STORE_KEY, {}).get(_normalize_email(email))
        if not raw:
            return None
        user = raw if isinstance(raw, AppUser) else AppUser.from_dict(raw)
        return normalize_subscription_user(user)

    def list_users(self) -> list[AppUser]:
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if self.supabase and self.supabase.enabled and authenticated.get("access_token"):
            rows = self.supabase.list_users(authenticated["access_token"])
            users = [
                AppUser.from_dict(row)
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
                AppUser.from_dict(row)
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
        promoted = replace(target, role=next_role)
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
        if target.email == actor.email and target.role == "Admin" and next_role != "Admin":
            raise PermissionError("ผู้ดูแลระบบไม่สามารถลดสิทธิ์บัญชีของตนเองได้")
        authenticated = self.state.get(AUTH_USER_KEY, {})
        updated = replace(
            target,
            role=next_role,
            subscription_plan=(
                "Leader" if next_role in {"Leader", "Partner"} else target.subscription_plan
            ),
        )
        if next_role == "Leader":
            updated = apply_subscription_action(updated, "approve", actor.email)
        if self.supabase and self.supabase.enabled:
            token = str(authenticated.get("access_token", ""))
            if not token:
                raise PermissionError("กรุณาเข้าสู่ระบบใหม่ก่อนเปลี่ยนบทบาท")
            self.supabase.promote_user(target.email, next_role, token)
            if next_role in {"Leader", "Partner"}:
                self.supabase.update_user_subscription(target.email, updated, token)
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

    def update_subscription(
        self, actor_email: str, target_email: str, action: str
    ) -> AppUser:
        actor = self.get(actor_email)
        target = self.get(target_email)
        if not actor or actor.role != "Admin":
            raise PermissionError("คุณไม่มีสิทธิ์จัดการการสมัครใช้งาน")
        if not target:
            raise KeyError("ไม่พบบัญชีผู้ใช้")
        updated = apply_subscription_action(target, action, actor.email)
        authenticated = self.state.get(AUTH_USER_KEY, {})
        if self.supabase and self.supabase.enabled:
            token = str(authenticated.get("access_token", ""))
            if not token:
                raise PermissionError("กรุณาเข้าสู่ระบบใหม่")
            self.supabase.update_user_subscription(target.email, updated, token)
        users = dict(self.state.get(USER_STORE_KEY, {}))
        users[target.email] = updated.to_dict()
        self.state[USER_STORE_KEY] = users
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


def _password_error_message(message: str) -> str:
    normalized = message.casefold()
    if "same password" in normalized or "different from the old password" in normalized:
        return "รหัสผ่านใหม่ต้องไม่เหมือนรหัสผ่านเดิม"
    if "weak" in normalized or "least" in normalized or "characters" in normalized:
        return "รหัสผ่านใหม่ไม่ผ่านเงื่อนไขความปลอดภัย"
    if "jwt" in normalized or "session" in normalized or "token" in normalized:
        return "เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่"
    return "ไม่สามารถเปลี่ยนรหัสผ่านได้ กรุณาลองใหม่อีกครั้ง"


def _validate_new_password(new_password: str, confirm_password: str) -> None:
    if not new_password:
        raise ValueError("กรุณากรอกรหัสผ่านใหม่")
    if len(new_password) < 8:
        raise ValueError("รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร")
    if new_password != confirm_password:
        raise ValueError("รหัสผ่านใหม่และการยืนยันรหัสผ่านไม่ตรงกัน")
