import unittest

from models import ActionItem, MemberProfile
from services.onboarding_service import build_onboarding_status
from services.progress_service import member_progress_key
from services.workplan_service import create_default_workplan


class OnboardingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = MemberProfile(name="สมาชิกเริ่มต้น", occupation="เจ้าของกิจการ")
        self.key = member_progress_key(self.profile)

    def test_empty_member_has_no_completed_steps(self) -> None:
        status = build_onboarding_status({}, None)
        self.assertEqual(sum(status.values()), 0)

    def test_status_uses_profile_plan_workplan_chat_and_progress(self) -> None:
        workplan = create_default_workplan()
        workplan["contacts"] = [{"name": "ผู้มุ่งหวังหนึ่งราย"}]
        state = {
            "action_plan": [ActionItem(1, "เริ่มต้น", "ภารกิจ", ("ลงมือทำ",), "สำเร็จ")],
            "workplan_by_member": {self.key: workplan},
            "plan_completion_by_member": {self.key: {"1": True}},
            "coach_messages": [{"role": "user", "content": "ผมควรเริ่มอย่างไร"}],
        }

        status = build_onboarding_status(state, self.profile)

        self.assertTrue(all(status.values()))

    def test_empty_default_workplan_does_not_complete_workplan_step(self) -> None:
        state = {"workplan_by_member": {self.key: create_default_workplan()}}
        status = build_onboarding_status(state, self.profile)
        self.assertTrue(status["profile"])
        self.assertFalse(status["workplan"])


if __name__ == "__main__":
    unittest.main()
