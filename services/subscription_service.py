from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from models import AppUser


LOCKED_MESSAGE = "กรุณาชำระเงินและรอการอนุมัติก่อนใช้งานระบบ"
ACTIVE_STATUSES = {"active", "trialing"}
TRIAL_DAYS = 7


def _account_value(user: AppUser, primary: str, alias: str, default: object) -> object:
    primary_value = getattr(user, primary, None)
    if primary_value not in (None, ""):
        return primary_value
    alias_value = getattr(user, alias, None)
    if alias_value not in (None, ""):
        return alias_value
    return default


def _parse_account_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def normalize_subscription_user(user: AppUser) -> AppUser:
    return AppUser(
        email=str(getattr(user, "email", "")),
        full_name=str(getattr(user, "full_name", "")),
        role=str(getattr(user, "role", "Member") or "Member"),
        password_hash=str(getattr(user, "password_hash", "")),
        subscription_status=str(
            _account_value(
                user, "subscription_status", "membership_status", "active"
            )
        ),
        subscription_plan=str(
            _account_value(user, "subscription_plan", "membership_plan", "Member")
        ),
        subscription_started_at=str(
            _account_value(
                user, "subscription_started_at", "membership_started_at", ""
            )
        ),
        subscription_expires_at=str(
            _account_value(
                user, "subscription_expires_at", "membership_expires_at", ""
            )
        ),
        last_payment_at=str(getattr(user, "last_payment_at", "") or ""),
        approved_by=str(getattr(user, "approved_by", "") or ""),
        approved_at=str(getattr(user, "approved_at", "") or ""),
        trial_started_at=str(getattr(user, "trial_started_at", "") or ""),
        trial_ends_at=str(getattr(user, "trial_ends_at", "") or ""),
        trial_used=bool(getattr(user, "trial_used", False)),
    )


def effective_subscription_status(user: AppUser, now: datetime | None = None) -> str:
    user = normalize_subscription_user(user)
    if user.role == "Admin":
        return "active"
    status = getattr(user, "subscription_status", "active") or "active"
    if status == "trialing":
        trial_end = _parse_account_datetime(user.trial_ends_at)
        if not trial_end:
            return "expired"
        return "expired" if trial_end < _utc_now(now) else "trialing"
    expires_at = getattr(user, "subscription_expires_at", "") or ""
    if status == "active" and expires_at:
        expires = _parse_account_datetime(expires_at)
        if expires and expires < _utc_now(now):
            return "expired"
    return status


def has_active_subscription(user: AppUser, now: datetime | None = None) -> bool:
    return (
        getattr(user, "role", "Member") == "Admin"
        or effective_subscription_status(user, now) in ACTIVE_STATUSES
    )


def start_trial(user: AppUser, now: datetime | None = None) -> AppUser:
    user = normalize_subscription_user(user)
    if user.trial_used:
        raise ValueError("บัญชีนี้เคยใช้สิทธิ์ทดลองใช้ฟรีแล้ว")
    current = _utc_now(now)
    return replace(
        user,
        subscription_status="trialing",
        trial_started_at=current.isoformat(),
        trial_ends_at=(current + timedelta(days=TRIAL_DAYS)).isoformat(),
        trial_used=True,
    )


def trial_days_remaining(user: AppUser, now: datetime | None = None) -> int:
    user = normalize_subscription_user(user)
    end = _parse_account_datetime(user.trial_ends_at)
    if not end:
        return 0
    seconds = (end - _utc_now(now)).total_seconds()
    if seconds <= 0:
        return 0
    return max(1, int((seconds + 86399) // 86400))


def apply_subscription_action(
    user: AppUser,
    action: str,
    admin_email: str,
    now: datetime | None = None,
) -> AppUser:
    user = normalize_subscription_user(user)
    current = now or datetime.now(timezone.utc)
    if action in {"approve", "renew"}:
        base = current
        if action == "renew" and user.subscription_expires_at:
            try:
                existing = datetime.fromisoformat(user.subscription_expires_at.replace("Z", "+00:00"))
                if existing > current:
                    base = existing
            except ValueError:
                pass
        return replace(
            user,
            subscription_status="active",
            subscription_started_at=user.subscription_started_at or current.isoformat(),
            subscription_expires_at=(base + timedelta(days=30)).isoformat(),
            last_payment_at=current.isoformat(),
            approved_by=admin_email,
            approved_at=current.isoformat(),
        )
    if action == "suspend":
        return replace(user, subscription_status="suspended")
    if action == "pending":
        return replace(user, subscription_status="pending_payment")
    raise ValueError("คำสั่งจัดการสมาชิกไม่ถูกต้อง")
