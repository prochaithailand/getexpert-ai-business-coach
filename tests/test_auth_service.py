import unittest
from unittest.mock import Mock

from models import AppUser, MemberProfile
from services.auth_service import AUTH_USER_KEY, USER_STORE_KEY, SessionUserStore
from services.supabase_service import SupabaseError


class AuthServiceTests(unittest.TestCase):
    def test_supabase_registration_loads_team_data_when_session_is_created(self) -> None:
        state = {"pending_invite_code": "INVITE123"}
        supabase = Mock()
        supabase.enabled = True
        supabase.sign_up.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "user": {"id": "user-1"},
        }
        store = SessionUserStore(state, supabase)

        user = store.register(
            "member@example.com",
            "strong-pass",
            "สมาชิกใหม่",
        )

        authenticated = state[AUTH_USER_KEY]
        supabase.load_user_data.assert_called_once_with(state, authenticated)
        self.assertEqual(state["pending_invite_code"], "INVITE123")
        self.assertEqual(user.role, "Member")
        self.assertEqual(user.subscription_status, "trialing")
        self.assertEqual(user.subscription_plan, "Member")
        self.assertTrue(user.trial_used)
        self.assertTrue(user.trial_started_at)
        self.assertTrue(user.trial_ends_at)

    def test_registration_defaults_to_member_and_hashes_password(self) -> None:
        state = {}
        store = SessionUserStore(state)

        user = store.register("Member@Example.com", "strong-pass", "สมาชิก ทดสอบ")

        self.assertEqual(user.email, "member@example.com")
        self.assertEqual(user.role, "Member")
        self.assertNotEqual(state[USER_STORE_KEY][user.email]["password_hash"], "strong-pass")
        self.assertTrue(state[USER_STORE_KEY][user.email]["password_hash"].startswith("pbkdf2_sha256$"))

    def test_user_cannot_register_as_admin(self) -> None:
        store = SessionUserStore({})
        with self.assertRaises(ValueError):
            store.register("admin@example.com", "strong-pass", "ผู้ใช้", role="Admin")

    def test_login_sets_session_and_logout_clears_current_user_data(self) -> None:
        state = {"member_profile": {"name": "ข้อมูลเดิม"}, "coach_messages": [{"role": "user"}]}
        store = SessionUserStore(state)
        store.register("member@example.com", "strong-pass", "สมาชิก ทดสอบ")

        self.assertIsNone(store.authenticate("member@example.com", "wrong-pass"))
        user = store.authenticate("MEMBER@example.com", "strong-pass")
        self.assertEqual(user.role, "Member")
        self.assertEqual(state[AUTH_USER_KEY]["email"], "member@example.com")
        self.assertNotIn("password_hash", state[AUTH_USER_KEY])

        store.logout()
        self.assertNotIn(AUTH_USER_KEY, state)
        self.assertNotIn("member_profile", state)
        self.assertNotIn("coach_messages", state)

    def test_only_admin_can_promote_member_then_leader_to_admin(self) -> None:
        state = {}
        store = SessionUserStore(state)
        admin = store.create_admin_internally("owner@example.com", "owner-pass", "เจ้าของระบบ")
        member = store.register("member@example.com", "member-pass", "สมาชิก ทีม")
        other = store.register("other@example.com", "other-pass", "สมาชิก อื่น")
        state["member_profiles_by_user"] = {
            member.email: MemberProfile(name=member.full_name, occupation="งาน", role="Member").to_dict()
        }

        with self.assertRaises(PermissionError):
            store.promote(other.email, member.email)
        leader = store.promote(admin.email, member.email)
        self.assertEqual(leader.role, "Leader")
        self.assertEqual(state["member_profiles_by_user"][member.email]["role"], "Leader")
        promoted_admin = store.promote(admin.email, member.email)
        self.assertEqual(promoted_admin.role, "Admin")

    def test_only_admin_can_assign_and_remove_partner_role(self) -> None:
        admin = AppUser("admin@example.com", "ผู้ดูแล", "Admin", "hash")
        leader = AppUser("leader@example.com", "ผู้นำ", "Leader", "hash")
        member = AppUser("member@example.com", "สมาชิก", "Member", "hash")
        state = {
            USER_STORE_KEY: {
                admin.email: admin.to_dict(),
                leader.email: leader.to_dict(),
                member.email: member.to_dict(),
            },
            "member_profiles_by_user": {
                member.email: MemberProfile(
                    name=member.full_name, occupation="งาน", role="Member"
                ).to_dict(),
            },
        }
        store = SessionUserStore(state)

        with self.assertRaises(PermissionError):
            store.set_role(member.email, member.email, "Partner")
        with self.assertRaises(PermissionError):
            store.set_role(leader.email, leader.email, "Partner")

        partner = store.set_role(admin.email, member.email, "Partner")
        self.assertEqual(partner.role, "Partner")
        self.assertEqual(
            state["member_profiles_by_user"][member.email]["partner_status"],
            "approved",
        )
        restored = store.set_role(admin.email, member.email, "Leader")
        self.assertEqual(restored.role, "Leader")
        self.assertEqual(
            state["member_profiles_by_user"][member.email]["partner_status"],
            "",
        )

    def test_admin_cannot_demote_own_account(self) -> None:
        admin = AppUser("admin@example.com", "ผู้ดูแล", "Admin", "hash")
        store = SessionUserStore(
            {USER_STORE_KEY: {admin.email: admin.to_dict()}}
        )

        with self.assertRaises(PermissionError):
            store.set_role(admin.email, admin.email, "Member")

    def test_change_password_validates_login_length_and_confirmation(self) -> None:
        supabase = Mock()
        supabase.enabled = True
        store = SessionUserStore({}, supabase)

        with self.assertRaises(PermissionError):
            store.change_password("new-password", "new-password")

        store.state[AUTH_USER_KEY] = {"access_token": "access-token"}
        with self.assertRaisesRegex(ValueError, "อย่างน้อย 8"):
            store.change_password("short", "short")
        with self.assertRaisesRegex(ValueError, "ไม่ตรงกัน"):
            store.change_password("new-password", "different-password")

        store.change_password("new-password", "new-password")
        supabase.update_password.assert_called_once_with(
            "access-token", "new-password"
        )

    def test_forgot_and_reset_password_use_supabase_auth_only(self) -> None:
        supabase = Mock()
        supabase.enabled = True
        store = SessionUserStore({}, supabase)

        with self.assertRaisesRegex(ValueError, "อีเมล"):
            store.request_password_reset(
                "not-an-email",
                "https://getexpert-ai.streamlit.app",
            )

        store.request_password_reset(
            "Member@Example.com",
            "https://getexpert-ai.streamlit.app",
        )
        supabase.request_password_reset.assert_called_once_with(
            "member@example.com",
            "https://getexpert-ai.streamlit.app",
        )

        with self.assertRaisesRegex(PermissionError, "ไม่ถูกต้องหรือหมดอายุ"):
            store.reset_password("", "new-password", "new-password")
        with self.assertRaisesRegex(ValueError, "ไม่ตรงกัน"):
            store.reset_password(
                "recovery-token",
                "new-password",
                "different-password",
            )

        store.reset_password(
            "recovery-token",
            "new-password",
            "new-password",
        )
        supabase.update_password.assert_called_once_with(
            "recovery-token",
            "new-password",
        )

        supabase.update_password.side_effect = SupabaseError("expired jwt")
        with self.assertRaisesRegex(ValueError, "หมดอายุ"):
            store.reset_password(
                "expired-token",
                "another-password",
                "another-password",
            )

    def test_local_leader_list_contains_only_leaders(self) -> None:
        state = {}
        store = SessionUserStore(state)
        admin = store.create_admin_internally("owner@example.com", "owner-pass", "เจ้าของระบบ")
        member = store.register("member@example.com", "member-pass", "สมาชิก")
        leader = store.register("leader@example.com", "leader-pass", "หัวหน้าทีม")
        state[USER_STORE_KEY][leader.email]["role"] = "Leader"

        leaders = store.list_users_by_role("Leader")

        self.assertEqual([user.email for user in leaders], [leader.email])
        self.assertNotIn(member.email, [user.email for user in leaders])
        self.assertNotIn(admin.email, [user.email for user in leaders])


if __name__ == "__main__":
    unittest.main()
