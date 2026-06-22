import unittest

from models import MemberProfile
from services.progress_service import calculate_plan_progress, member_progress_key


class ProgressServiceTests(unittest.TestCase):
    def test_progress_counts_pp_and_remaining_days(self) -> None:
        statuses = {str(day): day <= 12 for day in range(1, 31)}
        summary = calculate_plan_progress(statuses)
        self.assertEqual(summary.total_days, 30)
        self.assertEqual(summary.completed_days, 12)
        self.assertEqual(summary.remaining_days, 18)
        self.assertEqual(summary.pp_score, 120)
        self.assertEqual(summary.percentage, 40.0)
        self.assertEqual(summary.status_level, "กำลังสร้างวินัย")

    def test_status_levels_follow_required_percentage_ranges(self) -> None:
        cases = (
            (0, "เริ่มต้น"),
            (7, "เริ่มต้น"),
            (8, "กำลังสร้างวินัย"),
            (15, "กำลังสร้างวินัย"),
            (16, "นักปฏิบัติ"),
            (22, "นักปฏิบัติ"),
            (23, "ผู้สร้างผลลัพธ์"),
            (30, "ผู้สร้างผลลัพธ์"),
        )
        for completed_days, expected_level in cases:
            with self.subTest(completed_days=completed_days):
                statuses = {str(day): day <= completed_days for day in range(1, 31)}
                self.assertEqual(calculate_plan_progress(statuses).status_level, expected_level)

    def test_member_progress_key_is_stable_and_member_specific(self) -> None:
        first = MemberProfile(name="นิดา", age=30, occupation="ครู")
        same_member = MemberProfile(name=" นิดา ", age=30, occupation=" ครู ", income_goal=90000)
        second = MemberProfile(name="มาลี", age=30, occupation="ครู")
        self.assertEqual(member_progress_key(first), member_progress_key(same_member))
        self.assertNotEqual(member_progress_key(first), member_progress_key(second))


if __name__ == "__main__":
    unittest.main()
