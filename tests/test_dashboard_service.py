import unittest

from models import MemberProfile
from services.coach_service import LocalCoachService
from services.dashboard_service import (
    EMPTY_DASHBOARD_MESSAGE,
    build_and_save_dashboard,
    dashboard_context,
    record_member_usage,
)
from services.progress_service import member_progress_key
from services.workplan_service import add_contact, create_default_workplan, replace_weekly_goals


class DashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = MemberProfile(
            name="สมาชิกแดชบอร์ด",
            age=38,
            occupation="เจ้าของกิจการ",
            daily_available_time=2,
            income_goal=60000,
            online_marketing_experience="ระดับกลาง (1-3 ปี)",
            team_name="ทีมแดชบอร์ด",
            team_id="TEAM-DASH",
            team_leader="หัวหน้าทีม",
            sponsor="ผู้แนะนำ",
            role="Leader",
        )

    def test_dashboard_combines_member_progress_workplan_and_usage(self) -> None:
        key = member_progress_key(self.profile)
        workplan = create_default_workplan()
        for category in ("A", "A", "B", "D"):
            workplan = add_contact(workplan, {"name": f"รายชื่อ {category}", "category": category})
        workplan = replace_weekly_goals(workplan, "sponsor", [{"week": 1, "target": 4, "actual": 3}])
        workplan = replace_weekly_goals(workplan, "team_points", [{"week": 1, "target": 1000, "actual": 500}])
        workplan = replace_weekly_goals(workplan, "income", [{"week": 1, "target": 20000, "actual": 5000}])
        state = {
            "workplan_by_member": {key: workplan},
            "plan_completion_by_member": {key: {str(day): True for day in range(1, 16)}},
            "teams": {
                "TEAM-DASH": {
                    "name": "ทีมจากทะเบียนกลาง", "team_id": "TEAM-DASH", "leader": "หัวหน้าจากทะเบียน",
                    "primary_sponsor": "ผู้สนับสนุนหลัก", "notes": "",
                }
            },
        }
        record_member_usage(state, self.profile, "content_creator")
        record_member_usage(state, self.profile, "content_creator")
        record_member_usage(state, self.profile, "ai_coach")

        snapshot = build_and_save_dashboard(state, self.profile)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["plan"]["percentage"], 50)
        self.assertEqual(snapshot["plan"]["pp_score"], 150)
        self.assertEqual(snapshot["plan"]["status"], "กำลังสร้างวินัย")
        self.assertEqual(
            snapshot["contacts"],
            {"total": 4, "A": 2, "B": 1, "C": 0, "D": 1, "signed_up": 0, "appointments": 0},
        )
        self.assertEqual(snapshot["goals"]["sponsor"]["percentage"], 75)
        self.assertEqual(snapshot["goals"]["team_points"]["percentage"], 50)
        self.assertEqual(snapshot["goals"]["income"]["percentage"], 25)
        self.assertEqual(snapshot["usage"], {"content_creator": 2, "ai_coach": 1})
        self.assertEqual(
            snapshot["team"],
            {
                "name": "ทีมจากทะเบียนกลาง", "id": "TEAM-DASH", "leader": "หัวหน้าจากทะเบียน",
                "sponsor": "ผู้แนะนำ", "role": "Leader",
            },
        )
        self.assertEqual(state["dashboard_by_member"][key], snapshot)
        self.assertIn("ถามโค้ช AI 1 ครั้ง", dashboard_context(snapshot))
        self.assertIn("ทีม: ทีมจากทะเบียนกลาง", dashboard_context(snapshot))

    def test_dashboard_requires_profile_and_workplan_data(self) -> None:
        self.assertIsNone(build_and_save_dashboard({}, None))
        self.assertIsNone(build_and_save_dashboard({}, self.profile))
        self.assertEqual(EMPTY_DASHBOARD_MESSAGE, "ยังไม่มีข้อมูลเพียงพอ กรุณากรอกโปรไฟล์และ Workplan ก่อน")

    def test_local_dashboard_insight_is_thai_and_complete(self) -> None:
        insight = LocalCoachService().generate_dashboard_insight(self.profile, "ข้อมูลทดสอบ")
        for heading in ("จุดแข็งของสมาชิก", "จุดที่ควรปรับปรุง", "สิ่งที่ควรทำต่อใน 7 วันข้างหน้า"):
            self.assertIn(heading, insight)


if __name__ == "__main__":
    unittest.main()
