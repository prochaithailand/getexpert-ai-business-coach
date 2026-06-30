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

    def test_myanmar_home_and_profile_translations_are_available(self) -> None:
        expectations = {
            "Home Welcome Back": "ပြန်လည်ကြိုဆိုပါသည်",
            "Home Hero Kicker": "အသင်းဝင်အောင်မြင်မှု",
            "Home Business Area Title": "စီးပွားရေးဖွံ့ဖြိုးရေး",
            "Home Feature Profile Title": "အဖွဲ့ဝင် ပရိုဖိုင်",
            "Home Feature Plan Title": "ရက် ၃၀ အစီအစဉ်",
            "Home Feature Content Title": "ကွန်တင့် ဖန်တီးခြင်း",
            "Home Feature Knowledge Title": "ဗဟုသုတဘဏ်",
            "Home Feature AI Title": "AI နည်းပြ",
            "ยังไม่มีประสบการณ์": "အတွေ့အကြုံ မရှိသေးပါ",
            "ระดับเริ่มต้น (น้อยกว่า 1 ปี)": "စတင်သူအဆင့်",
            "ระดับกลาง (1-3 ปี)": "အလယ်အလတ်အဆင့်",
            "ระดับเชี่ยวชาญ (มากกว่า 3 ปี)": "ကျွမ်းကျင်အဆင့်",
        }
        for key, expected in expectations.items():
            with self.subTest(key=key):
                translated = translate(key, "my")
                self.assertIn(expected, translated)
                self.assertNotEqual(translated, translate(key, "th"))

    def test_core_page_translation_keys_are_available_for_launch_languages(self) -> None:
        required_keys = (
            "Home Welcome Back",
            "Home Hero Kicker",
            "Home Hero Description",
            "Home Feature Profile Title",
            "Home Feature Profile Description",
            "Home Feature Plan Title",
            "Home Feature Content Title",
            "Home Feature Knowledge Title",
            "Home Feature AI Title",
            "ยังไม่มีประสบการณ์",
            "ระดับเริ่มต้น (น้อยกว่า 1 ปี)",
            "ระดับกลาง (1-3 ปี)",
            "ระดับเชี่ยวชาญ (มากกว่า 3 ปี)",
            "Assigned Team Info",
            "Team Name",
            "Team ID",
            "Team Leader",
            "Not Assigned",
            "30-Day Plan Page Title",
            "30-Day Plan Page Description",
            "Action Plan Daily Time",
            "Action Plan Monthly Goal",
            "Action Plan Generate Button",
            "Action Plan Empty Hint",
            "Progress Summary",
            "No Workplan Data Message",
            "เริ่มต้น",
            "กำลังสร้างวินัย",
            "นักปฏิบัติ",
            "ผู้สร้างผลลัพธ์",
            "Workplan Page Description",
            "Prospect Page Description",
            "Dashboard Page Description",
            "Member Dashboard Title",
            "Dashboard Insufficient Data",
            "AI Coach Semantic Ready",
        )
        for language in ("th", "my", "en"):
            with self.subTest(language=language):
                for key in required_keys:
                    self.assertIn(key, TRANSLATIONS[language])
                    self.assertTrue(translate(key, language).strip())

    def test_myanmar_phase_two_ui_translations_are_available(self) -> None:
        expectations = {
            "Member Dashboard Title": "အသင်းဝင် ဒက်ရှ်ဘုတ်",
            "Dashboard Insufficient Data": "အချက်အလက် မလုံလောက်",
            "โพสต์ Facebook": "Facebook ပို့စ်",
            "สร้างการรับรู้": "အသိအမြင်",
            "เพิ่มผู้สนใจใหม่": "စိတ်ဝင်စားသူအသစ်",
            "เชิญเข้าร่วมกิจกรรม": "ဖိတ်ခေါ်",
            "ติดตามลูกค้า": "Follow-up",
            "พัฒนาทีม": "အသင်းအဖွဲ့",
            "ยังไม่ติดต่อ": "မဆက်သွယ်ရသေးပါ",
            "ติดต่อแล้ว": "ဆက်သွယ်ပြီး",
            "ส่งข้อมูลแล้ว": "အချက်အလက်ပို့ပြီး",
            "นัดหมายแล้ว": "ချိန်းဆိုပြီး",
            "นำเสนอแล้ว": "တင်ပြပြီး",
            "กำลังตัดสินใจ": "ဆုံးဖြတ်နေဆဲ",
            "สมัครแล้ว": "စာရင်းသွင်းပြီး",
            "Account Settings Description": "လုံခြုံရေး",
            "Membership Status": "အသင်းဝင် အခြေအနေ",
            "Free Trial": "အခမဲ့",
            "Change Password": "စကားဝှက်",
            "Save New Password": "စကားဝှက်အသစ်",
        }
        for key, expected in expectations.items():
            with self.subTest(key=key):
                translated = translate(key, "my")
                self.assertIn(expected, translated)
                self.assertNotEqual(translated, translate(key, "th"))

    def test_phase_two_translation_keys_exist_for_all_launch_languages(self) -> None:
        required_keys = (
            "Member Dashboard Title",
            "Dashboard Insufficient Data",
            "โพสต์ Facebook",
            "สคริปต์ TikTok",
            "ข้อความบรอดแคสต์ LINE OA",
            "สร้างการรับรู้",
            "เพิ่มผู้สนใจใหม่",
            "เชิญเข้าร่วมกิจกรรม",
            "ติดตามลูกค้า",
            "พัฒนาทีม",
            "ยังไม่ติดต่อ",
            "ติดต่อแล้ว",
            "ส่งข้อมูลแล้ว",
            "นัดหมายแล้ว",
            "นำเสนอแล้ว",
            "กำลังตัดสินใจ",
            "สมัครแล้ว",
            "ไม่สนใจ",
            "นัดหมาย",
            "ปฏิเสธ",
            "Account Settings Description",
            "Login Required For Password",
            "Membership Status",
            "Membership Status Line",
            "Active Subscription",
            "Free Trial",
            "Pending Payment",
            "Expired Subscription",
            "Suspended Subscription",
            "Trial Expiry Date",
            "Trial Days Remaining",
            "Change Password",
            "New Password",
            "Confirm New Password",
            "Save New Password",
            "Password Changed Success",
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
