import unittest
from unittest.mock import Mock

from models import MemberProfile
from services.auth_service import AUTH_USER_KEY, USER_STORE_KEY, SessionUserStore


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
