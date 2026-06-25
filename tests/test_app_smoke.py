import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from config import NAV_ITEMS
from models import ActionItem, AppUser, MemberProfile, Team
from services.auth_service import (
    AUTH_USER_KEY,
    USER_STORE_KEY,
    recovery_params_from_query,
)
from services.coach_service import LocalCoachService
from services.progress_service import member_progress_key
from services.workplan_service import add_contact, create_default_workplan, replace_weekly_goals
from views.pages import render_action_plan, render_knowledge_base


def _authenticate_app(app: AppTest, role: str = "Member") -> AppTest:
    email = "test-user@example.com"
    user = AppUser(email, "ผู้ใช้ทดสอบ", role, "test-hash")
    app.session_state[USER_STORE_KEY] = {email: user.to_dict()}
    app.session_state[AUTH_USER_KEY] = user.public_dict()
    return app.run()


def _set_authenticated_role(app: AppTest, role: str) -> AppTest:
    email = app.session_state[AUTH_USER_KEY]["email"]
    user = AppUser(email, "ผู้ใช้ทดสอบ", role, "test-hash")
    app.session_state[USER_STORE_KEY] = {email: user.to_dict()}
    app.session_state[AUTH_USER_KEY] = user.public_dict()
    return app.run()


def render_saved_action_plan() -> None:
    import streamlit as st
    from models import ActionItem, MemberProfile
    from services.progress_service import member_progress_key
    from views.pages import render_action_plan

    class NeverGenerateCoach:
        is_api_enabled = True

        def generate_action_plan(self, profile: MemberProfile):
            raise AssertionError("ไม่ควรเรียก OpenAI เมื่อมีแผนที่บันทึกไว้แล้ว")

    profile = MemberProfile(name="สมาชิกเดิม", age=35, occupation="เจ้าของกิจการ")
    signature = (
        profile.name, profile.age, profile.occupation, profile.daily_available_time,
        profile.income_goal, profile.online_marketing_experience, profile.team_name,
        profile.team_id, profile.team_leader, profile.sponsor, profile.role,
    )
    plan = [
        ActionItem(day, "ลงมือทำ", f"ภารกิจวันที่ {day}", ("ทำภารกิจ",), "ทำสำเร็จ")
        for day in range(1, 31)
    ]
    member_key = member_progress_key(profile)
    st.session_state.setdefault("action_plan", plan)
    st.session_state.setdefault("action_plan_signature", signature)
    st.session_state.setdefault("plan_completion_by_member", {member_key: {"1": True}})
    render_action_plan(profile, NeverGenerateCoach())


class AppSmokeTests(unittest.TestCase):
    def test_recovery_query_parser_accepts_supabase_and_legacy_params(self) -> None:
        self.assertEqual(
            recovery_params_from_query(
                {"type": "recovery", "access_token": "query-token"}
            ),
            ("recovery", "query-token"),
        )
        self.assertEqual(
            recovery_params_from_query(
                {
                    "recovery_type": "recovery",
                    "recovery_access_token": "legacy-token",
                }
            ),
            ("recovery", "legacy-token"),
        )

    def test_knowledge_base_import_and_navigation_contract(self) -> None:
        self.assertTrue(callable(render_knowledge_base))
        self.assertNotIn("คลังความรู้", NAV_ITEMS)

    def test_home_onboarding_renders_all_ctas_and_navigates(self) -> None:
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run())
        profile = MemberProfile(name="สมาชิกใหม่", occupation="เจ้าของกิจการ")
        app.session_state["member_profile"] = profile.to_dict()
        app.run()

        labels = {button.label for button in app.button}
        self.assertTrue({
            "ไปกรอกโปรไฟล์", "สร้างแผน 30 วัน", "ไปที่ Workplan",
            "ถามโค้ช AI", "ดู Dashboard",
        }.issubset(labels))
        self.assertTrue(any("เริ่มต้นใช้งาน GetExpert" in item.value for item in app.markdown))

        next(button for button in app.button if button.label == "สร้างแผน 30 วัน").click().run()
        self.assertEqual(app.radio[0].value, "แผนปฏิบัติการ 30 วัน")
        self.assertFalse(app.exception)

    def test_all_pages_render_without_exceptions(self) -> None:
        app = AppTest.from_file("app.py", default_timeout=10).run()
        self.assertFalse(app.exception)
        self.assertEqual(
            tuple(app.radio[0].options),
            ("เข้าสู่ระบบ", "สมัครสมาชิก", "ลืมรหัสผ่าน"),
        )
        app = _authenticate_app(app)

        app.session_state["member_profile"] = {
            "name": "Test Member",
            "age": 30,
            "occupation": "Business owner",
            "daily_available_time": 1.0,
            "income_goal": 30000.0,
            "online_marketing_experience": "Beginner (less than 1 year)",
        }
        for page in (
            "โปรไฟล์สมาชิก",
            "Dashboard สมาชิก",
            "แผนปฏิบัติการ 30 วัน",
            "เครื่องมือสร้างคอนเทนต์",
            "ผู้มุ่งหวัง",
            "Workplan ธุรกิจ",
            "ถามคำถาม AI",
        ):
            app.radio[0].set_value(page).run()
            self.assertFalse(app.exception, f"{page} failed to render")
            self.assertTrue(all(button.label.strip() for button in app.button), f"{page} contains an unlabeled button")

        app.radio[0].set_value("ถามคำถาม AI").run()
        missing_key_message = "ยังไม่ได้ตั้งค่า OPENAI_API_KEY ระบบจึงใช้โหมดค้นหาพื้นฐาน"
        warning_values = [alert.value for alert in app.warning]
        success_values = [alert.value for alert in app.success]
        self.assertTrue(
            missing_key_message in warning_values
            or any("เชื่อมต่อ OpenAI API" in value for value in success_values)
        )

    def test_action_plan_completion_persists_across_page_switches(self) -> None:
        profile = MemberProfile(
            name="สมาชิกทดสอบ",
            age=32,
            occupation="เจ้าของกิจการ",
            daily_available_time=1.0,
            income_goal=30000,
            online_marketing_experience="ระดับเริ่มต้น (น้อยกว่า 1 ปี)",
            team_name="ทีม Dashboard",
            team_id="TEAM-UI",
            team_leader="หัวหน้า UI",
            sponsor="ผู้แนะนำ UI",
            role="Leader",
        )
        signature = (
            profile.name,
            profile.age,
            profile.occupation,
            profile.daily_available_time,
            profile.income_goal,
            profile.online_marketing_experience,
        )
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run(), "Leader")
        app.session_state["member_profile"] = profile.to_dict()
        app.session_state["action_plan"] = LocalCoachService().generate_action_plan(profile)
        app.session_state["action_plan_signature"] = signature
        app.run()

        app.radio[0].set_value("แผนปฏิบัติการ 30 วัน").run()
        self.assertEqual(len(app.checkbox), 30)
        app.checkbox[0].check().run()

        member_key = member_progress_key(profile)
        progress_store = app.session_state["plan_completion_by_member"]
        self.assertTrue(progress_store[member_key]["1"])

        app.radio[0].set_value("หน้าแรก").run()
        app.radio[0].set_value("แผนปฏิบัติการ 30 วัน").run()
        self.assertTrue(app.checkbox[0].value)

    def test_saved_action_plan_auto_loads_without_openai_or_generate_button(self) -> None:
        app = AppTest.from_function(render_saved_action_plan, default_timeout=10).run()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.checkbox), 30)
        self.assertTrue(app.checkbox[0].value)
        labels = [button.label for button in app.button]
        self.assertIn("สร้างแผนใหม่", labels)
        self.assertNotIn("สร้างแผนปฏิบัติการ 30 วันของฉัน", labels)
        visible_text = "\n".join(item.value for item in app.markdown)
        self.assertIn("10 PP", visible_text)
        dashboard = " ".join(markdown.value for markdown in app.markdown)
        for label in ("แผนทั้งหมด", "ทำสำเร็จแล้ว", "คงเหลือ", "คะแนน PP"):
            self.assertIn(label, dashboard)

    def test_member_dashboard_renders_cards_and_four_charts_with_data(self) -> None:
        profile = MemberProfile(
            name="สมาชิก Dashboard",
            age=36,
            occupation="ผู้ประกอบการ",
            daily_available_time=1.5,
            income_goal=50000,
            online_marketing_experience="ระดับเริ่มต้น (น้อยกว่า 1 ปี)",
            team_name="ทีม Dashboard",
            team_id="TEAM-UI",
            team_leader="หัวหน้า UI",
            sponsor="ผู้แนะนำ UI",
            role="Leader",
        )
        member_key = member_progress_key(profile)
        workplan = add_contact(create_default_workplan(), {"name": "ผู้สนใจ A", "category": "A"})
        for goal_key, target, actual in (
            ("sponsor", 4, 2),
            ("team_points", 1000, 500),
            ("income", 10000, 4000),
        ):
            workplan = replace_weekly_goals(
                workplan,
                goal_key,
                [{"week": 1, "target": target, "actual": actual}],
            )
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run(), "Leader")
        app.session_state["member_profile"] = profile.to_dict()
        app.session_state["workplan_by_member"] = {member_key: workplan}
        app.session_state["plan_completion_by_member"] = {member_key: {"1": True, "2": True}}
        app.run()

        app.radio[0].set_value("Dashboard สมาชิก").run()

        self.assertFalse(app.exception)
        rendered = " ".join(
            [*(item.value for item in app.markdown), *(item.value for item in app.subheader)]
        )
        for label in (
            "ชื่อสมาชิก", "เป้าหมายรายได้", "คะแนน PP", "รายชื่อ A",
            "เป้าหมายสปอนเซอร์", "เป้าหมายคะแนนทีม", "ผู้มุ่งหวังสมัครแล้ว",
            "ผู้มุ่งหวังนัดหมายแล้ว", "AI Insight",
            "ชื่อทีม", "ทีม Dashboard", "รหัสทีม", "TEAM-UI", "หัวหน้าทีม",
            "หัวหน้า UI", "ผู้แนะนำ UI", "บทบาท", "Leader",
        ):
            self.assertIn(label, rendered)
        self.assertEqual(len(app.get("vega_lite_chart")), 4)
        download_buttons = app.get("download_button")
        self.assertEqual(download_buttons[0].label, "ดาวน์โหลดรายงาน PDF")

    def test_prospect_manager_renders_required_thai_fields_and_statuses(self) -> None:
        profile = MemberProfile(name="สมาชิก CRM", occupation="เจ้าของกิจการ")
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run())
        app.session_state["member_profile"] = profile.to_dict()
        app.session_state["workplan_by_member"] = {
            member_progress_key(profile): add_contact(
                create_default_workplan(),
                {
                    "name": "ผู้สนใจ A",
                    "category": "A",
                    "status": "นัดหมายแล้ว",
                    "province": "กรุงเทพมหานคร",
                    "notes": "นัดติดตามข้อมูล",
                    "next_follow_up": "2026-06-22",
                },
            )
        }

        app.radio[0].set_value("ผู้มุ่งหวัง").run()

        self.assertFalse(app.exception)
        labels = {
            *(item.label for item in app.text_input),
            *(item.label for item in app.number_input),
            *(item.label for item in app.text_area),
            *(item.label for item in app.date_input),
            *(item.label for item in app.selectbox),
        }
        for label in (
            "ชื่อ", "เบอร์โทร", "อายุ", "อาชีพ", "รายได้ต่อเดือน (บาท)",
            "จังหวัด", "เกรด A/B/C/D", "สถานะ", "หมายเหตุ", "วันที่ติดตามครั้งถัดไป",
        ):
            self.assertIn(label, labels)
        status = next(item for item in app.selectbox if item.label == "สถานะ")
        self.assertEqual(
            tuple(status.options),
            (
                "ยังไม่ติดต่อ", "ติดต่อแล้ว", "ส่งข้อมูลแล้ว", "นัดหมายแล้ว",
                "นำเสนอแล้ว", "กำลังตัดสินใจ", "สมัครแล้ว", "ไม่สนใจ",
            ),
        )
        grade_filter = next(item for item in app.selectbox if item.label == "กรองตามเกรด")
        status_filter = next(item for item in app.selectbox if item.label == "กรองตามสถานะ")
        self.assertEqual(tuple(grade_filter.options), ("ทั้งหมด", "A", "B", "C", "D"))
        self.assertEqual(
            tuple(status_filter.options),
            ("ทั้งหมด", "ยังไม่ติดต่อ", "ติดต่อแล้ว", "นัดหมาย", "สมัครแล้ว", "ปฏิเสธ"),
        )
        for action in ("อัปเดตสถานะ", "แก้ไข", "ลบ"):
            self.assertTrue(any(item.label == action for item in app.button))
        rendered = " ".join(
            [*(item.value for item in app.markdown), *(item.value for item in app.caption)]
        )
        self.assertIn("จังหวัด", rendered)
        self.assertIn("กรุงเทพมหานคร", rendered)

    def test_prospect_quick_status_edit_and_delete_update_session_state(self) -> None:
        profile = MemberProfile(name="สมาชิก Action", occupation="เจ้าของกิจการ")
        member_key = member_progress_key(profile)
        workplan = add_contact(
            create_default_workplan(),
            {"name": "รายชื่อทดสอบ", "category": "B", "status": "ยังไม่ติดต่อ"},
        )
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run())
        app.session_state["member_profile"] = profile.to_dict()
        app.session_state["workplan_by_member"] = {member_key: workplan}
        app.radio[0].set_value("ผู้มุ่งหวัง").run()

        quick_status = next(item for item in app.selectbox if item.label == "สถานะใหม่ของ รายชื่อทดสอบ")
        quick_status.set_value("ติดต่อแล้ว")
        next(item for item in app.button if item.label == "อัปเดตสถานะ").click().run()
        self.assertEqual(
            app.session_state["workplan_by_member"][member_key]["contacts"][0]["status"],
            "ติดต่อแล้ว",
        )

        next(item for item in app.button if item.label == "แก้ไข").click().run()
        edit_name = next(item for item in app.text_input if str(item.key).startswith("edit_name_"))
        edit_name.set_value("รายชื่อแก้ไข")
        next(item for item in app.button if item.label == "บันทึกการแก้ไข").click().run()
        self.assertEqual(
            app.session_state["workplan_by_member"][member_key]["contacts"][0]["name"],
            "รายชื่อแก้ไข",
        )

        edited_workplan = app.session_state["workplan_by_member"][member_key]
        delete_app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run())
        delete_app.session_state["member_profile"] = profile.to_dict()
        delete_app.session_state["workplan_by_member"] = {member_key: edited_workplan}
        delete_app.radio[0].set_value("ผู้มุ่งหวัง").run()
        next(item for item in delete_app.button if item.label == "ลบ").click().run()
        next(item for item in delete_app.button if item.label == "ยืนยันการลบ").click().run()
        self.assertEqual(delete_app.session_state["workplan_by_member"][member_key]["contacts"], [])

    def test_leader_profile_shows_assigned_team_read_only(self) -> None:
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run(), "Leader")
        assigned = MemberProfile(
            name="สมาชิกทีม UI", occupation="ผู้ประกอบการ", team_name="ทีมทดสอบ UI",
            team_id="TEAM-TEST", team_leader="หัวหน้าทดสอบ", sponsor="ผู้แนะนำทดสอบ",
            role="Leader",
        )
        app.session_state["member_profile"] = assigned.to_dict()
        app.run()
        app.radio[0].set_value("โปรไฟล์สมาชิก").run()

        self.assertFalse(any(item.label == "เลือกทีม" for item in app.selectbox))
        for label, expected in (
            ("ชื่อทีม", "ทีมทดสอบ UI"),
            ("รหัสทีม", "TEAM-TEST"),
            ("หัวหน้าทีม", "หัวหน้าทดสอบ"),
        ):
            field = next(item for item in app.text_input if item.label == label)
            self.assertEqual(field.value, expected)
            self.assertTrue(field.disabled)
        role = next(item for item in app.text_input if item.label == "บทบาทในทีม")
        self.assertEqual(role.value, "ผู้นำ")
        self.assertTrue(role.disabled)
        next(item for item in app.text_input if item.label == "อาชีพ").set_value("ที่ปรึกษาธุรกิจ")
        next(item for item in app.button if item.label == "บันทึกโปรไฟล์สมาชิก").click().run()

        saved = app.session_state["member_profile"]
        self.assertEqual(saved["team_name"], "ทีมทดสอบ UI")
        self.assertEqual(saved["team_id"], "TEAM-TEST")
        self.assertEqual(saved["team_leader"], "หัวหน้าทดสอบ")
        self.assertEqual(saved["sponsor"], "ผู้แนะนำทดสอบ")
        self.assertEqual(saved["role"], "Leader")
        self.assertEqual(saved["occupation"], "ที่ปรึกษาธุรกิจ")

    def test_member_profile_hides_all_team_fields(self) -> None:
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run(), "Member")
        assigned = MemberProfile(
            name="สมาชิกทั่วไป", occupation="พนักงาน", team_name="ทีมลับ",
            team_id="TEAM-HIDDEN", team_leader="หัวหน้าทีม", sponsor="ผู้แนะนำ",
            role="Member",
        )
        app.session_state["member_profile"] = assigned.to_dict()
        app.run()
        app.radio[0].set_value("โปรไฟล์สมาชิก").run()

        text_labels = {item.label for item in app.text_input}
        select_labels = {item.label for item in app.selectbox}
        for hidden in ("ชื่อทีม", "รหัสทีม", "หัวหน้าทีม", "บทบาทในทีม"):
            self.assertNotIn(hidden, text_labels)
        self.assertNotIn("เลือกทีม", select_labels)
        for personal in ("ชื่อ-นามสกุล", "อาชีพ", "ผู้แนะนำ"):
            self.assertIn(personal, text_labels)

        next(item for item in app.text_input if item.label == "ผู้แนะนำ").set_value("คุณสมชาย")
        next(item for item in app.button if item.label == "บันทึกโปรไฟล์สมาชิก").click().run()
        self.assertEqual(app.session_state["member_profile"]["sponsor"], "คุณสมชาย")
        button_labels = [item.label for item in app.button]
        for cta in ("สร้างแผน 30 วัน", "บันทึกผู้มุ่งหวัง", "ไปที่ Dashboard"):
            self.assertIn(cta, button_labels)

    def test_admin_can_create_team_from_team_management_page(self) -> None:
        profile = MemberProfile(name="ผู้ดูแลทีม", occupation="ผู้นำธุรกิจ", role="Admin")
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run(), "Admin")
        app.session_state["member_profile"] = profile.to_dict()
        member = AppUser("leader@example.com", "หัวหน้าพัฒนา", "Leader", "test-hash")
        users = dict(app.session_state[USER_STORE_KEY])
        users[member.email] = member.to_dict()
        app.session_state[USER_STORE_KEY] = users
        app.run()
        app.radio[0].set_value("จัดการทีม").run()

        values = {
            "ชื่อทีม": "ทีมพัฒนา",
            "รหัสทีม": "dev-01",
            "ผู้สนับสนุนหลัก": "ผู้สนับสนุนกลาง",
        }
        for label, value in values.items():
            next(item for item in app.text_input if item.label == label).set_value(value)
        next(item for item in app.selectbox if item.label == "หัวหน้าทีม").set_value(
            "หัวหน้าพัฒนา (leader@example.com)"
        )
        next(item for item in app.text_area if item.label == "หมายเหตุ").set_value("ทีมสำหรับพัฒนาสมาชิก")
        next(item for item in app.button if item.label == "สร้างทีม").click().run()

        self.assertIn("DEV-01", app.session_state["teams"])
        self.assertEqual(app.session_state["teams"]["DEV-01"]["name"], "ทีมพัฒนา")
        self.assertEqual(app.session_state["teams"]["DEV-01"]["leader"], "หัวหน้าพัฒนา")
        self.assertEqual(app.session_state[USER_STORE_KEY][member.email]["role"], "Leader")
        self.assertEqual(app.session_state["member_profiles_by_user"][member.email]["team_id"], "DEV-01")
        self.assertTrue(any(item.label == "แก้ไข" for item in app.button))
        self.assertTrue(any(item.label == "กำหนดหัวหน้า" for item in app.button))
        self.assertTrue(any(item.label == "กำหนดสมาชิก" for item in app.button))
        self.assertTrue(any(item.label == "ลบ" for item in app.button))

    def test_team_dashboard_renders_summary_table_rankings_and_insights(self) -> None:
        profile = MemberProfile(
            name="หัวหน้าทีม UI", occupation="ผู้นำธุรกิจ", team_name="ทีม UI",
            team_id="TEAM-UI", team_leader="หัวหน้าทีม UI", role="Leader",
        )
        member_key = member_progress_key(profile)
        workplan = add_contact(create_default_workplan(), {"name": "รายชื่อ A", "category": "A"})
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run(), "Leader")
        app.session_state["member_profile"] = profile.to_dict()
        app.session_state["member_profiles_by_key"] = {member_key: profile.to_dict()}
        app.session_state["teams"] = {"TEAM-UI": Team("ทีม UI", "TEAM-UI", "หัวหน้าทีม UI").to_dict()}
        app.session_state["workplan_by_member"] = {member_key: workplan}
        app.session_state["plan_completion_by_member"] = {member_key: {"1": True, "2": True}}
        app.run()
        app.radio[0].set_value("Team Dashboard").run()

        self.assertFalse(app.exception)
        visible_text = "\n".join(
            [*(item.value for item in app.markdown), *(item.value for item in app.subheader)]
        )
        for expected in (
            "สรุปภาพรวมทีม", "จำนวนสมาชิกทั้งหมด", "คะแนน PP รวม", "ตารางสมาชิกทีม",
            "อันดับผลงานทีม", "สมาชิกที่ทำผลงานดีที่สุด", "งานที่ควรโฟกัสในสัปดาห์นี้",
            "รหัสทีม", "TEAM-UI", "โค้ช AI สำหรับทีม", "สรุป Prospect Pipeline",
            "ยังไม่ติดต่อ", "ความคืบหน้าแผน 30 วันของทีม", "Completed 100%", "Below 50%",
        ):
            self.assertIn(expected, visible_text)
        self.assertEqual(len(app.dataframe), 1)

    def test_sidebar_hides_restricted_team_pages_by_role(self) -> None:
        app = _authenticate_app(AppTest.from_file("app.py", default_timeout=10).run())
        self.assertNotIn("จัดการทีม", app.radio[0].options)
        self.assertNotIn("Team Dashboard", app.radio[0].options)
        self.assertNotIn("จัดการผู้ใช้", app.radio[0].options)

        _set_authenticated_role(app, "Leader")
        self.assertNotIn("จัดการทีม", app.radio[0].options)
        self.assertIn("Team Dashboard", app.radio[0].options)
        self.assertNotIn("จัดการผู้ใช้", app.radio[0].options)

        _set_authenticated_role(app, "Admin")
        self.assertIn("จัดการทีม", app.radio[0].options)
        self.assertIn("Team Dashboard", app.radio[0].options)
        self.assertIn("จัดการผู้ใช้", app.radio[0].options)
        app.radio[0].set_value("จัดการผู้ใช้").run()
        self.assertIn(
            "สถานะระบบ OpenAI",
            [item.value for item in app.subheader],
        )


if __name__ == "__main__":
    unittest.main()
