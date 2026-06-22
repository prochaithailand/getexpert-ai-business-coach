import unittest
from pathlib import Path

from models import KnowledgeMatch, MemberProfile
from services.coach_service import LocalCoachService
from services.knowledge_service import KnowledgeService


class StubKnowledgeService(KnowledgeService):
    def __init__(self, matches: list[KnowledgeMatch]) -> None:
        super().__init__(Path("knowledge"))
        self.matches = matches

    def search_text(self, query: str, limit: int = 4) -> list[KnowledgeMatch]:
        return self.matches[:limit]


class LocalCoachServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.match = KnowledgeMatch(
            "หนังสือ 5 โมดูลธุรกิจ MLM",
            "การพัฒนาธุรกิจ",
            12,
            "การทำรายชื่อและติดตามผลอย่างสม่ำเสมอเป็นพื้นฐานสำคัญของการสร้างธุรกิจเครือข่ายให้เติบโต",
            0.9,
        )
        self.service = LocalCoachService(StubKnowledgeService([self.match]))
        self.profile = MemberProfile(
            name="Nida Expert",
            age=35,
            occupation="Sales consultant",
            daily_available_time=1.5,
            income_goal=50000,
            online_marketing_experience="ระดับเริ่มต้น (น้อยกว่า 1 ปี)",
        )

    def test_action_plan_contains_30_ordered_days(self) -> None:
        plan = self.service.generate_action_plan(self.profile)
        self.assertEqual(len(plan), 30)
        self.assertEqual([item.day for item in plan], list(range(1, 31)))
        self.assertTrue(all(item.tasks and item.success_metric for item in plan))
        self.assertEqual(plan[-1].focus, "สรุปผลการทำงานครบ 30 วัน")

    def test_all_content_channels_generate_personalized_copy(self) -> None:
        expected_markers = {
            "โพสต์ Facebook": "Nida Expert",
            "สคริปต์ TikTok": "1.5 ชั่วโมง",
            "ข้อความบรอดแคสต์ LINE OA": "Nida Expert",
        }
        for channel, marker in expected_markers.items():
            result = self.service.generate_content(channel, self.profile)
            self.assertGreater(len(result), 100)
            self.assertIn(marker, result)

    def test_coach_uses_profile_name_and_knowledge_source(self) -> None:
        reply = self.service.reply("How do I find more leads?", self.profile)
        self.assertIn("Nida", reply)
        self.assertIn("การทำรายชื่อ", reply)

        result = self.service.answer_question("How do I find more leads?", self.profile)
        self.assertEqual(result.sources, ("หนังสือ 5 โมดูลธุรกิจ MLM",))
        self.assertNotIn("knowledge", " ".join(result.sources).lower())

    def test_coach_declines_when_knowledge_has_no_match(self) -> None:
        service = LocalCoachService(StubKnowledgeService([]))
        result = service.answer_question("What is the weather?", self.profile)
        self.assertIn("ฐานความรู้ยังไม่มีข้อมูลเพียงพอ", result.answer)
        self.assertEqual(result.sources, ())

    def test_different_profiles_generate_different_plans(self) -> None:
        beginner = MemberProfile(
            name="เมย์",
            age=24,
            occupation="พนักงานบัญชี",
            daily_available_time=0.5,
            income_goal=15000,
            online_marketing_experience="ยังไม่มีประสบการณ์",
        )
        advanced = MemberProfile(
            name="คุณสมชาย",
            age=48,
            occupation="เจ้าของกิจการ",
            daily_available_time=3.0,
            income_goal=100000,
            online_marketing_experience="ระดับเชี่ยวชาญ (มากกว่า 3 ปี)",
        )

        beginner_plan = self.service.generate_action_plan(beginner)
        advanced_plan = self.service.generate_action_plan(advanced)

        self.assertNotEqual(beginner_plan, advanced_plan)
        self.assertIn("เมย์", beginner_plan[0].focus)
        self.assertIn("พนักงานบัญชี", " ".join(beginner_plan[0].tasks))
        self.assertIn("48 ปี", advanced_plan[2].focus)
        self.assertNotEqual(beginner_plan[3].focus, advanced_plan[3].focus)

    def test_content_varies_by_profile_platform_goal_and_topic(self) -> None:
        second_profile = MemberProfile(
            name="อรุณ",
            age=45,
            occupation="ครู",
            daily_available_time=2.0,
            income_goal=80000,
            online_marketing_experience="ระดับเชี่ยวชาญ (มากกว่า 3 ปี)",
        )
        facebook = self.service.generate_content(
            "โพสต์ Facebook", self.profile, "เพิ่มผู้สนใจใหม่", "การสร้างรายชื่อผู้มุ่งหวัง"
        )
        tiktok = self.service.generate_content(
            "สคริปต์ TikTok", self.profile, "สร้างการรับรู้", "การสร้างทีม"
        )
        line_for_second_profile = self.service.generate_content(
            "ข้อความบรอดแคสต์ LINE OA", second_profile, "ติดตามลูกค้า", "การดูแลลูกค้าเก่า"
        )

        self.assertEqual(len({facebook, tiktok, line_for_second_profile}), 3)
        self.assertIn("เพิ่มผู้สนใจใหม่", facebook)
        self.assertIn("การสร้างทีม", tiktok)
        self.assertIn("อรุณ", line_for_second_profile)
        self.assertIn("การดูแลลูกค้าเก่า", line_for_second_profile)


if __name__ == "__main__":
    unittest.main()
