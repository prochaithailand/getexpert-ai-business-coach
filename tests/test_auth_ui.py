import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.auth_service import AUTH_USER_KEY, USER_STORE_KEY
from services.settings_service import SupabaseConfig
from models import AppUser
from views.auth_pages import _role_actions_for
from views.auth_pages import render_account_settings


def render_change_password_for_guest() -> None:
    from services.auth_service import SessionUserStore
    from views.auth_pages import render_account_settings

    render_account_settings(SessionUserStore({}), None)


def render_change_password_for_authenticated_user() -> None:
    import streamlit as st

    from models import AppUser
    from services.auth_service import AUTH_USER_KEY, SessionUserStore
    from views.auth_pages import render_account_settings

    class FakeSupabase:
        enabled = True

        def update_password(self, access_token: str, new_password: str) -> None:
            st.session_state["changed_password_token"] = access_token
            st.session_state["password_was_changed"] = bool(new_password)

    user = AppUser("member@example.com", "สมาชิก", "Member")
    state = st.session_state
    state.setdefault(
        AUTH_USER_KEY,
        {**user.public_dict(), "access_token": "access-token"},
    )
    render_account_settings(SessionUserStore(state, FakeSupabase()), user)


def render_forgot_password_page() -> None:
    import streamlit as st

    from services.auth_service import SessionUserStore
    from views.auth_pages import render_forgot_password

    class FakeSupabase:
        enabled = True

        def request_password_reset(self, email: str, redirect_url: str) -> None:
            st.session_state["reset_email"] = email
            st.session_state["reset_redirect_url"] = redirect_url

    render_forgot_password(
        SessionUserStore(st.session_state, FakeSupabase()),
        "https://getexpert-ai.streamlit.app",
    )


def render_reset_password_page() -> None:
    import streamlit as st

    from services.auth_service import SessionUserStore
    from views.auth_pages import render_reset_password

    class FakeSupabase:
        enabled = True

        def update_password(self, access_token: str, new_password: str) -> None:
            st.session_state["recovery_token_used"] = access_token
            st.session_state["reset_password_saved"] = bool(new_password)

    if not st.session_state.get("recovery_test_initialized"):
        st.session_state["password_recovery_access_token"] = "recovery-token"
        st.session_state["recovery_test_initialized"] = True
    render_reset_password(
        SessionUserStore(st.session_state, FakeSupabase()),
        str(st.session_state.get("password_recovery_access_token", "")),
    )


def render_login_page_with_failed_auth() -> None:
    import streamlit as st

    from views.auth_pages import render_login

    class FakeStore:
        def authenticate(self, email: str, password: str):
            st.session_state["login_attempt_email"] = email
            st.session_state["login_attempt_password"] = password
            return None

    render_login(FakeStore())


def render_login_page_already_in_progress() -> None:
    import streamlit as st

    from views.auth_pages import render_login

    class FakeStore:
        def authenticate(self, email: str, password: str):
            st.session_state["unexpected_login_attempt"] = True
            return None

    st.session_state["login_in_progress"] = True
    render_login(FakeStore())


class AuthUiTests(unittest.TestCase):
    def test_login_in_progress_disables_submit_and_shows_status(self) -> None:
        app = AppTest.from_function(
            render_login_page_already_in_progress,
            default_timeout=10,
        ).run()

        submit = next(
            item
            for item in app.button
            if item.label == "กำลังเข้าสู่ระบบ..."
        )
        self.assertTrue(submit.disabled)
        self.assertTrue(
            any("กำลังเข้าสู่ระบบ กรุณารอสักครู่" in item.value for item in app.info)
        )
        self.assertNotIn("unexpected_login_attempt", app.session_state)

    def test_failed_login_resets_in_progress_state(self) -> None:
        app = AppTest.from_function(
            render_login_page_with_failed_auth,
            default_timeout=10,
        ).run()

        next(item for item in app.text_input if item.label == "อีเมล").set_value(
            "member@example.com"
        )
        next(item for item in app.text_input if item.label == "รหัสผ่าน").set_value(
            "wrong-password"
        )
        next(item for item in app.button if item.label == "เข้าสู่ระบบ").click().run()

        self.assertEqual(app.session_state["login_attempt_email"], "member@example.com")
        self.assertFalse(app.session_state["login_in_progress"])
        self.assertNotIn("pending_login_email", app.session_state)
        self.assertNotIn("pending_login_password", app.session_state)
        self.assertTrue(
            any("อีเมลหรือรหัสผ่านไม่ถูกต้อง" in item.value for item in app.error)
        )

    def test_forgot_password_form_sends_email_with_configured_redirect(self) -> None:
        app = AppTest.from_function(
            render_forgot_password_page,
            default_timeout=10,
        ).run()

        next(item for item in app.text_input if item.label == "อีเมล").set_value(
            "Member@Example.com"
        )
        next(
            item
            for item in app.button
            if item.label == "ส่งลิงก์รีเซ็ตรหัสผ่าน"
        ).click().run()

        self.assertEqual(app.session_state["reset_email"], "member@example.com")
        self.assertEqual(
            app.session_state["reset_redirect_url"],
            "https://getexpert-ai.streamlit.app",
        )
        self.assertTrue(any("ระบบได้ส่งลิงก์" in item.value for item in app.success))

    def test_recovery_user_can_set_new_password(self) -> None:
        app = AppTest.from_function(
            render_reset_password_page,
            default_timeout=10,
        ).run()

        next(
            item for item in app.text_input if item.label == "รหัสผ่านใหม่"
        ).set_value("new-password")
        next(
            item
            for item in app.text_input
            if item.label == "ยืนยันรหัสผ่านใหม่"
        ).set_value("new-password")
        next(
            item
            for item in app.button
            if item.label == "บันทึกรหัสผ่านใหม่"
        ).click().run()

        self.assertEqual(
            app.session_state["recovery_token_used"],
            "recovery-token",
        )
        self.assertTrue(app.session_state["reset_password_saved"])
        self.assertNotIn(
            "password_recovery_access_token",
            app.session_state,
        )
        self.assertTrue(app.session_state["password_reset_completed"])

    def test_guest_cannot_access_change_password_page(self) -> None:
        app = AppTest.from_function(
            render_change_password_for_guest,
            default_timeout=10,
        ).run()

        self.assertTrue(any("กรุณาเข้าสู่ระบบ" in item.value for item in app.warning))
        self.assertFalse(any(item.label == "รหัสผ่านใหม่" for item in app.text_input))

    def test_authenticated_user_sees_and_can_submit_change_password_form(self) -> None:
        app = AppTest.from_function(
            render_change_password_for_authenticated_user,
            default_timeout=10,
        ).run()

        new_password = next(
            item for item in app.text_input if item.label == "รหัสผ่านใหม่"
        )
        confirmation = next(
            item for item in app.text_input if item.label == "ยืนยันรหัสผ่านใหม่"
        )
        submit = next(
            item for item in app.button if item.label == "บันทึกรหัสผ่านใหม่"
        )
        new_password.set_value("short")
        confirmation.set_value("short")
        submit.click().run()
        self.assertTrue(any("อย่างน้อย 8" in item.value for item in app.error))

        new_password.set_value("new-password")
        confirmation.set_value("different-password")
        submit.click().run()
        self.assertTrue(any("ไม่ตรงกัน" in item.value for item in app.error))

        new_password.set_value("new-password")
        confirmation.set_value("new-password")
        submit.click().run()
        self.assertTrue(
            any("เปลี่ยนรหัสผ่านเรียบร้อยแล้ว" in item.value for item in app.success)
        )
        self.assertTrue(app.session_state["password_was_changed"])

    def test_admin_user_management_exposes_partner_actions_by_current_role(self) -> None:
        admin = AppUser("admin@example.com", "ผู้ดูแล", "Admin")
        member_actions = _role_actions_for(
            AppUser("member@example.com", "สมาชิก", "Member"), admin
        )
        leader_actions = _role_actions_for(
            AppUser("leader@example.com", "ผู้นำ", "Leader"), admin
        )
        partner_actions = _role_actions_for(
            AppUser("partner@example.com", "Partner", "Partner"), admin
        )
        other_admin_actions = _role_actions_for(
            AppUser("other-admin@example.com", "ผู้ดูแลอื่น", "Admin"), admin
        )
        current_admin_actions = _role_actions_for(admin, admin)

        self.assertIn(("แต่งตั้งเป็น Partner", "Partner"), member_actions)
        self.assertIn(("แต่งตั้งเป็น Partner", "Partner"), leader_actions)
        self.assertIn(
            ("ถอด Partner และปรับเป็นผู้นำ", "Leader"),
            partner_actions,
        )
        self.assertIn(
            ("ถอด Partner และปรับเป็นสมาชิก", "Member"),
            partner_actions,
        )
        self.assertIn(("ลดสิทธิ์เป็นผู้นำ", "Leader"), other_admin_actions)
        self.assertIn(("ลดสิทธิ์เป็นสมาชิก", "Member"), other_admin_actions)
        self.assertEqual(current_admin_actions, ())

    @patch("services.settings_service.load_supabase_config", return_value=SupabaseConfig())
    def test_guest_sees_only_login_and_registration_then_can_sign_in(self, _mock_load) -> None:
        app = AppTest.from_file("app.py", default_timeout=10).run()

        self.assertFalse(app.exception)
        self.assertEqual(
            tuple(app.radio[0].options),
            ("เข้าสู่ระบบ", "สมัครสมาชิก", "ลืมรหัสผ่าน"),
        )
        self.assertNotIn("หน้าแรก", app.radio[0].options)

        app.radio[0].set_value("สมัครสมาชิก").run()
        next(item for item in app.text_input if item.label == "ชื่อ-นามสกุล").set_value("สมาชิก ใหม่")
        next(item for item in app.text_input if item.label == "อีเมล").set_value("new@example.com")
        next(item for item in app.text_input if item.label == "รหัสผ่าน").set_value("secure-pass")
        role = next(item for item in app.text_input if item.label == "บทบาท")
        self.assertTrue(role.disabled)
        self.assertEqual(role.value, "สมาชิก")
        marketing_opt_in = next(
            item
            for item in app.checkbox
            if item.label.startswith("ฉันต้องการรับบทความ")
        )
        self.assertFalse(marketing_opt_in.value)
        marketing_opt_in.check()
        next(item for item in app.button if item.label == "สมัครสมาชิก").click().run()

        self.assertEqual(app.session_state[USER_STORE_KEY]["new@example.com"]["role"], "Member")
        self.assertTrue(
            app.session_state[USER_STORE_KEY]["new@example.com"][
                "marketing_email_opt_in"
            ]
        )
        app.radio[0].set_value("เข้าสู่ระบบ").run()
        next(item for item in app.text_input if item.label == "อีเมล").set_value("new@example.com")
        next(item for item in app.text_input if item.label == "รหัสผ่าน").set_value("secure-pass")
        next(item for item in app.button if item.label == "เข้าสู่ระบบ").click().run()

        self.assertEqual(app.session_state[AUTH_USER_KEY]["email"], "new@example.com")
        self.assertEqual(
            app.session_state[AUTH_USER_KEY]["subscription_status"],
            "trialing",
        )
        self.assertIn("หน้าแรก", app.radio[0].options)
        self.assertNotIn("ชำระเงิน / เปิดใช้งาน", app.radio[0].options)
        self.assertIn("โปรไฟล์สมาชิก", app.radio[0].options)
        self.assertIn("ออกจากระบบ", app.radio[0].options)
        self.assertNotIn("Team Dashboard", app.radio[0].options)
        self.assertNotIn("จัดการทีม", app.radio[0].options)


if __name__ == "__main__":
    unittest.main()
