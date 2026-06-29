import unittest

from brand_config import get_brand, resolve_brand_key
from translations import LANGUAGE_OPTIONS, TRANSLATIONS, translate, translate_nav


class BrandConfigTests(unittest.TestCase):
    def test_default_brand_is_getexpert(self) -> None:
        brand = get_brand({}, {})

        self.assertEqual(brand["key"], "getexpert")
        self.assertEqual(brand["app_name"], "GetExpert AI Business Coach")

    def test_tglife_brand_can_be_selected_from_environment(self) -> None:
        brand = get_brand({}, {"APP_BRAND": "tglife"})

        self.assertEqual(brand["key"], "tglife")
        self.assertEqual(brand["app_name"], "TG Life AI Business Coach")
        self.assertEqual(brand["powered_by"], "powered by GetExpert")

    def test_unknown_brand_falls_back_to_getexpert(self) -> None:
        self.assertEqual(resolve_brand_key({}, {"APP_BRAND": "unknown"}), "getexpert")

    def test_language_selector_options_are_available(self) -> None:
        self.assertEqual(tuple(LANGUAGE_OPTIONS.keys()), ("th", "my", "en"))
        self.assertEqual(LANGUAGE_OPTIONS["th"], "ไทย")
        self.assertEqual(LANGUAGE_OPTIONS["my"], "မြန်မာ")
        self.assertEqual(LANGUAGE_OPTIONS["en"], "English")

    def test_myanmar_menu_translations_are_available(self) -> None:
        self.assertEqual(translate_nav("Dashboard สมาชิก", "my"), "ဒက်ရှ်ဘုတ်")
        self.assertEqual(translate_nav("ถามคำถาม AI", "my"), "AI ကို မေးရန်")
        self.assertEqual(translate_nav("ผู้มุ่งหวัง", "my"), "အလားအလာရှိသူများ")
        self.assertEqual(translate("30-Day Plan", "my"), "ရက် ၃၀ အစီအစဉ်")

    def test_myanmar_auth_translations_are_available(self) -> None:
        self.assertEqual(translate("language_selector", "my"), "ဘာသာစကား / Language")
        self.assertEqual(translate("Sign Up", "my"), "စာရင်းသွင်းရန်")
        self.assertEqual(translate("Full Name", "my"), "အမည် အပြည့်အစုံ")
        self.assertEqual(translate("Email", "my"), "အီးမေးလ်")
        self.assertEqual(translate("Password", "my"), "စကားဝှက်")
        self.assertEqual(translate("Role", "my"), "အခန်းကဏ္ဍ")
        self.assertIn("အီးမေးလ်များ", translate("Email Consent", "my"))
        self.assertIn("AI ဖြင့်", translate("Marketing Opt In", "my"))

    def test_myanmar_onboarding_and_ai_source_translations_are_available(self) -> None:
        self.assertIn("စတင်အသုံးပြုရန်", translate("Onboarding Title", "my"))
        self.assertIn("ပရိုဖိုင်ဖြည့်ရန်", translate("Onboarding CTA Profile", "my"))
        self.assertIn("ရက် ၃၀", translate("Onboarding CTA Plan", "my"))
        self.assertIn("AI Coach", translate("Onboarding CTA AI", "my"))
        self.assertIn("Dashboard", translate("Onboarding CTA Dashboard", "my"))
        self.assertEqual(translate("Answer Source OpenAI", "my"), "အဖြေရင်းမြစ်: OpenAI")
        self.assertIn("အရန်အဖြေ", translate("Answer Source Fallback", "my"))
        self.assertEqual(translate("Reference Heading", "my"), "ကိုးကားအချက်အလက်များ")
        self.assertIn("မလုံလောက်သေးပါ", translate("Reference Missing", "my"))

    def test_core_page_translation_keys_are_available_for_launch_languages(self) -> None:
        required_keys = (
            "30-Day Plan Page Title",
            "30-Day Plan Page Description",
            "Action Plan Daily Time",
            "Action Plan Monthly Goal",
            "Action Plan Generate Button",
            "Action Plan Empty Hint",
            "Progress Summary",
            "Workplan Page Description",
            "Prospect Page Description",
            "Dashboard Page Description",
            "AI Coach Semantic Ready",
        )
        for language in ("th", "my", "en"):
            with self.subTest(language=language):
                for key in required_keys:
                    self.assertIn(key, TRANSLATIONS[language])
                    self.assertTrue(translate(key, language).strip())

    def test_missing_translation_key_falls_back_safely(self) -> None:
        self.assertEqual(translate("Unknown Launch Key", "my"), "Unknown Launch Key")
        self.assertEqual(translate("30-Day Plan Page Title", "unknown"), "แผนปฏิบัติการ 30 วัน")


if __name__ == "__main__":
    unittest.main()
