import unittest

from models import MemberProfile
from services.workplan_service import (
    SessionWorkplanRepository,
    add_contact,
    completion_percentage,
    contact_counts,
    create_default_workplan,
    goal_summary,
    replace_contacts,
    replace_weekly_goals,
)


class WorkplanServiceTests(unittest.TestCase):
    def test_default_workplan_has_twelve_weeks_for_every_goal(self) -> None:
        workplan = create_default_workplan()
        self.assertEqual(set(workplan["goals"]), {"sponsor", "team_points", "income"})
        for rows in workplan["goals"].values():
            self.assertEqual(len(rows), 12)
            self.assertEqual([row["week"] for row in rows], list(range(1, 13)))

    def test_contact_add_edit_delete_and_category_counts(self) -> None:
        workplan = add_contact(
            create_default_workplan(),
            {
                "name": "สมชาย",
                "age": 35,
                "occupation": "พนักงานบริษัท",
                "status": "ติดต่อแล้ว",
                "income": 25000,
                "phone": "0812345678",
                "category": "A",
            },
        )
        contact_id = workplan["contacts"][0]["id"]
        self.assertEqual(contact_counts(workplan["contacts"]), {"total": 1, "A": 1, "B": 0, "C": 0, "D": 0})

        edited = dict(workplan["contacts"][0], name="สมชาย ใหม่", category="B")
        workplan = replace_contacts(workplan, [edited])
        self.assertEqual(workplan["contacts"][0]["id"], contact_id)
        self.assertEqual(workplan["contacts"][0]["name"], "สมชาย ใหม่")
        self.assertEqual(contact_counts(workplan["contacts"])["B"], 1)

        workplan = replace_contacts(workplan, [dict(edited, delete=True)])
        self.assertEqual(workplan["contacts"], [])

    def test_weekly_targets_and_completion_percentage(self) -> None:
        self.assertEqual(completion_percentage(10, 5), 50)
        self.assertEqual(completion_percentage(10, 15), 100)
        self.assertEqual(completion_percentage(0, 5), 0)

        workplan = replace_weekly_goals(
            create_default_workplan(),
            "sponsor",
            [{"week": 1, "target": 4, "actual": 2}, {"week": 2, "target": 6, "actual": 3}],
        )
        self.assertEqual(goal_summary(workplan["goals"]["sponsor"]), {"target": 10.0, "actual": 5.0, "percentage": 50.0})

    def test_session_repository_persists_and_isolates_members(self) -> None:
        state = {}
        first = MemberProfile(name="สมาชิกหนึ่ง", occupation="เจ้าของกิจการ")
        second = MemberProfile(name="สมาชิกสอง", occupation="พนักงานบริษัท")
        repository = SessionWorkplanRepository(state)

        first_plan = add_contact(repository.get(first), {"name": "ผู้มุ่งหวัง A", "category": "A"})
        repository.save(first, first_plan)

        self.assertEqual(repository.get(first)["contacts"][0]["name"], "ผู้มุ่งหวัง A")
        self.assertEqual(repository.get(second)["contacts"], [])


if __name__ == "__main__":
    unittest.main()
