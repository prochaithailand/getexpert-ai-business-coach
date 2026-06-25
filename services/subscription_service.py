from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from models import AppUser


LOCKED_MESSAGE = "กรุณาชำระเงินและรอการอนุมัติก่อนใช้งานระบบ"
ACTIVE_STATUSES = {"active", "trialing"}
TRIAL_DAYS = 7


def normalize_subscription_user(user: AppUser) -> AppUser:
    return AppUser(
        email=str(getattr(user, "email", "")),
        full_name=str(getattr(user, "full_name", "")),
        role=str(getattr(user, "role", "Member") or "Member"),
        password_hash=str(getattr(user, "password_hash", "")),
        subscription_status=str(
            getattr(user, "subscription_status", "active") or "active"
        ),
        subscription_plan=str(
            getattr(user, "subscription_plan", "Member") or "Member"
        ),
        subscription_started_at=str(
            getattr(user, "subscription_started_at", "") or ""
        ),
        subscription_expires_at=str(
            getattr(user, "subscription_expires_at", "") or ""
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
        trial_ends_at = getattr(user, "trial_ends_at", "") or ""
        if not trial_ends_at:
            return "expired"
        try:
            trial_end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
            return "expired" if trial_end < (now or datetime.now(timezone.utc)) else "trialing"
        except ValueError:
            return "expired"
    expires_at = getattr(user, "subscription_expires_at", "") or ""
    if status == "active" and expires_at:
        try:
            expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires < (now or datetime.now(timezone.utc)):
                return "expired"
        except ValueError:
            return status
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
    current = now or datetime.now(timezone.utc)
    return replace(
        user,
        subscription_status="trialing",
        trial_started_at=current.isoformat(),
        trial_ends_at=(current + timedelta(days=TRIAL_DAYS)).isoformat(),
        trial_used=True,
    )


def trial_days_remaining(user: AppUser, now: datetime | None = None) -> int:
    user = normalize_subscription_user(user)
    if not user.trial_ends_at:
        return 0
    try:
        end = datetime.fromisoformat(user.trial_ends_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    seconds = (end - (now or datetime.now(timezone.utc))).total_seconds()
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
