import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from brand_config import get_brand
from models import KnowledgeMatch, MemberProfile
from services.knowledge_service import KnowledgeService
from services.member_activity_service import MemberActivityContext, NO_WORKPLAN_MESSAGE
from services.openai_coach_service import OpenAICoachService


class StubKnowledgeService(KnowledgeService):
    def __init__(self, matches: list[KnowledgeMatch]) -> None:
        super().__init__(Path("knowledge"))
        self.matches = matches

    def search_text(self, query: str, limit: int = 4) -> list[KnowledgeMatch]:
        return self.matches[:limit]


class FakeResponses:
    def __init__(self, output_text: str = "", error: Exception | None = None) -> None:
        self.output_text = output_text
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


class OpenAICoachServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.match = KnowledgeMatch(
            "หนังสือ 5 โมดูลธุรกิจ MLM",
            "การพัฒนาธุรกิจ",
            12,
            "การสร้างรายชื่อผู้มุ่งหวังและติดตามผลอย่างสม่ำเสมอเป็นพื้นฐานของการพัฒนาธุรกิจ",
            0.9,
        )
        self.profile = MemberProfile(
            name="นิดา เอ็กซ์เพิร์ต",
            age=35,
            occupation="ที่ปรึกษาการขาย",
            daily_available_time=1.5,
            income_goal=50000,
            online_marketing_experience="ระดับเริ่มต้น (น้อยกว่า 1 ปี)",
            team_name="ทีม GetExpert",
            team_id="TEAM-AI",
            team_leader="คุณลีดเดอร์",
            sponsor="คุณสปอนเซอร์",
            role="Leader",
        )

    def test_api_request_contains_identity_profile_history_and_knowledge(self) -> None:
        responses = FakeResponses(
            "🎯 Executive Summary\nควรเริ่มจากการวางแผนที่ทำได้จริง\n\n"
            "──────────────\n\n"
            "📖 รายละเอียด\n- จัดทำรายชื่อผู้มุ่งหวัง\n- ติดตามผลอย่างสม่ำเสมอ\n\n"
            "──────────────\n\n"
            "✅ สิ่งที่ควรทำต่อ\n1. เริ่มพูดคุยวันละ 3 ราย"
        )
        service = OpenAICoachService(
            StubKnowledgeService([self.match]),
            model="gpt-test",
            client=FakeClient(responses),
        )

        result = service.answer_question(
            "ควรเริ่มหาลูกค้าอย่างไร",
            self.profile,
            [{"role": "user", "content": "ฉันมีเวลาวันละหนึ่งชั่วโมงครึ่ง"}],
        )

        self.assertEqual(result.sources, ("หนังสือ 5 โมดูลธุรกิจ MLM",))
        self.assertEqual(result.metadata["answer_source"], "openai")
        self.assertEqual(result.metadata["model"], "gpt-test")
        self.assertEqual(result.metadata["error_category"], "")
        call = responses.calls[0]
        self.assertEqual(call["model"], "gpt-test")
        self.assertFalse(call["store"])
        for expected in (
            "GetExpert AI Business Coach ผู้ช่วยพัฒนานักธุรกิจเครือข่ายยุคดิจิทัล",
            "นิดา เอ็กซ์เพิร์ต",
            "ที่ปรึกษาการขาย",
            "50,000 บาท",
            "1.5 ชั่วโมง",
            "ระดับเริ่มต้น",
            "ทีม GetExpert",
            "TEAM-AI",
            "คุณลีดเดอร์",
            "คุณสปอนเซอร์",
            "Leader",
        ):
            self.assertIn(expected, call["instructions"])
        self.assertEqual(call["input"][0]["content"], "ฉันมีเวลาวันละหนึ่งชั่วโมงครึ่ง")
        self.assertIn("หนังสือ 5 โมดูลธุรกิจ MLM", call["input"][-1]["content"])
        self.assertNotIn("C:\\", call["input"][-1]["content"])
        self.assertIn("สรุปความหมาย", call["instructions"])
        self.assertIn("🎯 Executive Summary", call["instructions"])
        self.assertIn("📖 รายละเอียด", call["instructions"])
        self.assertIn("✅ สิ่งที่ควรทำต่อ", call["instructions"])
        self.assertNotIn("**สรุปคำตอบ**", call["instructions"])
        self.assertNotIn("**ประเด็นสำคัญ**", call["instructions"])
        self.assertNotIn("**แนวทางนำไปใช้**", call["instructions"])
        self.assertIn("ต้องใช้หัวข้อ 3 บรรทัดนี้แบบตรงตัว", call["instructions"])
        self.assertIn("ห้ามเปลี่ยนคำ", call["instructions"])
        self.assertIn("ห้ามใช้หัวข้อแทน เช่น สรุปคำตอบ หรือ แนวทางนำไปใช้", call["instructions"])
        self.assertIn("สำหรับคำถามสั้น", call["instructions"])
        self.assertTrue(result.answer.rstrip().endswith("- หนังสือ 5 โมดูลธุรกิจ MLM"))
        self.assertIn("**แหล่งข้อมูลอ้างอิง**", result.answer)

    def test_non_thai_api_response_is_not_displayed(self) -> None:
        responses = FakeResponses("Start by making a list of prospects.")
        service = OpenAICoachService(StubKnowledgeService([self.match]), client=FakeClient(responses))

        result = service.answer_question("เริ่มต้นอย่างไร", self.profile)

        self.assertIn("ไม่สามารถจัดรูปแบบคำตอบได้", result.answer)
        self.assertNotIn("Start by", result.answer)
        self.assertIn("**แหล่งข้อมูลอ้างอิง**", result.answer)

    def test_no_evidence_does_not_call_openai(self) -> None:
        responses = FakeResponses("ไม่ควรถูกเรียกใช้งาน")
        service = OpenAICoachService(StubKnowledgeService([]), client=FakeClient(responses))

        result = service.answer_question("พยากรณ์อากาศพรุ่งนี้", self.profile)

        self.assertEqual(responses.calls, [])
        self.assertIn("ฐานความรู้ของระบบยังไม่มีข้อมูลเพียงพอ", result.answer)
        self.assertIn("**แหล่งข้อมูลอ้างอิง**", result.answer)

    def test_workplan_question_sends_member_activity_without_pdf_matches(self) -> None:
        responses = FakeResponses(
            "🎯 Executive Summary\nมีข้อมูล Workplan แล้ว\n\n"
            "──────────────\n\n"
            "📖 รายละเอียด\n- รายชื่อ A มี 3 ราย\n\n"
            "──────────────\n\n"
            "✅ สิ่งที่ควรทำต่อ\n1. ติดตามผลวันนี้"
        )
        service = OpenAICoachService(StubKnowledgeService([]), client=FakeClient(responses))
        context = MemberActivityContext(
            True,
            "ผู้มุ่งหวังทั้งหมด 5 ราย | A 3 | B 1 | C 1 | D 0\n"
            "ลำดับ 1: คุณเอ | เกรด A | กำลังตัดสินใจ | ครบกำหนดวันนี้ | หมายเหตุ ขอคุยหลังเลิกงาน\n"
            "สปอนเซอร์เป้าหมาย 4 คน ทำได้ 2 คน\nคะแนน PP 60",
        )

        result = service.answer_question("ควรติดตามใครก่อน", self.profile, activity_context=context)

        self.assertEqual(len(responses.calls), 1)
        request = responses.calls[0]
        self.assertIn("ผู้มุ่งหวังทั้งหมด 5 ราย", request["input"][-1]["content"])
        self.assertIn("คะแนน PP 60", request["input"][-1]["content"])
        self.assertIn("คุณเอ", request["input"][-1]["content"])
        self.assertIn("ข้อมูล Workplan และแผน 30 วันที่แนบมาเป็นแหล่งหลัก", request["instructions"])
        self.assertIn("เกรด สถานะ วันที่ติดตาม และหมายเหตุ", request["instructions"])
        self.assertIn("มีข้อมูล Workplan", result.answer)

    def test_workplan_question_without_data_returns_required_message(self) -> None:
        responses = FakeResponses("ไม่ควรถูกเรียกใช้งาน")
        service = OpenAICoachService(StubKnowledgeService([self.match]), client=FakeClient(responses))

        result = service.answer_question(
            "มีข้อมูลเข้าใน workplan ไหม",
            self.profile,
            activity_context=MemberActivityContext(False, NO_WORKPLAN_MESSAGE),
        )

        self.assertEqual(responses.calls, [])
        self.assertEqual(result.answer, NO_WORKPLAN_MESSAGE)

    def test_target_questions_follow_rag_answer_contract(self) -> None:
        questions = (
            "5 โมดูล MLM มีอะไรบ้าง",
            "สรุปหนังสือ 5 โมดูล MLM",
            "สมาชิกใหม่ควรเริ่มต้นอย่างไร",
            "จะสร้างคอนเทนต์สำหรับธุรกิจเครือข่ายอย่างไร",
        )
        for question in questions:
            with self.subTest(question=question):
                responses = FakeResponses(
                    "🎯 Executive Summary\nสรุปจากคลังความรู้\n\n"
                    "──────────────\n\n"
                    "📖 รายละเอียด\n- เรียนรู้เป็นขั้นตอน\n\n"
                    "──────────────\n\n"
                    "✅ สิ่งที่ควรทำต่อ\n1. เริ่มลงมือทำวันนี้"
                )
                service = OpenAICoachService(
                    StubKnowledgeService([self.match]),
                    client=FakeClient(responses),
                )

                result = service.answer_question(question, self.profile)

                self.assertEqual(len(responses.calls), 1)
                request = responses.calls[0]
                self.assertIn(question, request["input"][-1]["content"])
                for old_heading in ("**สรุปคำตอบ**", "**ประเด็นสำคัญ**", "**แนวทางนำไปใช้**"):
                    self.assertNotIn(old_heading, request["instructions"])
                    self.assertNotIn(old_heading, result.answer)
                for section in ("🎯 Executive Summary", "📖 รายละเอียด", "✅ สิ่งที่ควรทำต่อ", "**แหล่งข้อมูลอ้างอิง**"):
                    self.assertIn(section, result.answer)
                self.assertTrue(result.answer.rstrip().endswith("- หนังสือ 5 โมดูลธุรกิจ MLM"))

    def test_api_error_returns_thai_knowledge_fallback(self) -> None:
        responses = FakeResponses(error=RuntimeError("offline"))
        service = OpenAICoachService(StubKnowledgeService([self.match]), client=FakeClient(responses))

        result = service.answer_question("วิธีสร้างรายชื่อ", self.profile)

        self.assertIn("AI หลักยังไม่พร้อมใช้งาน", result.answer)
        self.assertIn("การสร้างรายชื่อผู้มุ่งหวัง", result.answer)
        self.assertEqual(result.sources, ("หนังสือ 5 โมดูลธุรกิจ MLM",))
        self.assertEqual(result.metadata["answer_source"], "fallback")
        self.assertEqual(result.metadata["error_category"], "unknown")
        self.assertEqual(result.metadata["model"], "")
        self.assertNotIn("offline", str(result.metadata))

    def test_tglife_brand_prompt_supports_multilingual_answers(self) -> None:
        responses = FakeResponses(
            "🎯 Executive Summary\nFocus on three prospects today.\n\n"
            "──────────────\n\n"
            "📖 รายละเอียด\nUse your Workplan and follow up consistently.\n\n"
            "──────────────\n\n"
            "✅ สิ่งที่ควรทำต่อ\n1. Contact your top A prospects."
        )
        service = OpenAICoachService(
            StubKnowledgeService([self.match]),
            client=FakeClient(responses),
            brand=get_brand({}, {"APP_BRAND": "tglife"}),
        )

        result = service.answer_question(
            "How should I grow my TG Life team this week?",
            self.profile,
        )

        call = responses.calls[0]
        self.assertIn("TG Life AI Business Coach powered by GetExpert", call["instructions"])
        self.assertIn("Answer in the same language as the user", call["instructions"])
        self.assertIn("Burmese/Myanmar", call["instructions"])
        self.assertEqual(result.metadata["answer_source"], "openai")
        self.assertIn("Focus on three prospects", result.answer)

    def test_openai_action_plan_receives_all_profile_fields(self) -> None:
        days = [
            {
                "day": day,
                "phase": "วางแผน",
                "focus": f"กิจกรรมวันที่ {day}",
                "tasks": ["ลงมือทำ", "บันทึกผล"],
                "success_metric": "ทำครบตามแผน",
            }
            for day in range(1, 31)
        ]
        responses = FakeResponses(json.dumps({"days": days}, ensure_ascii=False))
        service = OpenAICoachService(StubKnowledgeService([self.match]), client=FakeClient(responses))

        plan = service.generate_action_plan(self.profile)

        self.assertEqual(len(plan), 30)
        request = responses.calls[0]["input"]
        for expected in (
            "นิดา เอ็กซ์เพิร์ต", "35 ปี", "ที่ปรึกษาการขาย", "1.5 ชั่วโมง",
            "50,000 บาท", "ระดับเริ่มต้น", "ทีม GetExpert", "TEAM-AI", "Leader",
        ):
            self.assertIn(expected, request)

    def test_openai_content_receives_selections_profile_and_knowledge(self) -> None:
        responses = FakeResponses("โพสต์ภาษาไทยเฉพาะบุคคลสำหรับสร้างผู้สนใจใหม่")
        service = OpenAICoachService(StubKnowledgeService([self.match]), client=FakeClient(responses))

        content = service.generate_content(
            "โพสต์ Facebook",
            self.profile,
            "เพิ่มผู้สนใจใหม่",
            "การสร้างรายชื่อผู้มุ่งหวัง",
        )

        self.assertIn("ภาษาไทย", content)
        request = responses.calls[0]["input"]
        for expected in (
            "โพสต์ Facebook",
            "เพิ่มผู้สนใจใหม่",
            "การสร้างรายชื่อผู้มุ่งหวัง",
            "นิดา เอ็กซ์เพิร์ต",
            "หนังสือ 5 โมดูลธุรกิจ MLM",
        ):
            self.assertIn(expected, request)

    def test_openai_dashboard_insight_receives_member_metrics(self) -> None:
        responses = FakeResponses(
            "**จุดแข็งของสมาชิก**\n- มีวินัย\n\n"
            "**จุดที่ควรปรับปรุง**\n- เพิ่มรายชื่อ\n\n"
            "**สิ่งที่ควรทำต่อใน 7 วันข้างหน้า**\n- ติดตามผลทุกวัน"
        )
        service = OpenAICoachService(StubKnowledgeService([]), client=FakeClient(responses))
        context = "แผน 30 วัน 50% | คะแนน PP 150 | รายชื่อ A 4 | สปอนเซอร์ 75%"

        insight = service.generate_dashboard_insight(self.profile, context)

        self.assertEqual(len(responses.calls), 1)
        call = responses.calls[0]
        self.assertIn(context, call["input"])
        self.assertIn("ห้ามแต่งตัวเลข", call["instructions"])
        self.assertIn("สิ่งที่ควรทำต่อใน 7 วันข้างหน้า", insight)

    def test_openai_team_insight_receives_team_metrics(self) -> None:
        responses = FakeResponses(
            "**สมาชิกที่ทำผลงานดีที่สุด**\n- คุณเอ\n\n"
            "**สมาชิกที่ต้องการความช่วยเหลือ**\n- คุณบี\n\n"
            "**ความคืบหน้าของทีม**\n- กำลังเติบโต\n\n"
            "**งานที่ควรโฟกัสในสัปดาห์นี้**\n- เพิ่มรายชื่อ A"
        )
        service = OpenAICoachService(StubKnowledgeService([]), client=FakeClient(responses))
        context = "ทีม TEAM-AI | สมาชิก 5 คน | PP รวม 420 | ความคืบหน้าเฉลี่ย 48%"

        insight = service.generate_team_insight(context)

        self.assertEqual(len(responses.calls), 1)
        call = responses.calls[0]
        self.assertIn(context, call["input"])
        self.assertIn("ห้ามแต่งตัวเลข", call["instructions"])
        self.assertIn("งานที่ควรโฟกัสในสัปดาห์นี้", insight)

    def test_ai_team_coach_receives_question_history_and_full_team_context(self) -> None:
        responses = FakeResponses(
            "**คำแนะนำสำหรับทีมวันนี้**\n- ให้สมาชิกที่ความคืบหน้าต่ำทำภารกิจหนึ่งงาน\n- ติดตามรายชื่อเกรด A ที่นัดหมายแล้ว"
        )
        service = OpenAICoachService(StubKnowledgeService([]), client=FakeClient(responses))
        context = (
            "ทีม TEAM-AI | Workplan สปอนเซอร์ 2/4 | PP รวม 300 | "
            "สมาชิกคุณบีความคืบหน้า 10% | ผู้มุ่งหวังเกรด A นัดหมายแล้ว"
        )
        history = [{"role": "user", "content": "เมื่อวานทีมทำอะไรไปบ้าง"}]

        answer = service.answer_team_question("ทีมของผมควรทำอะไรวันนี้", context, history)

        self.assertEqual(len(responses.calls), 1)
        call = responses.calls[0]
        self.assertIn("Workplan", call["instructions"])
        self.assertIn("คะแนน PP", call["instructions"])
        self.assertIn("🎯 Executive Summary", call["instructions"])
        self.assertIn("📖 รายละเอียด", call["instructions"])
        self.assertIn("✅ สิ่งที่ควรทำต่อ", call["instructions"])
        self.assertIn("ต้องใช้หัวข้อ 3 บรรทัดนี้แบบตรงตัว", call["instructions"])
        self.assertEqual(call["input"][0]["content"], history[0]["content"])
        self.assertIn(context, call["input"][-1]["content"])
        self.assertIn("ทีมของผมควรทำอะไรวันนี้", call["input"][-1]["content"])
        self.assertIn("คำแนะนำสำหรับทีมวันนี้", answer)


if __name__ == "__main__":
    unittest.main()
