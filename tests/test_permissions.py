import unittest

from streamlit.testing.v1 import AppTest

from config import NAV_ITEMS
from models import MemberProfile
from services.permissions import (
    UNAUTHORIZED_MESSAGE,
    can_access_team_dashboard,
    can_access_team_management,
    visible_navigation,
)


def render_denied_team_management():
    from models import MemberProfile
    from views.team_page import render_team_management

    render_team_management(MemberProfile(name="สมาชิก", occupation="งาน", role="Member"))


def render_denied_team_dashboard():
    from models import MemberProfile
    from services.coach_service import LocalCoachService
    from views.team_dashboard_page import render_team_dashboard

    render_team_dashboard(
        MemberProfile(name="สมาชิก", occupation="งาน", role="Member"),
        LocalCoachService(),
    )


class PermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.member = MemberProfile(name="สมาชิก", occupation="งาน", role="Member")
        self.leader = MemberProfile(name="ผู้นำ", occupation="งาน", role="Leader")
        self.admin = MemberProfile(name="ผู้ดูแล", occupation="งาน", role="Admin")

    def test_member_cannot_see_or_access_restricted_team_pages(self) -> None:
        navigation = visible_navigation(NAV_ITEMS, self.member)
        self.assertNotIn("จัดการทีม", navigation)
        self.assertNotIn("Team Dashboard", navigation)
        self.assertNotIn("จัดการผู้ใช้", navigation)
        self.assertFalse(can_access_team_management(self.member))
        self.assertFalse(can_access_team_dashboard(self.member))

    def test_leader_can_only_access_team_dashboard(self) -> None:
        navigation = visible_navigation(NAV_ITEMS, self.leader)
        self.assertNotIn("จัดการทีม", navigation)
        self.assertIn("Team Dashboard", navigation)
        self.assertNotIn("จัดการผู้ใช้", navigation)
        self.assertFalse(can_access_team_management(self.leader))
        self.assertTrue(can_access_team_dashboard(self.leader))

    def test_admin_can_access_both_team_pages(self) -> None:
        navigation = visible_navigation(NAV_ITEMS, self.admin)
        self.assertIn("จัดการทีม", navigation)
        self.assertIn("Team Dashboard", navigation)
        self.assertIn("จัดการผู้ใช้", navigation)
        self.assertTrue(can_access_team_management(self.admin))
        self.assertTrue(can_access_team_dashboard(self.admin))
        self.assertEqual(UNAUTHORIZED_MESSAGE, "คุณไม่มีสิทธิ์เข้าถึงหน้านี้")

    def test_restricted_pages_show_required_thai_message_when_called_directly(self) -> None:
        management = AppTest.from_function(
            render_denied_team_management, default_timeout=10
        ).run()
        dashboard = AppTest.from_function(
            render_denied_team_dashboard, default_timeout=10
        ).run()

        self.assertIn(UNAUTHORIZED_MESSAGE, [warning.value for warning in management.warning])
        self.assertIn(UNAUTHORIZED_MESSAGE, [warning.value for warning in dashboard.warning])
        self.assertFalse(management.exception)
        self.assertFalse(dashboard.exception)


if __name__ == "__main__":
    unittest.main()
