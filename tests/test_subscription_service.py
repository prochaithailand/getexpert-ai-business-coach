import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from streamlit.testing.v1 import AppTest

from models import AppUser
from services.permissions import visible_navigation
from services.subscription_service import (
    apply_subscription_action,
    effective_subscription_status,
    has_active_subscription,
    normalize_subscription_user,
)
from views.payment_page import LINE_OA_URL


def render_pending_payment_page():
    from models import AppUser
    from views.payment_page import render_payment_page

    render_payment_page(
        AppUser(
            "member@example.com", "สมาชิก",
            subscription_status="pending_payment",
            subscription_plan="Member",
        )
    )


class SubscriptionServiceTests(unittest.TestCase):
    def test_legacy_app_user_without_subscription_attributes_falls_back_active(self):
        legacy = object.__new__(AppUser)
        object.__setattr__(legacy, "email", "legacy@example.com")
        object.__setattr__(legacy, "full_name", "ผู้ใช้เดิม")
        object.__setattr__(legacy, "role", "Member")
        object.__setattr__(legacy, "password_hash", "")

        normalized = normalize_subscription_user(legacy)

        self.assertEqual(normalized.subscription_status, "active")
        self.assertEqual(normalized.subscription_plan, "Member")
        self.assertTrue(has_active_subscription(legacy))

    def test_pending_user_sees_payment_page_and_qr_code(self):
        app = AppTest.from_function(render_pending_payment_page).run()
        visible = "\n".join(
            [*(item.value for item in app.markdown), *(item.value for item in app.warning)]
        )
        self.assertIn("89 บาท", visible)
        self.assertNotIn("ยังไม่ได้ตั้งค่า QR Code", visible)
        self.assertTrue(
            (Path(__file__).resolve().parents[1] / "assets" / "payment_qr.png").is_file()
        )
        self.assertEqual(LINE_OA_URL, "https://lin.ee/YXNuJrR5")

    def test_pending_suspended_and_expired_users_are_locked_but_admin_is_not(self):
        items = (
            "หน้าแรก", "โปรไฟล์สมาชิก", "ชำระเงิน / เปิดใช้งาน",
            "Dashboard สมาชิก", "ตั้งค่าบัญชี", "ออกจากระบบ",
        )
        for status in ("pending_payment", "suspended", "expired"):
            user = AppUser("user@example.com", "ผู้ใช้", subscription_status=status)
            navigation = visible_navigation(items, user)
            self.assertNotIn("หน้าแรก", navigation)
            self.assertNotIn("Dashboard สมาชิก", navigation)
            self.assertIn("ชำระเงิน / เปิดใช้งาน", navigation)
        admin = AppUser("admin@example.com", "Admin", "Admin", subscription_status="suspended")
        self.assertTrue(has_active_subscription(admin))
        self.assertIn("หน้าแรก", visible_navigation(items, admin))
        self.assertNotIn("ชำระเงิน / เปิดใช้งาน", visible_navigation(items, admin))

        active = AppUser(
            "active@example.com", "ผู้ใช้ Active",
            subscription_status="active",
            subscription_expires_at=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        )
        active_navigation = visible_navigation(items, active)
        self.assertIn("หน้าแรก", active_navigation)
        self.assertIn("Dashboard สมาชิก", active_navigation)
        self.assertNotIn("ชำระเงิน / เปิดใช้งาน", active_navigation)

    def test_expiration_and_admin_approval_and_renewal(self):
        now = datetime(2026, 6, 24, tzinfo=timezone.utc)
        expired = AppUser(
            "user@example.com", "ผู้ใช้",
            subscription_status="active",
            subscription_expires_at=(now - timedelta(days=1)).isoformat(),
        )
        self.assertEqual(effective_subscription_status(expired, now), "expired")
        approved = apply_subscription_action(expired, "approve", "admin@example.com", now)
        self.assertEqual(approved.subscription_status, "active")
        self.assertEqual(
            datetime.fromisoformat(approved.subscription_expires_at),
            now + timedelta(days=30),
        )
        renewed = apply_subscription_action(approved, "renew", "admin@example.com", now)
        self.assertEqual(
            datetime.fromisoformat(renewed.subscription_expires_at),
            now + timedelta(days=60),
        )
