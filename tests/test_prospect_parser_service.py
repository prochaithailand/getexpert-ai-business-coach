import unittest
from datetime import date

from models import AppUser
from services.prospect_parser_service import ProspectDraft, parse_prospect_text
from services.workplan_service import add_contact, create_default_workplan
from views.prospect_page import _can_use_ai_prospect_entry


class ProspectParserServiceTests(unittest.TestCase):
    def test_parses_identity_phone_occupation_and_location(self) -> None:
        draft = parse_prospect_text(
            "ชื่อสมชาย อายุ 42 ปี เป็นเจ้าของร้านกาแฟ เบอร์ 081-234-5678 "
            "จังหวัดปทุมธานี อยู่รังสิต นัดคุยวันเสาร์นี้",
            today=date(2026, 6, 25),
        )

        self.assertEqual(draft.name, "สมชาย")
        self.assertEqual(draft.age, 42)
        self.assertEqual(draft.occupation, "เจ้าของร้านกาแฟ")
        self.assertEqual(draft.phone, "0812345678")
        self.assertEqual(draft.province, "ปทุมธานี")
        self.assertEqual(draft.area, "รังสิต")
        self.assertEqual(draft.status, "นัดหมายแล้ว")
        self.assertEqual(draft.next_follow_up, "2026-06-27")

    def test_parses_line_interest_need_and_experience(self) -> None:
        draft = parse_prospect_text(
            "ชื่อมาลี LINE ID: malee.work สนใจรายได้เสริม "
            "ต้องการมีเวลาให้ครอบครัว เคยขายสินค้าออนไลน์ เกรด B"
        )

        self.assertEqual(draft.line_id, "malee.work")
        self.assertEqual(draft.interest, "รายได้เสริม")
        self.assertEqual(draft.pain_point, "มีเวลาให้ครอบครัว")
        self.assertEqual(draft.previous_experience, "ขายสินค้าออนไลน์")
        self.assertEqual(draft.category, "B")

    def test_incomplete_text_does_not_invent_personal_data(self) -> None:
        draft = parse_prospect_text("สนใจเรียนรู้ธุรกิจเพิ่มเติม")

        self.assertEqual(draft.name, "")
        self.assertEqual(draft.age, 0)
        self.assertEqual(draft.phone, "")
        self.assertEqual(draft.line_id, "")
        self.assertEqual(draft.status, "")
        self.assertEqual(draft.category, "")
        self.assertEqual(draft.interest, "เรียนรู้ธุรกิจเพิ่มเติม")

    def test_parser_only_creates_draft_until_confirmed_by_caller(self) -> None:
        workplan = create_default_workplan()
        draft = parse_prospect_text("ชื่อสมใจ อายุ 35 ปี")

        self.assertEqual(workplan["contacts"], [])
        confirmed = add_contact(workplan, draft.to_dict())
        self.assertEqual(len(confirmed["contacts"]), 1)
        self.assertEqual(confirmed["contacts"][0]["name"], "สมใจ")

    def test_new_json_fields_survive_contact_normalization(self) -> None:
        contact = add_contact(
            create_default_workplan(),
            ProspectDraft(
                name="สมหญิง",
                line_id="somying.line",
                area="บางนา",
                interest="รายได้เสริม",
                pain_point="มีเวลาจำกัด",
                previous_experience="ขายออนไลน์",
            ).to_dict(),
        )["contacts"][0]

        self.assertEqual(contact["line_id"], "somying.line")
        self.assertEqual(contact["area"], "บางนา")
        self.assertEqual(contact["interest"], "รายได้เสริม")
        self.assertEqual(contact["pain_point"], "มีเวลาจำกัด")
        self.assertEqual(contact["previous_experience"], "ขายออนไลน์")
        self.assertNotIn("email", contact)

    def test_subscription_guard_allows_active_and_admin_only(self) -> None:
        self.assertTrue(
            _can_use_ai_prospect_entry(
                AppUser("active@example.com", "Active", subscription_status="active")
            )
        )
        for status in ("pending_payment", "expired", "suspended"):
            self.assertFalse(
                _can_use_ai_prospect_entry(
                    AppUser("locked@example.com", "Locked", subscription_status=status)
                )
            )
        self.assertTrue(
            _can_use_ai_prospect_entry(
                AppUser("admin@example.com", "Admin", role="Admin", subscription_status="suspended")
            )
        )


if __name__ == "__main__":
    unittest.main()
