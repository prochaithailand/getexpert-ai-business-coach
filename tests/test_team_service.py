import unittest

from models import AppUser, MemberProfile, Team
from services.auth_service import USER_STORE_KEY
from services.team_service import SessionTeamRepository, can_manage_teams, resolve_profile_team


class TeamServiceTests(unittest.TestCase):
    def test_create_update_and_delete_team_syncs_current_profile(self) -> None:
        profile = MemberProfile(
            name="สมาชิกทีม",
            occupation="เจ้าของกิจการ",
            team_name="ทีมเดิม",
            team_id="TEAM-OLD",
            team_leader="หัวหน้าเดิม",
            sponsor="ผู้แนะนำสมาชิก",
            role="Leader",
        )
        state = {"member_profile": profile.to_dict()}
        repository = SessionTeamRepository(state)
        created = repository.create(Team("ทีมเดิม", "team-old", "หัวหน้าเดิม", "ผู้สนับสนุนหลัก", "หมายเหตุ"))

        self.assertEqual(created.team_id, "TEAM-OLD")
        self.assertEqual(repository.get("team-old"), created)
        with self.assertRaises(ValueError):
            repository.create(created)

        updated = repository.update(
            "TEAM-OLD",
            Team("ทีมใหม่", "team-new", "หัวหน้าใหม่", "ผู้สนับสนุนใหม่", "ปรับข้อมูลแล้ว"),
        )
        self.assertIsNone(repository.get("TEAM-OLD"))
        self.assertEqual(updated.team_id, "TEAM-NEW")
        self.assertEqual(state["member_profile"]["team_name"], "ทีมใหม่")
        self.assertEqual(state["member_profile"]["team_id"], "TEAM-NEW")
        self.assertEqual(state["member_profile"]["team_leader"], "หัวหน้าใหม่")
        self.assertEqual(state["member_profile"]["sponsor"], "ผู้แนะนำสมาชิก")

        repository.delete("TEAM-NEW")
        self.assertEqual(repository.list(), [])
        self.assertEqual(state["member_profile"]["team_name"], "")
        self.assertEqual(state["member_profile"]["team_id"], "")
        self.assertEqual(state["member_profile"]["team_leader"], "")
        self.assertEqual(state["member_profile"]["sponsor"], "ผู้แนะนำสมาชิก")

    def test_legacy_profile_team_is_migrated_and_resolved(self) -> None:
        profile = MemberProfile(
            name="สมาชิกเดิม",
            occupation="พนักงานบริษัท",
            team_name="ทีมจากโปรไฟล์เดิม",
            team_id="LEGACY-1",
            team_leader="หัวหน้าเดิม",
            sponsor="ผู้แนะนำเดิม",
        )
        state: dict = {}
        repository = SessionTeamRepository(state)

        migrated = repository.ensure_profile_team(profile)

        self.assertIsNotNone(migrated)
        self.assertEqual(resolve_profile_team(state, profile), migrated)
        self.assertEqual(migrated.primary_sponsor, "ผู้แนะนำเดิม")

    def test_only_complete_leader_or_admin_can_manage_teams(self) -> None:
        self.assertFalse(can_manage_teams(None))
        self.assertFalse(can_manage_teams(MemberProfile(name="สมาชิก", occupation="งาน", role="Member")))
        self.assertFalse(can_manage_teams(MemberProfile(name="ผู้นำ", occupation="งาน", role="Leader")))
        self.assertTrue(can_manage_teams(MemberProfile(name="ผู้ดูแล", occupation="งาน", role="Admin")))

    def test_admin_assigns_leader_and_members_to_team(self) -> None:
        leader = AppUser("leader@example.com", "หัวหน้าคนใหม่", "Member")
        member = AppUser("member@example.com", "สมาชิกทีม", "Member")
        state = {
            USER_STORE_KEY: {
                leader.email: leader.to_dict(),
                member.email: member.to_dict(),
            },
            "member_profiles_by_user": {
                member.email: MemberProfile(name="สมาชิกทีม", occupation="พนักงาน").to_dict(),
            },
        }
        repository = SessionTeamRepository(state)
        repository.create(Team("ทีมดิจิทัล", "TEAM-DIGITAL", "ยังไม่กำหนด"))

        updated_team = repository.assign_leader("TEAM-DIGITAL", leader)
        assigned = repository.assign_members("TEAM-DIGITAL", [member])

        self.assertEqual(updated_team.leader, "หัวหน้าคนใหม่")
        self.assertEqual(state[USER_STORE_KEY][leader.email]["role"], "Leader")
        self.assertEqual(state["member_profiles_by_user"][leader.email]["team_id"], "TEAM-DIGITAL")
        self.assertEqual(state["member_profiles_by_user"][leader.email]["role"], "Leader")
        self.assertEqual(assigned[0].team_id, "TEAM-DIGITAL")
        self.assertEqual(state["member_profiles_by_user"][member.email]["role"], "Member")

    def test_admin_account_cannot_be_assigned_to_team(self) -> None:
        state = {}
        repository = SessionTeamRepository(state)
        repository.create(Team("ทีมทดสอบ", "TEAM-TEST", "ยังไม่กำหนด"))
        admin = AppUser("admin@example.com", "ผู้ดูแล", "Admin")

        with self.assertRaises(ValueError):
            repository.assign_leader("TEAM-TEST", admin)
        with self.assertRaises(ValueError):
            repository.assign_members("TEAM-TEST", [admin])


if __name__ == "__main__":
    unittest.main()
