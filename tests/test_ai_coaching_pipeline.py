import unittest

from ui.ai_coaching_pipeline import PIPELINE_STEPS, THINKING_MESSAGES, _pipeline_html


class AICoachingPipelineTests(unittest.TestCase):
    def test_pipeline_contains_all_six_steps(self) -> None:
        html = _pipeline_html()

        self.assertEqual(len(PIPELINE_STEPS), 6)
        for step, title, description in PIPELINE_STEPS:
            self.assertIn(step, html)
            self.assertIn(title, html)
            self.assertIn(description, html)

    def test_pipeline_contains_thinking_messages_and_main_title(self) -> None:
        html = _pipeline_html()

        self.assertIn("AI Business Coach กำลังวิเคราะห์ธุรกิจของคุณ...", html)
        for message in THINKING_MESSAGES:
            self.assertIn(message, html)

    def test_pipeline_is_presentation_only(self) -> None:
        html = _pipeline_html()

        self.assertNotIn("OpenAI(", html)
        self.assertNotIn("responses.create", html)
        self.assertIn("prefers-reduced-motion", html)


if __name__ == "__main__":
    unittest.main()
