import unittest

from models import MemberProfile, Team
from services.profile_repository import SessionProfileRepository
from services.progress_service import member_progress_key
from services.team_dashboard_service import (
    build_team_dashboard,
    rule_based_team_insight,
    rule_based_team_coach_answer,
    team_dashboard_context,
)
from services.workplan_service import add_contact, create_default_workplan, replace_weekly_goals


class TeamDashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.leader = MemberProfile(
            name="หัวหน้าทีม", occupation="ผู้นำธุรกิจ", team_name="ทีมทดสอบ",
            team_id="TEAM-01", team_leader="หัวหน้าทีม", role="Leader",
        )
        self.member = MemberProfile(
            name="สมาชิกหนึ่ง", occupation="พนักงาน", team_name="ทีมทดสอบ",
            team_id="TEAM-01", team_leader="หัวหน้าทีม", role="Member",
        )
        self.other_team = MemberProfile(
            name="สมาชิกต่างทีม", occupation="เจ้าของกิจการ", team_name="ทีมอื่น",
            team_id="TEAM-02", team_leader="หัวหน้าอื่น", role="Member",
        )

    def test_dashboard_aggregates_only_members_with_same_team_id(self) -> None:
        state = {
            "teams": {
                "TEAM-01": Team("ทีมทะเบียนกลาง", "TEAM-01", "ผู้นำทะเบียน").to_dict(),
                "TEAM-02": Team("ทีมอื่น", "TEAM-02", "หัวหน้าอื่น").to_dict(),
            }
        }
        profiles = SessionProfileRepository(state)
        for profile in (self.leader, self.member, self.other_team):
            profiles.save(profile)
        state["member_profile"] = self.leader.to_dict()

        leader_plan = create_default_workplan()
        leader_plan = add_contact(
            leader_plan, {"name": "รายชื่อ A นัดหมาย", "category": "A", "status": "นัดหมายแล้ว"}
        )
        leader_plan = add_contact(
            leader_plan, {"name": "รายชื่อ A สมัคร", "category": "A", "status": "สมัครแล้ว"}
        )
        leader_plan = add_contact(leader_plan, {"name": "รายชื่อ B", "category": "B"})
        leader_plan = replace_weekly_goals(leader_plan, "sponsor", [{"week": 1, "target": 2, "actual": 1}])
        member_plan = add_contact(create_default_workplan(), {"name": "รายชื่อ C", "category": "C"})
        state["workplan_by_member"] = {
            member_progress_key(self.leader): leader_plan,
            member_progress_key(self.member): member_plan,
        }
        state["plan_completion_by_member"] = {
            member_progress_key(self.leader): {str(day): True for day in range(1, 11)},
            member_progress_key(self.member): {str(day): True for day in range(1, 6)},
        }

        snapshot = build_team_dashboard(state, self.leader)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["team_name"], "ทีมทะเบียนกลาง")
        self.assertEqual(snapshot["team_leader"], "ผู้นำทะเบียน")
        self.assertEqual(snapshot["total_members"], 2)
        self.assertEqual(snapshot["active_members"], 2)
        self.assertEqual(snapshot["total_pp"], 150)
        self.assertEqual(snapshot["average_completion"], 25)
        self.assertEqual(snapshot["total_prospects"], 4)
        self.assertEqual(snapshot["appointments"], 1)
        self.assertEqual(snapshot["signed_up"], 1)
        self.assertEqual(snapshot["grades"], {"A": 2, "B": 1, "C": 1, "D": 0})
        self.assertEqual(snapshot["pipeline"], {
            "ยังไม่ติดต่อ": 2,
            "ติดต่อแล้ว": 0,
            "นัดหมาย": 1,
            "นำเสนอ": 0,
            "สมัครสมาชิก": 1,
        })
        self.assertEqual(snapshot["progress_distribution"], {
            "completed_100": 0,
            "above_80": 0,
            "above_50": 0,
            "below_50": 2,
        })
        self.assertEqual([member["name"] for member in snapshot["members"]], ["สมาชิกหนึ่ง", "หัวหน้าทีม"])
        self.assertIn("รหัสทีม TEAM-01", team_dashboard_context(snapshot))
        self.assertIn("นัดหมายแล้ว 1", team_dashboard_context(snapshot))
        self.assertIn("กิจกรรมล่าสุด", team_dashboard_context(snapshot))

        insight = rule_based_team_insight(snapshot)
        for heading in (
            "สมาชิกที่ทำผลงานดีที่สุด", "สมาชิกที่ต้องการความช่วยเหลือ",
            "ความคืบหน้าของทีม", "งานที่ควรโฟกัสในสัปดาห์นี้",
        ):
            self.assertIn(heading, insight)
        self.assertIn("รายชื่อ A นัดหมาย", rule_based_team_coach_answer(snapshot, "ใครมีโอกาสปิดการสมัครสูง"))
        self.assertIn("ควรได้รับการโค้ชเพิ่มเติม", rule_based_team_coach_answer(snapshot, "สมาชิกคนใดต้องการความช่วยเหลือ"))

    def test_dashboard_uses_persisted_pp_scores(self) -> None:
        state = {}
        SessionProfileRepository(state).save(self.leader)
        key = member_progress_key(self.leader)
        state["pp_scores_by_member"] = {key: 275}

        snapshot = build_team_dashboard(state, self.leader)

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["total_pp"], 275)
        self.assertEqual(snapshot["members"][0]["pp"], 275)

    def test_leader_cannot_request_another_team_but_admin_can(self) -> None:
        state = {
            "teams": {
                "TEAM-01": Team("ทีมหนึ่ง", "TEAM-01", "หัวหน้าทีม").to_dict(),
                "TEAM-02": Team("ทีมสอง", "TEAM-02", "หัวหน้าสอง").to_dict(),
            }
        }
        profiles = SessionProfileRepository(state)
        profiles.save(self.leader)
        profiles.save(self.other_team)

        self.assertIsNone(build_team_dashboard(state, self.leader, "TEAM-02"))
        admin = MemberProfile(name="ผู้ดูแล", occupation="ระบบ", role="Admin")
        snapshot = build_team_dashboard(state, admin, "TEAM-02")
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot["team_id"], "TEAM-02")
        self.assertEqual([member["name"] for member in snapshot["members"]], ["สมาชิกต่างทีม"])

    def test_dashboard_requires_complete_profile_with_team(self) -> None:
        self.assertIsNone(build_team_dashboard({}, None))
        self.assertIsNone(build_team_dashboard({}, MemberProfile(name="ไม่มีทีม", occupation="งาน")))


if __name__ == "__main__":
    unittest.main()
