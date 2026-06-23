import unittest
from io import BytesIO

from pypdf import PdfReader

from models import MemberProfile
from services.pdf_report_service import (
    generate_member_report_pdf,
    member_report_filename,
    thai_pdf_font_paths,
    thai_pdf_fonts_available,
)


class PdfReportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = MemberProfile(
            name="สมชาย ใจดี",
            age=40,
            occupation="เจ้าของกิจการ",
            daily_available_time=2,
            income_goal=80000,
            online_marketing_experience="ระดับกลาง (1-3 ปี)",
            team_name="ทีมสุขภาพดี",
            team_id="TEAM-888",
            team_leader="คุณหัวหน้า",
            sponsor="คุณผู้แนะนำ",
            role="Admin",
        )
        self.snapshot = {
            "member_key": "member-test",
            "name": self.profile.name,
            "income_goal": self.profile.income_goal,
            "plan": {"completed": 18, "total": 30, "percentage": 60.0, "pp_score": 180, "status": "นักปฏิบัติ"},
            "contacts": {"total": 25, "A": 5, "B": 8, "C": 7, "D": 5},
            "goals": {
                "sponsor": {"target": 8.0, "actual": 5.0, "percentage": 62.5},
                "team_points": {"target": 12000.0, "actual": 9000.0, "percentage": 75.0},
                "income": {"target": 80000.0, "actual": 48000.0, "percentage": 60.0},
            },
            "usage": {"content_creator": 4, "ai_coach": 6},
        }
        self.insight = (
            "**จุดแข็งของสมาชิก**\n- มีวินัยในการทำแผนอย่างต่อเนื่อง\n"
            "**จุดที่ควรปรับปรุง**\n- เพิ่มการติดตามรายชื่อประเภท A\n"
            "**สิ่งที่ควรทำต่อใน 7 วันข้างหน้า**\n- ติดต่อผู้สนใจใหม่วันละ 3 ราย"
        )

    def test_filename_uses_required_format_and_sanitizes_invalid_characters(self) -> None:
        self.assertEqual(member_report_filename("สมชาย ใจดี"), "Member_Report_สมชาย_ใจดี.pdf")
        self.assertEqual(member_report_filename("สมชาย/ใจดี"), "Member_Report_สมชาย_ใจดี.pdf")

    def test_pdf_uses_embedded_thai_fonts_from_assets_folder(self) -> None:
        paths = thai_pdf_font_paths()

        self.assertTrue(thai_pdf_fonts_available())
        self.assertEqual(paths["regular"].as_posix().split("/")[-3:], ["assets", "fonts", "THSarabunNew.ttf"])
        self.assertEqual(paths["bold"].as_posix().split("/")[-3:], ["assets", "fonts", "THSarabunNew-Bold.ttf"])

    def test_pdf_contains_thai_sections_member_data_and_insight(self) -> None:
        pdf = generate_member_report_pdf(self.profile, self.snapshot, self.insight)

        self.assertTrue(pdf.startswith(b"%PDF-"))
        reader = PdfReader(BytesIO(pdf))
        self.assertGreaterEqual(len(reader.pages), 1)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        for expected in (
            "ส่วนที่ 1 ข้อมูลสมาชิก",
            "สมชาย ใจดี",
            "ทีมสุขภาพดี",
            "TEAM-888",
            "คุณหัวหน้า",
            "คุณผู้แนะนำ",
            "Admin",
            "ส่วนที่ 2 ความคืบหน้า",
            "180 PP",
            "ส่วนที่ 3 Workplan",
            "จำนวน A",
            "ส่วนที่ 4 เป้าหมาย",
            "ผลลัพธ์จริง - คะแนนทีม",
            "ส่วนที่ 5 AI Insight",
            "จุดแข็งของสมาชิก",
            "ติดต่อผู้สนใจใหม่วันละ 3 ราย",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
