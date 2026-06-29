from __future__ import annotations


LANGUAGE_OPTIONS: dict[str, str] = {
    "th": "ไทย",
    "my": "မြန်မာ",
    "en": "English",
}

DEFAULT_LANGUAGE = "th"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "th": {
        "language_selector": "ภาษา / Language",
        "Dashboard": "Dashboard สมาชิก",
        "AI Coach": "ถามคำถาม AI",
        "Workplan": "Workplan ธุรกิจ",
        "CRM": "ผู้มุ่งหวัง",
        "Team Dashboard": "Team Dashboard",
        "Knowledge Hub": "คลังความรู้",
        "Profile": "โปรไฟล์สมาชิก",
        "Logout": "ออกจากระบบ",
        "Login": "เข้าสู่ระบบ",
        "Sign Up": "สมัครสมาชิก",
        "Submit": "ส่งข้อมูล",
        "Save": "บันทึก",
        "Cancel": "ยกเลิก",
        "Ask AI": "ถามคำถาม AI",
        "My Team": "ทีมของฉัน",
        "Prospects": "ผู้มุ่งหวัง",
        "30-Day Plan": "แผนปฏิบัติการ 30 วัน",
        "Home": "หน้าแรก",
        "Payment": "ชำระเงิน / เปิดใช้งาน",
        "Team Management": "จัดการทีม",
        "User Management": "จัดการผู้ใช้",
        "Content Creator": "เครื่องมือสร้างคอนเทนต์",
        "Account Settings": "ตั้งค่าบัญชี",
        "Main Menu": "เมนูหลัก",
        "Account Menu": "เมนูบัญชี",
    },
    "my": {
        "language_selector": "ဘာသာစကား / Language",
        "Dashboard": "ဒက်ရှ်ဘုတ်",
        "AI Coach": "AI ကို မေးရန်",
        "Workplan": "လုပ်ငန်းအစီအစဉ်",
        "CRM": "အလားအလာရှိသူများ",
        "Team Dashboard": "အသင်း ဒက်ရှ်ဘုတ်",
        "Knowledge Hub": "အသိပညာစင်တာ",
        "Profile": "အသင်းဝင် ပရိုဖိုင်",
        "Logout": "ထွက်ရန်",
        "Login": "ဝင်ရောက်ရန်",
        "Sign Up": "စာရင်းသွင်းရန်",
        "Submit": "ပေးပို့ရန်",
        "Save": "သိမ်းရန်",
        "Cancel": "မလုပ်တော့ပါ",
        "Ask AI": "AI ကို မေးရန်",
        "My Team": "ကျွန်ုပ်၏ အသင်း",
        "Prospects": "အလားအလာရှိသူများ",
        "30-Day Plan": "ရက် ၃၀ အစီအစဉ်",
        "Home": "ပင်မစာမျက်နှာ",
        "Payment": "ငွေပေးချေ / အသုံးပြုခွင့်ဖွင့်ရန်",
        "Team Management": "အသင်းစီမံခန့်ခွဲမှု",
        "User Management": "အသုံးပြုသူ စီမံခန့်ခွဲမှု",
        "Content Creator": "အကြောင်းအရာ ဖန်တီးရေး",
        "Account Settings": "အကောင့် ဆက်တင်များ",
        "Main Menu": "မီနူး",
        "Account Menu": "အကောင့် မီနူး",
    },
    "en": {
        "language_selector": "Language",
        "Dashboard": "Member Dashboard",
        "AI Coach": "Ask AI",
        "Workplan": "Business Workplan",
        "CRM": "Prospects",
        "Team Dashboard": "Team Dashboard",
        "Knowledge Hub": "Knowledge Hub",
        "Profile": "Member Profile",
        "Logout": "Logout",
        "Login": "Login",
        "Sign Up": "Sign Up",
        "Submit": "Submit",
        "Save": "Save",
        "Cancel": "Cancel",
        "Ask AI": "Ask AI",
        "My Team": "My Team",
        "Prospects": "Prospects",
        "30-Day Plan": "30-Day Plan",
        "Home": "Home",
        "Payment": "Payment / Activate Account",
        "Team Management": "Team Management",
        "User Management": "User Management",
        "Content Creator": "Content Creator",
        "Account Settings": "Account Settings",
        "Main Menu": "Main Menu",
        "Account Menu": "Account Menu",
    },
}

NAV_TRANSLATION_KEYS: dict[str, str] = {
    "หน้าแรก": "Home",
    "โปรไฟล์สมาชิก": "Profile",
    "ชำระเงิน / เปิดใช้งาน": "Payment",
    "จัดการทีม": "Team Management",
    "จัดการผู้ใช้": "User Management",
    "Team Dashboard": "Team Dashboard",
    "Dashboard สมาชิก": "Dashboard",
    "แผนปฏิบัติการ 30 วัน": "30-Day Plan",
    "เครื่องมือสร้างคอนเทนต์": "Content Creator",
    "ผู้มุ่งหวัง": "CRM",
    "Workplan ธุรกิจ": "Workplan",
    "คลังความรู้": "Knowledge Hub",
    "ถามคำถาม AI": "AI Coach",
    "ตั้งค่าบัญชี": "Account Settings",
    "ออกจากระบบ": "Logout",
}


def normalize_language(language: str | None) -> str:
    key = str(language or DEFAULT_LANGUAGE).strip().lower()
    return key if key in TRANSLATIONS else DEFAULT_LANGUAGE


def translate(key: str, language: str | None = None) -> str:
    language_key = normalize_language(language)
    return TRANSLATIONS.get(language_key, TRANSLATIONS[DEFAULT_LANGUAGE]).get(
        key,
        TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key),
    )


def translate_nav(item: str, language: str | None = None) -> str:
    return translate(NAV_TRANSLATION_KEYS.get(item, item), language)

