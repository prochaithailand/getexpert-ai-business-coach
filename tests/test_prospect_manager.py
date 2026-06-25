import unittest
from datetime import date, timedelta

from models import MemberProfile
from services.dashboard_service import build_and_save_dashboard
from services.member_activity_service import build_member_activity_context
from services.progress_service import member_progress_key
from services.workplan_service import (
    SessionWorkplanRepository,
    add_contact,
    create_default_workplan,
    delete_contact,
    priority_contacts,
    prospect_summary,
    replace_contacts,
    update_contact,
    update_contact_status,
)
from views.prospect_page import filter_prospects


class ProspectManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = MemberProfile(name="สมาชิก CRM", occupation="เจ้าของกิจการ")

    def test_extended_prospect_fields_survive_add_edit_and_delete(self) -> None:
        workplan = add_contact(
            create_default_workplan(),
            {
                "name": "สมหญิง",
                "phone": "0812345678",
                "age": 32,
                "occupation": "พนักงานบริษัท",
                "income": 35000,
                "province": "เชียงใหม่",
                "category": "A",
                "status": "ส่งข้อมูลแล้ว",
                "notes": "สนใจรายได้เสริมและต้องการข้อมูลเพิ่มเติม",
                "next_follow_up": date(2026, 6, 25),
            },
        )
        prospect = workplan["contacts"][0]
        self.assertEqual(prospect["province"], "เชียงใหม่")
        self.assertEqual(prospect["notes"], "สนใจรายได้เสริมและต้องการข้อมูลเพิ่มเติม")
        self.assertEqual(prospect["next_follow_up"], "2026-06-25")

        edited = dict(prospect, status="นัดหมายแล้ว", province="ลำพูน")
        workplan = replace_contacts(workplan, [edited])
        self.assertEqual(workplan["contacts"][0]["status"], "นัดหมายแล้ว")
        self.assertEqual(workplan["contacts"][0]["province"], "ลำพูน")

        workplan = replace_contacts(workplan, [dict(edited, delete=True)])
        self.assertEqual(workplan["contacts"], [])

    def test_summary_and_priority_use_grade_status_follow_up_and_notes(self) -> None:
        today = date(2026, 6, 21)
        contacts = [
            {
                "name": "เอ เร่งด่วน", "category": "A", "status": "กำลังตัดสินใจ",
                "next_follow_up": (today - timedelta(days=2)).isoformat(), "notes": "ขอคุยหลังเลิกงาน",
            },
            {
                "name": "บี วันนี้", "category": "B", "status": "นัดหมายแล้ว",
                "next_follow_up": today.isoformat(), "notes": "นัดเวลา 19:00 น.",
            },
            {"name": "เอ สมัครแล้ว", "category": "A", "status": "สมัครแล้ว"},
            {"name": "ซี ทั่วไป", "category": "C", "status": "ยังไม่ติดต่อ"},
        ]

        summary = prospect_summary(contacts)
        prioritized = priority_contacts(contacts, today=today)

        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["A"], 2)
        self.assertEqual(summary["signed_up"], 1)
        self.assertEqual(summary["appointments"], 1)
        self.assertEqual(prioritized[0]["name"], "เอ เร่งด่วน")
        self.assertEqual(prioritized[0]["days_until_follow_up"], -2)
        self.assertNotIn("เอ สมัครแล้ว", [item["name"] for item in prioritized])

    def test_crm_and_dashboard_read_the_same_workplan_contacts(self) -> None:
        state = {}
        repository = SessionWorkplanRepository(state)
        workplan = add_contact(
            repository.get(self.profile),
            {"name": "ผู้มุ่งหวัง A", "category": "A", "status": "นัดหมายแล้ว"},
        )
        repository.save(self.profile, workplan)

        dashboard = build_and_save_dashboard(state, self.profile)

        self.assertEqual(
            state["workplan_by_member"][member_progress_key(self.profile)]["contacts"][0]["name"],
            "ผู้มุ่งหวัง A",
        )
        assert dashboard is not None
        self.assertEqual(dashboard["contacts"]["total"], 1)
        self.assertEqual(dashboard["contacts"]["A"], 1)
        self.assertEqual(dashboard["contacts"]["appointments"], 1)
        coach_context = build_member_activity_context(state, self.profile)
        self.assertIn("ผู้มุ่งหวัง A", coach_context.summary)
        self.assertIn("สถานะ นัดหมายแล้ว", coach_context.summary)

    def test_single_prospect_actions_update_and_delete_immediately(self) -> None:
        workplan = add_contact(
            create_default_workplan(),
            {"name": "รายชื่อเดิม", "category": "C", "status": "ยังไม่ติดต่อ"},
        )
        contact_id = workplan["contacts"][0]["id"]

        workplan = update_contact_status(workplan, contact_id, "ติดต่อแล้ว")
        self.assertEqual(workplan["contacts"][0]["status"], "ติดต่อแล้ว")

        workplan = update_contact(
            workplan,
            contact_id,
            {
                "name": "รายชื่อแก้ไขแล้ว",
                "phone": "0800000000",
                "age": 45,
                "occupation": "เจ้าของร้าน",
                "income": 50000,
                "province": "ขอนแก่น",
                "category": "A",
                "status": "นัดหมายแล้ว",
                "notes": "นัดวันเสาร์",
                "next_follow_up": "2026-06-28",
            },
        )
        prospect = workplan["contacts"][0]
        self.assertEqual(prospect["name"], "รายชื่อแก้ไขแล้ว")
        self.assertEqual(prospect["category"], "A")
        self.assertEqual(prospect["status"], "นัดหมายแล้ว")
        self.assertEqual(prospect["next_follow_up"], "2026-06-28")

        workplan = delete_contact(workplan, contact_id)
        self.assertEqual(workplan["contacts"], [])

    def test_status_options_preserve_contacted_and_not_interested(self) -> None:
        workplan = add_contact(
            create_default_workplan(),
            {"name": "ติดต่อแล้ว", "status": "ติดต่อแล้ว"},
        )
        workplan = add_contact(
            workplan,
            {"name": "ไม่สนใจ", "status": "ไม่สนใจ"},
        )
        self.assertEqual([item["status"] for item in workplan["contacts"]], ["ติดต่อแล้ว", "ไม่สนใจ"])
        self.assertEqual(priority_contacts(workplan["contacts"])[0]["name"], "ติดต่อแล้ว")

    def test_search_and_filters_preserve_matching_prospect_ids(self) -> None:
        contacts = [
            {
                "id": "prospect-a",
                "name": "สมชาย เจ้าของร้าน",
                "phone": "081-234-5678",
                "province": "ชุมพร",
                "area": "หลังสวน",
                "occupation": "เจ้าของร้านกาแฟ",
                "status": "นัดหมายแล้ว",
                "category": "A",
                "notes": "สนใจนัดคุยวันเสาร์",
                "line_id": "somchai.line",
                "interest": "รายได้เสริม",
                "pain_point": "มีเวลาจำกัด",
                "previous_experience": "ขายออนไลน์",
            },
            {
                "id": "prospect-b",
                "name": "มาลี",
                "phone": "0899999999",
                "province": "เชียงใหม่",
                "occupation": "ครู",
                "status": "ไม่สนใจ",
                "category": "C",
            },
        ]

        self.assertEqual(filter_prospects(contacts, "สมชาย")[0]["id"], "prospect-a")
        self.assertEqual(filter_prospects(contacts, "0812345678")[0]["id"], "prospect-a")
        self.assertEqual(filter_prospects(contacts, "ชุมพร")[0]["id"], "prospect-a")
        self.assertEqual(
            [item["id"] for item in filter_prospects(contacts, status_filter="นัดหมาย")],
            ["prospect-a"],
        )
        self.assertEqual(
            [item["id"] for item in filter_prospects(contacts, category_filter="C")],
            ["prospect-b"],
        )
        self.assertEqual(filter_prospects(contacts, "ไม่พบข้อมูล"), [])


if __name__ == "__main__":
    unittest.main()
