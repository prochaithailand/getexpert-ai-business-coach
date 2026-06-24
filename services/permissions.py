from __future__ import annotations

from collections.abc import Sequence

from models import AppUser, MemberProfile
from services.subscription_service import has_active_subscription


UNAUTHORIZED_MESSAGE = "คุณไม่มีสิทธิ์เข้าถึงหน้านี้"
TEAM_MANAGEMENT_PAGE = "จัดการทีม"
TEAM_DASHBOARD_PAGE = "Team Dashboard"
USER_MANAGEMENT_PAGE = "จัดการผู้ใช้"
PAYMENT_PAGE = "ชำระเงิน / เปิดใช้งาน"
LIMITED_PAGES = {"โปรไฟล์สมาชิก", PAYMENT_PAGE, "ตั้งค่าบัญชี", "ออกจากระบบ"}


def can_access_team_management(subject: MemberProfile | AppUser | None) -> bool:
    return bool(subject and subject.role == "Admin")


def can_access_team_dashboard(subject: MemberProfile | AppUser | None) -> bool:
    return bool(subject and subject.role in {"Leader", "Partner", "Admin"})


def visible_navigation(items: Sequence[str], subject: MemberProfile | AppUser | None) -> tuple[str, ...]:
    if isinstance(subject, AppUser) and not has_active_subscription(subject):
        return tuple(item for item in items if item in LIMITED_PAGES)
    hidden = {PAYMENT_PAGE} if isinstance(subject, AppUser) else set()
    if not can_access_team_management(subject):
        hidden.add(TEAM_MANAGEMENT_PAGE)
        hidden.add(USER_MANAGEMENT_PAGE)
    if not can_access_team_dashboard(subject):
        hidden.add(TEAM_DASHBOARD_PAGE)
    return tuple(item for item in items if item not in hidden)
