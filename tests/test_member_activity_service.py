import unittest
from datetime import date, timedelta

from models import ActionItem, MemberProfile
from services.coach_service import LocalCoachService
from services.member_activity_service import NO_WORKPLAN_MESSAGE, build_member_activity_context
from services.progress_service import member_progress_key
from services.workplan_service import add_contact, create_default_workplan, replace_weekly_goals


class MemberActivityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = MemberProfile(
            name="มานี ทดสอบ",
            age=34,
            occupation="เจ้าของกิจการ",
            daily_available_time=1.5,
            income_goal=50000,
            online_marketing_experience="ระดับเริ่มต้น",
            team_name="ทีมกิจกรรม",
            team_id="TEAM-ACT",
            team_leader="หัวหน้ากิจกรรม",
            sponsor="ผู้แนะนำกิจกรรม",
            role="Member",
        )

    def test_context_contains_workplan_progress_pp_and_completed_actions(self) -> None:
        key = member_progress_key(self.profile)
        workplan = create_default_workplan()
        for category in ("A", "A", "B", "C"):
            workplan = add_contact(workplan, {"name": f"รายชื่อ {category}", "category": category})
        workplan = replace_weekly_goals(
            workplan,
            "sponsor",
            [{"week": 1, "target": 4, "actual": 2}],
        )
        workplan = replace_weekly_goals(
            workplan,
            "team_points",
            [{"week": 1, "target": 1000, "actual": 750}],
        )
        workplan = replace_weekly_goals(
            workplan,
            "income",
            [{"week": 1, "target": 10000, "actual": 6000}],
        )
        plan = [ActionItem(1, "เริ่มต้น", "สร้างรายชื่อ", ("เขียนรายชื่อ",), "ครบ 10 ราย")]
        signature = (
            self.profile.name, self.profile.age, self.profile.occupation,
            self.profile.daily_available_time, self.profile.income_goal,
            self.profile.online_marketing_experience,
        )
        state = {
            "workplan_by_member": {key: workplan},
            "plan_completion_by_member": {key: {"1": True, "2": True}},
            "action_plan": plan,
            "action_plan_signature": signature,
            "teams": {
                "TEAM-ACT": {
                    "name": "ทีมจากระบบกลาง", "team_id": "TEAM-ACT", "leader": "หัวหน้าจากระบบกลาง",
                    "primary_sponsor": "ผู้สนับสนุนหลัก", "notes": "",
                }
            },
        }

        context = build_member_activity_context(state, self.profile)

        self.assertTrue(context.has_data)
        for expected in (
            "ทั้งหมด 4 ราย | A 2 | B 1 | C 1 | D 0",
            "สปอนเซอร์: เป้าหมายรวม 4 คน | ทำได้จริง 2 คน | สำเร็จ 50%",
            "คะแนนทีม: เป้าหมายรวม 1,000 คะแนน | ทำได้จริง 750 คะแนน | สำเร็จ 75%",
            "รายได้: เป้าหมายรวม 10,000 บาท | ทำได้จริง 6,000 บาท | สำเร็จ 60%",
            "ทำสำเร็จ 2/30 วัน",
            "คะแนน PP 20",
            "วันที่ 1: สร้างรายชื่อ",
        ):
            self.assertIn(expected, context.summary)
        self.assertNotIn("เบอร์โทร", context.summary)
        self.assertIn("ชื่อทีม ทีมจากระบบกลาง", context.summary)
        self.assertIn("รหัสทีม TEAM-ACT", context.summary)
        self.assertIn("หัวหน้าทีม หัวหน้าจากระบบกลาง", context.summary)

    def test_empty_state_returns_required_message(self) -> None:
        context = build_member_activity_context({}, self.profile)
        self.assertFalse(context.has_data)
        self.assertEqual(context.summary, NO_WORKPLAN_MESSAGE)

    def test_empty_state_uses_requested_language(self) -> None:
        my_context = build_member_activity_context({}, self.profile, "my")
        en_context = build_member_activity_context({}, self.profile, "en")

        self.assertFalse(my_context.has_data)
        self.assertIn("စနစ်ထဲတွင်", my_context.summary)
        self.assertNotIn("ตอนนี้ยังไม่มีข้อมูล", my_context.summary)
        self.assertFalse(en_context.has_data)
        self.assertEqual(
            en_context.summary,
            "There is no saved Workplan data in the system yet. Please add your information in the Business Workplan menu first.",
        )

    def test_local_coach_empty_workplan_answer_uses_question_language(self) -> None:
        answer = LocalCoachService().answer_question("Workplan လုပ်ငန်းအစီအစဉ် ရှိလား", self.profile).answer

        self.assertIn("စနစ်ထဲတွင်", answer)
        self.assertNotIn("ตอนนี้ยังไม่มีข้อมูล", answer)

    def test_local_coach_answers_from_workplan_without_api_key(self) -> None:
        context = build_member_activity_context(
            {
                "workplan_by_member": {
                    member_progress_key(self.profile): add_contact(
                        create_default_workplan(),
                        {"name": "ผู้สนใจตัวอย่าง", "category": "A"},
                    )
                }
            },
            self.profile,
        )

        answer = LocalCoachService().answer_question(
            "รายชื่อของผมพอไหม",
            self.profile,
            activity_context=context,
        ).answer

        self.assertIn("จำนวนผู้มุ่งหวังทั้งหมด 1 ราย | A 1", answer)
        self.assertIn("คะแนน PP 0", answer)

    def test_context_includes_crm_priority_notes_and_follow_up_without_phone(self) -> None:
        key = member_progress_key(self.profile)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        workplan = add_contact(
            create_default_workplan(),
            {
                "name": "คุณเอ",
                "phone": "0899999999",
                "category": "A",
                "status": "กำลังตัดสินใจ",
                "notes": "ต้องการปรึกษาครอบครัวก่อนตัดสินใจ",
                "next_follow_up": yesterday,
            },
        )

        context = build_member_activity_context({"workplan_by_member": {key: workplan}}, self.profile)

        self.assertIn("ลำดับ 1: คุณเอ", context.summary)
        self.assertIn("เกินกำหนด 1 วัน", context.summary)
        self.assertIn("ต้องการปรึกษาครอบครัวก่อนตัดสินใจ", context.summary)
        self.assertNotIn("0899999999", context.summary)


if __name__ == "__main__":
    unittest.main()
