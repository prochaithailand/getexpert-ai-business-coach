from __future__ import annotations

import os
import re
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

from models import MemberProfile


NAVY = "#0B2E59"
BLUE = "#1D4E89"
SILVER = "#D7DEE8"
LIGHT_GRAY = "#F5F7FA"
TEXT_DARK = "#1F2937"


def member_report_filename(member_name: str) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", member_name.strip())
    safe_name = re.sub(r"\s+", "_", safe_name).strip("._") or "Member"
    return f"Member_Report_{safe_name}.pdf"


def generate_member_report_pdf(
    profile: MemberProfile,
    snapshot: dict[str, Any],
    insight: str,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        CondPageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    regular_font, bold_font = _register_thai_fonts(pdfmetrics, TTFont)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"รายงานสมาชิก {profile.name}",
        author="GetExpert AI Business Coach",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ThaiTitle", parent=styles["Title"], fontName=bold_font, fontSize=20,
        leading=26, textColor=colors.HexColor(NAVY), alignment=TA_CENTER, spaceAfter=5 * mm,
        wordWrap="CJK",
    )
    subtitle_style = ParagraphStyle(
        "ThaiSubtitle", parent=styles["Normal"], fontName=regular_font, fontSize=9,
        leading=13, textColor=colors.HexColor(BLUE), alignment=TA_CENTER, spaceAfter=6 * mm,
        wordWrap="CJK",
    )
    body_style = ParagraphStyle(
        "ThaiBody", parent=styles["BodyText"], fontName=regular_font, fontSize=10,
        leading=16, textColor=colors.HexColor(TEXT_DARK), alignment=TA_LEFT, wordWrap="CJK",
    )
    label_style = ParagraphStyle(
        "ThaiLabel", parent=body_style, fontName=bold_font, textColor=colors.HexColor(NAVY),
    )
    section_style = ParagraphStyle(
        "ThaiSection", parent=body_style, fontName=bold_font, fontSize=12, leading=17,
        textColor=colors.white, leftIndent=2 * mm,
    )
    bullet_style = ParagraphStyle(
        "ThaiBullet", parent=body_style, leftIndent=5 * mm, firstLineIndent=-3 * mm,
        spaceAfter=1.5 * mm,
    )

    def paragraph(text: Any, style=body_style):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)

    def section(title: str):
        table = Table([[Paragraph(escape(title), section_style)]], colWidths=[178 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(NAVY)),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(NAVY)),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return [table, Spacer(1, 3 * mm)]

    def data_table(rows: Iterable[tuple[str, str]]):
        data = [[Paragraph(escape(label), label_style), paragraph(value)] for label, value in rows]
        table = Table(data, colWidths=[66 * mm, 112 * mm], repeatRows=0)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(LIGHT_GRAY)),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor(SILVER)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return [table, Spacer(1, 5 * mm)]

    plan = snapshot["plan"]
    contacts = snapshot["contacts"]
    goals = snapshot["goals"]
    story = [
        Paragraph("รายงานความสำเร็จสมาชิก", title_style),
        Paragraph("GetExpert AI Business Coach", subtitle_style),
    ]
    story += section("ส่วนที่ 1 ข้อมูลสมาชิก")
    story += data_table((
        ("ชื่อ", profile.name),
        ("อายุ", f"{profile.age} ปี"),
        ("อาชีพ", profile.occupation),
        ("เวลาว่างต่อวัน", f"{profile.daily_available_time:g} ชั่วโมง"),
        ("เป้าหมายรายได้", f"{profile.income_goal:,.0f} บาทต่อเดือน"),
        ("ชื่อทีม", profile.team_name or "ยังไม่ระบุ"),
        ("รหัสทีม", profile.team_id or "ยังไม่ระบุ"),
        ("หัวหน้าทีม", profile.team_leader or "ยังไม่ระบุ"),
        ("ผู้แนะนำ", profile.sponsor or "ยังไม่ระบุ"),
        ("บทบาทในทีม", profile.role),
    ))
    story += section("ส่วนที่ 2 ความคืบหน้า")
    story += data_table((
        ("แผนปฏิบัติการ 30 วัน", f"{plan['percentage']:.0f}% ({plan['completed']}/{plan['total']} วัน)"),
        ("คะแนน PP", f"{plan['pp_score']} PP"),
        ("ระดับสมาชิก", plan["status"]),
    ))
    story += section("ส่วนที่ 3 Workplan")
    story += data_table((
        ("จำนวนรายชื่อทั้งหมด", f"{contacts['total']} ราย"),
        ("จำนวน A", f"{contacts['A']} ราย"),
        ("จำนวน B", f"{contacts['B']} ราย"),
        ("จำนวน C", f"{contacts['C']} ราย"),
        ("จำนวน D", f"{contacts['D']} ราย"),
    ))
    story.append(CondPageBreak(80 * mm))
    story += section("ส่วนที่ 4 เป้าหมาย")
    story += data_table((
        ("เป้าหมายสปอนเซอร์", f"{goals['sponsor']['target']:,.0f} คน"),
        ("ผลลัพธ์จริง - สปอนเซอร์", f"{goals['sponsor']['actual']:,.0f} คน ({goals['sponsor']['percentage']:.0f}%)"),
        ("เป้าหมายคะแนนทีม", f"{goals['team_points']['target']:,.0f} คะแนน"),
        ("ผลลัพธ์จริง - คะแนนทีม", f"{goals['team_points']['actual']:,.0f} คะแนน ({goals['team_points']['percentage']:.0f}%)"),
        ("เป้าหมายรายได้", f"{goals['income']['target']:,.0f} บาท"),
        ("ผลลัพธ์จริง - รายได้", f"{goals['income']['actual']:,.0f} บาท ({goals['income']['percentage']:.0f}%)"),
    ))
    story += section("ส่วนที่ 5 AI Insight")
    insight_sections = _parse_insight(insight)
    for heading in ("จุดแข็งของสมาชิก", "จุดที่ควรปรับปรุง", "สิ่งที่ควรทำต่อใน 7 วันข้างหน้า"):
        story.append(Paragraph(escape(heading), label_style))
        for item in insight_sections.get(heading, ["ยังไม่มีข้อมูลในหัวข้อนี้"]):
            story.append(Paragraph(f"- {escape(item)}", bullet_style))
        story.append(Spacer(1, 2 * mm))

    def draw_page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(SILVER))
        canvas.line(16 * mm, 13 * mm, 194 * mm, 13 * mm)
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor(BLUE))
        canvas.drawString(16 * mm, 8 * mm, "GetExpert AI Business Coach")
        canvas.drawRightString(194 * mm, 8 * mm, f"หน้า {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()


def _register_thai_fonts(pdfmetrics, TTFont) -> tuple[str, str]:
    regular_name = "GetExpertThai"
    bold_name = "GetExpertThaiBold"
    if regular_name in pdfmetrics.getRegisteredFontNames():
        return regular_name, bold_name
    regular_path = _find_font(False)
    bold_path = _find_font(True) or regular_path
    pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
    return regular_name, bold_name


def _find_font(bold: bool) -> Path | None:
    custom = os.getenv("THAI_PDF_BOLD_FONT" if bold else "THAI_PDF_FONT")
    candidates = [
        custom,
        "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansThai-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    if bold:
        return None
    raise RuntimeError(
        "ไม่พบฟอนต์ภาษาไทยสำหรับสร้าง PDF กรุณากำหนด THAI_PDF_FONT และ THAI_PDF_BOLD_FONT"
    )


def _parse_insight(insight: str) -> dict[str, list[str]]:
    headings = ("จุดแข็งของสมาชิก", "จุดที่ควรปรับปรุง", "สิ่งที่ควรทำต่อใน 7 วันข้างหน้า")
    result = {heading: [] for heading in headings}
    current = headings[0]
    for raw_line in insight.splitlines():
        line = raw_line.replace("**", "").replace("###", "").strip()
        matched = next((heading for heading in headings if heading in line), None)
        if matched:
            current = matched
            continue
        item = line.lstrip("-• ").strip()
        if item:
            result[current].append(item)
    return result
