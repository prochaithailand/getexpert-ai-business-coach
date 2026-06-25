from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from services.workplan_service import CONTACT_STATUSES, CONTACT_TYPES


@dataclass(frozen=True)
class ProspectDraft:
    name: str = ""
    age: int = 0
    occupation: str = ""
    phone: str = ""
    line_id: str = ""
    province: str = ""
    area: str = ""
    income: float = 0.0
    status: str = ""
    category: str = ""
    interest: str = ""
    pain_point: str = ""
    previous_experience: str = ""
    next_follow_up: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuleBasedProspectParser:
    """Extract explicit prospect details without inventing missing information."""

    def parse(self, text: str, today: date | None = None) -> ProspectDraft:
        source = " ".join(str(text or "").split())
        if not source:
            return ProspectDraft()

        name = _extract(source, r"(?:ชื่อ|คุณ)\s*([ก-๙A-Za-z][^,.;\n]*?)(?=\s+(?:อายุ|เป็น|อาชีพ|เบอร์|โทร|LINE|ไลน์|อยู่|จังหวัด|สนใจ|ต้องการ|นัด|เกรด|สถานะ)|[,.;]|$)")
        age_text = _extract(source, r"อายุ\s*(\d{1,3})\s*(?:ปี)?")
        age = int(age_text) if age_text and 0 < int(age_text) <= 120 else 0
        phone_text = _extract(
            source, r"(?:เบอร์(?:โทร)?|โทร(?:ศัพท์)?)\s*[:\-]?\s*(0[\d\-\s]{8,12})"
        )
        phone = _normalize_phone(phone_text)
        line_id = _extract(
            source,
            r"(?:LINE\s*ID|ไลน์(?:ไอดี)?|ไลน์\s*ID)\s*[:\-]?\s*([A-Za-z0-9_.@\-]+)",
            flags=re.IGNORECASE,
        )
        occupation = _extract(
            source,
            r"(?:อาชีพ\s*[:\-]?\s*|เป็น\s*)([^,.;]*?)(?=\s+(?:อยู่|จังหวัด|เบอร์|โทร|LINE|ไลน์|สนใจ|ต้องการ|นัด|เกรด|สถานะ)|[,.;]|$)",
        )
        province = _extract(
            source,
            r"จังหวัด\s*[:\-]?\s*([ก-๙A-Za-z ]+?)(?=\s+(?:อยู่|พื้นที่|สนใจ|ต้องการ|นัด|เบอร์|โทร|LINE|ไลน์|เกรด|สถานะ)|[,.;]|$)",
        )
        area = _extract(
            source,
            r"(?:อยู่|พื้นที่)\s*[:\-]?\s*([ก-๙A-Za-z ]+?)(?=\s+(?:จังหวัด|สนใจ|ต้องการ|นัด|เบอร์|โทร|LINE|ไลน์|เกรด|สถานะ)|[,.;]|$)",
        )
        income_text = _extract(
            source,
            r"(?:รายได้(?:ต่อเดือน)?|เงินเดือน)\s*[:\-]?\s*([\d,]+)",
        )
        income = float(income_text.replace(",", "")) if income_text else 0.0
        interest = _extract(
            source,
            r"สนใจ\s*([^,.;]*?)(?=\s+(?:เพราะ|แต่|ปัญหา|ต้องการ|ประสบการณ์|เคย|นัด|เกรด|สถานะ)|[,.;]|$)",
        )
        pain_point = _extract(
            source,
            r"(?:ปัญหา|ต้องการ)\s*[:\-]?\s*([^,.;]*?)(?=\s+(?:ประสบการณ์|เคย|นัด|เกรด|สถานะ)|[,.;]|$)",
        )
        previous_experience = _extract(
            source,
            r"(?:ประสบการณ์(?:เดิม)?|เคย)\s*[:\-]?\s*([^,.;]*?)(?=\s+(?:นัด|เกรด|สถานะ)|[,.;]|$)",
        )
        category_text = _extract(source, r"(?:เกรด|ประเภท)\s*[:\-]?\s*([ABCD])\b", flags=re.IGNORECASE)
        category = category_text.upper() if category_text.upper() in CONTACT_TYPES else ""
        status = _extract_status(source)
        next_follow_up = _extract_follow_up(source, today or date.today())
        notes = _extract(source, r"หมายเหตุ\s*[:\-]?\s*(.+)$")
        uncertain: list[str] = []
        if age_text and not age:
            uncertain.append(f"อายุที่ระบุ: {age_text}")
        if phone_text and not phone:
            uncertain.append(f"เบอร์โทรที่ควรตรวจสอบ: {phone_text}")
        if uncertain:
            notes = "; ".join(filter(None, (notes, *uncertain)))

        return ProspectDraft(
            name=name,
            age=age,
            occupation=occupation,
            phone=phone,
            line_id=line_id,
            province=province,
            area=area,
            income=income,
            status=status,
            category=category,
            interest=interest,
            pain_point=pain_point,
            previous_experience=previous_experience,
            next_follow_up=next_follow_up,
            notes=notes,
        )


def parse_prospect_text(text: str, today: date | None = None) -> ProspectDraft:
    return RuleBasedProspectParser().parse(text, today=today)


def _extract(text: str, pattern: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1).strip(" :-") if match else ""


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits if 9 <= len(digits) <= 10 and digits.startswith("0") else ""


def _extract_status(text: str) -> str:
    aliases = {
        "ยังไม่ติดต่อ": "ยังไม่ติดต่อ",
        "ติดต่อแล้ว": "ติดต่อแล้ว",
        "ส่งข้อมูลแล้ว": "ส่งข้อมูลแล้ว",
        "นัดหมายแล้ว": "นัดหมายแล้ว",
        "นัดคุย": "นัดหมายแล้ว",
        "นำเสนอแล้ว": "นำเสนอแล้ว",
        "กำลังตัดสินใจ": "กำลังตัดสินใจ",
        "สมัครแล้ว": "สมัครแล้ว",
        "ไม่สนใจ": "ไม่สนใจ",
    }
    for phrase, status in aliases.items():
        if phrase in text and status in CONTACT_STATUSES:
            return status
    return ""


def _extract_follow_up(text: str, today: date) -> str:
    iso_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if iso_match:
        try:
            return date(*(int(value) for value in iso_match.groups())).isoformat()
        except ValueError:
            return ""

    thai_match = re.search(r"(?:วันที่|นัด(?:คุย)?(?:วันที่)?)\s*(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", text)
    if thai_match:
        day, month, year_text = thai_match.groups()
        year = int(year_text) if year_text else today.year
        if year > 2400:
            year -= 543
        elif year < 100:
            year += 2000
        try:
            return date(year, int(month), int(day)).isoformat()
        except ValueError:
            return ""

    if "พรุ่งนี้" in text:
        return (today + timedelta(days=1)).isoformat()
    if "วันนี้" in text:
        return today.isoformat()

    weekdays = {
        "จันทร์": 0, "อังคาร": 1, "พุธ": 2, "พฤหัส": 3,
        "ศุกร์": 4, "เสาร์": 5, "อาทิตย์": 6,
    }
    for label, weekday in weekdays.items():
        if f"วัน{label}" in text:
            days = (weekday - today.weekday()) % 7
            if days == 0 or "หน้า" in text:
                days += 7
            return (today + timedelta(days=days)).isoformat()
    return ""
