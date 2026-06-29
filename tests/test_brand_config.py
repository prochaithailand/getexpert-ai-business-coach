import unittest

from brand_config import get_brand, resolve_brand_key
from translations import translate, translate_nav


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

    def test_myanmar_menu_translations_are_available(self) -> None:
        self.assertEqual(translate_nav("Dashboard สมาชิก", "my"), "ဒက်ရှ်ဘုတ်")
        self.assertEqual(translate_nav("ถามคำถาม AI", "my"), "AI ကို မေးရန်")
        self.assertEqual(translate_nav("ผู้มุ่งหวัง", "my"), "အလားအလာရှိသူများ")
        self.assertEqual(translate("30-Day Plan", "my"), "ရက် ၃၀ အစီအစဉ်")


if __name__ == "__main__":
    unittest.main()

