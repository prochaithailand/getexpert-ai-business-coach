import unittest

from views.dashboard_page import (
    _chart_values,
    _dashboard_chart_entries,
    _progress_chart_spec,
    _safe_number,
)


class DashboardChartTests(unittest.TestCase):
    def test_thirty_day_progress_chart_uses_total_and_completed_values(self) -> None:
        values = _chart_values(30, 11)
        spec = _progress_chart_spec(
            values,
            item_field="รายการ",
            value_field="ค่า",
            unit="วัน",
        )

        self.assertEqual(spec["data"]["values"][0]["ค่า"], 30)
        self.assertEqual(spec["data"]["values"][1]["ค่า"], 11)
        self.assertNotIn("values", spec)

    def test_workplan_target_bar_renders_when_actual_is_zero(self) -> None:
        snapshot = {
            "plan": {"total": 30, "completed": 0},
            "goals": {
                "sponsor": {"target": "4", "actual": 0},
                "team_points": {"target": 0, "actual": 0},
                "income": {"target": 0, "actual": 0},
            },
        }

        charts, goals_empty = _dashboard_chart_entries(snapshot)

        self.assertFalse(goals_empty)
        self.assertEqual(charts[0][1:3], (30, 0))
        self.assertEqual(charts[1][1:3], ("4", 0))

    def test_empty_goal_state_when_all_workplan_targets_are_zero(self) -> None:
        snapshot = {
            "plan": {"total": 30, "completed": 11},
            "goals": {
                "sponsor": {"target": 0, "actual": 0},
                "team_points": {"target": None, "actual": ""},
                "income": {"target": "invalid", "actual": 0},
            },
        }

        charts, goals_empty = _dashboard_chart_entries(snapshot)

        self.assertTrue(goals_empty)
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0][1:3], (30, 11))

    def test_safe_number_normalizes_dashboard_chart_values(self) -> None:
        cases = (
            (None, 0.0),
            ("", 0.0),
            ("100", 100.0),
            ("1,250.5", 1250.5),
            ("not-a-number", 0.0),
            (-5, 0.0),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(_safe_number(value), expected)


if __name__ == "__main__":
    unittest.main()
