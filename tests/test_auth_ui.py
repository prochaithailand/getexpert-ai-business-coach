import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from services.auth_service import AUTH_USER_KEY, USER_STORE_KEY
from services.settings_service import SupabaseConfig


class AuthUiTests(unittest.TestCase):
    @patch("services.settings_service.load_supabase_config", return_value=SupabaseConfig())
    def test_guest_sees_only_login_and_registration_then_can_sign_in(self, _mock_load) -> None:
        app = AppTest.from_file("app.py", default_timeout=10).run()

        self.assertFalse(app.exception)
        self.assertEqual(tuple(app.radio[0].options), ("เข้าสู่ระบบ", "สมัครสมาชิก"))
        self.assertNotIn("หน้าแรก", app.radio[0].options)

        app.radio[0].set_value("สมัครสมาชิก").run()
        next(item for item in app.text_input if item.label == "ชื่อ-นามสกุล").set_value("สมาชิก ใหม่")
        next(item for item in app.text_input if item.label == "อีเมล").set_value("new@example.com")
        next(item for item in app.text_input if item.label == "รหัสผ่าน").set_value("secure-pass")
        role = next(item for item in app.text_input if item.label == "บทบาท")
        self.assertTrue(role.disabled)
        self.assertEqual(role.value, "สมาชิก")
        next(item for item in app.button if item.label == "สมัครสมาชิก").click().run()

        self.assertEqual(app.session_state[USER_STORE_KEY]["new@example.com"]["role"], "Member")
        app.radio[0].set_value("เข้าสู่ระบบ").run()
        next(item for item in app.text_input if item.label == "อีเมล").set_value("new@example.com")
        next(item for item in app.text_input if item.label == "รหัสผ่าน").set_value("secure-pass")
        next(item for item in app.button if item.label == "เข้าสู่ระบบ").click().run()

        self.assertEqual(app.session_state[AUTH_USER_KEY]["email"], "new@example.com")
        self.assertIn("หน้าแรก", app.radio[0].options)
        self.assertIn("ออกจากระบบ", app.radio[0].options)
        self.assertNotIn("Team Dashboard", app.radio[0].options)
        self.assertNotIn("จัดการทีม", app.radio[0].options)


if __name__ == "__main__":
    unittest.main()
