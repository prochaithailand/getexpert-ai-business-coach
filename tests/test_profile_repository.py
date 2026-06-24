import unittest

from models import MemberProfile
from services.profile_repository import SessionProfileRepository


class ProfileRepositoryTests(unittest.TestCase):
    def test_old_profile_data_loads_with_team_defaults(self) -> None:
        profile = MemberProfile.from_dict({"name": "สมาชิกเดิม", "occupation": "พนักงานบริษัท"})
        self.assertEqual(profile.team_name, "")
        self.assertEqual(profile.team_id, "")
        self.assertEqual(profile.team_leader, "")
        self.assertEqual(profile.sponsor, "")
        self.assertEqual(profile.role, "Member")

    def test_team_information_is_saved_in_session_state(self) -> None:
        state = {}
        repository = SessionProfileRepository(state)
        profile = MemberProfile(
            name="สมาชิกทีม",
            occupation="เจ้าของกิจการ",
            team_name="ทีมพลังดิจิทัล",
            team_id="TEAM-001",
            team_leader="หัวหน้าทดสอบ",
            sponsor="ผู้แนะนำทดสอบ",
            role="Leader",
        )

        repository.save(profile)

        self.assertEqual(state["member_profile"]["team_name"], "ทีมพลังดิจิทัล")
        self.assertEqual(state["member_profile"]["team_id"], "TEAM-001")
        self.assertEqual(state["member_profile"]["role"], "Leader")
        self.assertEqual(repository.get(), profile)
        self.assertEqual(repository.list_by_team("team-001"), [profile])

    def test_registry_keeps_multiple_member_profiles(self) -> None:
        state = {}
        repository = SessionProfileRepository(state)
        first = MemberProfile(name="สมาชิก ก", occupation="งาน", team_id="T-1")
        second = MemberProfile(name="สมาชิก ข", occupation="งาน", team_id="T-1")
        repository.save(first)
        repository.save(second)

        self.assertEqual([profile.name for profile in repository.list_by_team("T-1")], ["สมาชิก ก", "สมาชิก ข"])

    def test_public_save_cannot_elevate_new_user_to_admin(self) -> None:
        state = {}
        repository = SessionProfileRepository(state)
        repository.save(MemberProfile(name="ผู้ใช้ใหม่", occupation="งาน", role="Admin"))

        self.assertEqual(repository.get().role, "Member")

    def test_admin_can_only_be_assigned_through_internal_path(self) -> None:
        state = {}
        repository = SessionProfileRepository(state)
        profile = MemberProfile(name="ผู้ดูแลระบบ", occupation="เจ้าของระบบ")

        repository.assign_admin_internally(profile)

        self.assertEqual(repository.get().role, "Admin")
        repository.save(repository.get())
        self.assertEqual(repository.get().role, "Admin")

    def test_member_and_leader_cannot_change_admin_assigned_team(self) -> None:
        for role in ("Member", "Leader", "Partner"):
            with self.subTest(role=role):
                email = f"{role.casefold()}@example.com"
                assigned = MemberProfile(
                    name=role, occupation="งาน", team_name="ทีมที่ได้รับมอบหมาย",
                    team_id="TEAM-ADMIN", team_leader="หัวหน้าทีม", sponsor="ผู้แนะนำ",
                    role=role,
                )
                state = {
                    "authenticated_user": {"email": email, "role": role},
                    "member_profiles_by_user": {email: assigned.to_dict()},
                }
                repository = SessionProfileRepository(state)

                repository.save(MemberProfile(
                    name=role, occupation="งานใหม่", team_name="ทีมปลอม",
                    team_id="FORGED", team_leader="เปลี่ยนเอง", sponsor="เปลี่ยนเอง",
                    role=role,
                ))

                saved = repository.get()
                self.assertEqual(saved.team_id, "TEAM-ADMIN")
                self.assertEqual(saved.team_name, "ทีมที่ได้รับมอบหมาย")
                self.assertEqual(saved.team_leader, "หัวหน้าทีม")
                self.assertEqual(saved.sponsor, "เปลี่ยนเอง")
                self.assertEqual(saved.occupation, "งานใหม่")


if __name__ == "__main__":
    unittest.main()
