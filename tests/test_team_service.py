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

    def test_leader_generates_invite_and_member_joins_without_role_change(self) -> None:
        leader = AppUser("leader@example.com", "หัวหน้าทีม", "Leader")
        member = AppUser("member@example.com", "สมาชิกใหม่", "Member")
        state = {
            USER_STORE_KEY: {
                leader.email: leader.to_dict(),
                member.email: member.to_dict(),
            },
            "teams": {
                "TEAM-INVITE": Team(
                    "ทีมคำเชิญ", "TEAM-INVITE", leader.full_name,
                    leader_email=leader.email,
                ).to_dict(),
            },
        }
        repository = SessionTeamRepository(state)

        invited_team = repository.generate_invite_code("TEAM-INVITE", leader)
        joined = repository.join_with_invite(invited_team.invite_code, member)

        self.assertTrue(invited_team.invite_code)
        self.assertEqual(joined.team_id, "TEAM-INVITE")
        self.assertEqual(joined.role, "Member")
        self.assertEqual(joined.invited_by, leader.email)
        self.assertTrue(joined.joined_at)
        self.assertEqual(state[USER_STORE_KEY][member.email]["role"], "Member")

    def test_member_cannot_be_assigned_to_a_different_team(self) -> None:
        member = AppUser("member@example.com", "สมาชิกทีมเดิม", "Member")
        profile = MemberProfile(
            name=member.full_name,
            occupation="งาน",
            team_name="ทีมเดิม",
            team_id="TEAM-OLD",
            role="Member",
        )
        state = {
            USER_STORE_KEY: {member.email: member.to_dict()},
            "member_profiles_by_user": {member.email: profile.to_dict()},
            "teams": {
                "TEAM-OLD": Team("ทีมเดิม", "TEAM-OLD", "หัวหน้าเดิม").to_dict(),
                "TEAM-NEW": Team("ทีมใหม่", "TEAM-NEW", "หัวหน้าใหม่").to_dict(),
            },
        }
        repository = SessionTeamRepository(state)

        with self.assertRaisesRegex(
            ValueError,
            "สมาชิกคนนี้อยู่ในทีมอื่นแล้ว กรุณาลบออกจากทีมเดิมก่อน",
        ):
            repository.assign_members("TEAM-NEW", [member])

        self.assertEqual(
            state["member_profiles_by_user"][member.email]["team_id"],
            "TEAM-OLD",
        )

    def test_admin_removes_member_before_assigning_to_another_team(self) -> None:
        member = AppUser("member@example.com", "สมาชิกย้ายทีม", "Member")
        profile = MemberProfile(
            name=member.full_name,
            occupation="งาน",
            team_name="ทีมเดิม",
            team_id="TEAM-OLD",
            team_leader="หัวหน้าเดิม",
            role="Member",
        )
        state = {
            USER_STORE_KEY: {member.email: member.to_dict()},
            "member_profiles_by_user": {member.email: profile.to_dict()},
            "teams": {
                "TEAM-OLD": Team("ทีมเดิม", "TEAM-OLD", "หัวหน้าเดิม").to_dict(),
                "TEAM-NEW": Team("ทีมใหม่", "TEAM-NEW", "หัวหน้าใหม่").to_dict(),
            },
        }
        repository = SessionTeamRepository(state)

        removed = repository.remove_member("TEAM-OLD", member)
        assigned = repository.assign_members("TEAM-NEW", [member])[0]

        self.assertEqual(removed.team_id, "")
        self.assertEqual(removed.role, "Member")
        self.assertEqual(assigned.team_id, "TEAM-NEW")
        self.assertEqual(assigned.role, "Member")

    def test_leader_removes_only_member_from_own_team(self) -> None:
        leader = AppUser("leader@example.com", "หัวหน้าทีม", "Leader")
        other_leader = AppUser("other@example.com", "หัวหน้าทีมอื่น", "Leader")
        member = AppUser("member@example.com", "สมาชิก", "Member")
        profile = MemberProfile(
            name=member.full_name,
            occupation="งาน",
            team_name="ทีมหนึ่ง",
            team_id="TEAM-ONE",
            team_leader=leader.full_name,
            role="Member",
        )
        state = {
            USER_STORE_KEY: {
                leader.email: leader.to_dict(),
                other_leader.email: other_leader.to_dict(),
                member.email: member.to_dict(),
            },
            "member_profiles_by_user": {member.email: profile.to_dict()},
            "teams": {
                "TEAM-ONE": Team(
                    "ทีมหนึ่ง",
                    "TEAM-ONE",
                    leader.full_name,
                    leader_email=leader.email,
                ).to_dict(),
            },
        }
        repository = SessionTeamRepository(state)

        with self.assertRaises(PermissionError):
            repository.remove_member_as_leader("TEAM-ONE", member, other_leader)

        removed = repository.remove_member_as_leader("TEAM-ONE", member, leader)

        self.assertEqual(removed.team_id, "")
        self.assertEqual(removed.role, "Member")


if __name__ == "__main__":
    unittest.main()
