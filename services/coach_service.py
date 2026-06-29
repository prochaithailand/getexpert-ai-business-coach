from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Protocol

from models import ActionItem, CoachAnswer, KnowledgeMatch, MemberProfile
from services.knowledge_service import KnowledgeService
from services.member_activity_service import MemberActivityContext, is_workplan_question, no_workplan_message


class CoachService(Protocol):
    """Contract for local generation now and an OpenAI adapter later."""

    def generate_action_plan(self, profile: MemberProfile) -> list[ActionItem]: ...

    def generate_content(
        self,
        channel: str,
        profile: MemberProfile,
        goal: str = "สร้างการรับรู้",
        topic: str = "การเริ่มต้นธุรกิจเครือข่าย",
    ) -> str: ...

    def reply(self, message: str, profile: MemberProfile | None) -> str: ...

    def answer_question(
        self,
        message: str,
        profile: MemberProfile | None,
        history: Sequence[dict[str, Any]] = (),
        activity_context: MemberActivityContext | None = None,
    ) -> CoachAnswer: ...

    def generate_dashboard_insight(self, profile: MemberProfile, context: str) -> str: ...

    def generate_team_insight(self, context: str) -> str: ...

    def answer_team_question(
        self,
        question: str,
        context: str,
        history: Sequence[dict[str, Any]] = (),
    ) -> str: ...


class LocalCoachService:
    PHASES = {
        range(1, 8): "วางรากฐาน",
        range(8, 15): "สร้างการมองเห็น",
        range(15, 22): "เริ่มต้นบทสนทนา",
        range(22, 29): "นำเสนอและติดตามผล",
        range(29, 31): "ทบทวนและต่อยอด",
    }

    def __init__(self, knowledge_service: KnowledgeService | None = None) -> None:
        self.knowledge_service = knowledge_service

    def generate_action_plan(self, profile: MemberProfile) -> list[ActionItem]:
        minutes = max(15, round(profile.daily_available_time * 60))
        goal_factor = max(1, min(10, round(profile.income_goal / 10000)))
        outreach_target = max(2, min(20, round(profile.daily_available_time * 3) + goal_factor))
        advanced = "เชี่ยวชาญ" in profile.online_marketing_experience or "กลาง" in profile.online_marketing_experience
        content_days = (
            {3, 5, 8, 10, 12, 15, 17, 19, 22, 24, 26, 29}
            if not advanced
            else {2, 4, 6, 8, 10, 12, 15, 17, 19, 21, 23, 25, 27, 29}
        )
        presentation_days = {14, 18, 21, 23, 25, 27, 28, 30} if not advanced else {7, 11, 14, 18, 22, 24, 26, 28, 30}
        plan: list[ActionItem] = []

        for day in range(1, 31):
            phase = next(label for days, label in self.PHASES.items() if day in days)
            tasks = self._daily_tasks(day, minutes, outreach_target, content_days, presentation_days)
            metric = self._metric(day, outreach_target, content_days, presentation_days)
            if day == 1:
                tasks[0] = f"คุณ{profile.name}: กำหนดเป้าหมายรายได้ {profile.income_goal:,.0f} บาทต่อเดือน"
                tasks[1] = f"วางตารางลงมือทำวันละ {minutes} นาทีให้เหมาะกับงาน{profile.occupation}"
            elif day == 2:
                tasks[1] = f"กำหนดกลุ่มลูกค้าที่เชื่อมโยงกับประสบการณ์อาชีพ{profile.occupation}"
            elif day == 3:
                tasks[0] = f"ทบทวนจุดแข็งและเครือข่ายที่สะสมมาในวัย {profile.age} ปี"
            elif advanced and day in content_days:
                tasks[0] = "ทดสอบคอนเทนต์หลายรูปแบบและวัดผลเพื่อขยายสิ่งที่ได้ผล"
            elif not advanced and day in content_days:
                tasks[0] = "ฝึกสร้างคอนเทนต์พื้นฐานทีละรูปแบบเพื่อสร้างความมั่นใจ"
            if day not in {1, 2, 3}:
                tasks.append(f"จัดสรรเวลาไม่เกิน {minutes} นาทีตามตารางของคุณ")
            plan.append(ActionItem(day, phase, tasks[0], tuple(tasks[1:]), metric))
        return plan

    def generate_content(
        self,
        channel: str,
        profile: MemberProfile,
        goal: str = "สร้างการรับรู้",
        topic: str = "การเริ่มต้นธุรกิจเครือข่าย",
    ) -> str:
        name = profile.name or "ชื่อของคุณ"
        occupation = profile.occupation or "ผู้ประกอบอาชีพที่มีเวลาจำกัด"
        experience_tone = (
            "แบ่งปันจากประสบการณ์จริงและชวนผู้สนใจแลกเปลี่ยนมุมมอง"
            if "เชี่ยวชาญ" in profile.online_marketing_experience or "กลาง" in profile.online_marketing_experience
            else "เล่าการเรียนรู้แบบเป็นขั้นตอนด้วยภาษาที่จริงใจและเข้าถึงง่าย"
        )
        knowledge_note = self._content_knowledge_note(channel, goal, topic)
        if channel == "โพสต์ Facebook":
            return (
                f"**{topic}: ก้าวเล็ก ๆ ที่เริ่มได้วันนี้**\n\n"
                f"ผมชื่อ{name} ทำงานด้าน{occupation} และมีเวลาพัฒนาธุรกิจวันละประมาณ "
                f"{profile.daily_available_time:g} ชั่วโมง จึงเลือกเรียนรู้และลงมือทำอย่างมีระบบ\n\n"
                f"เป้าหมายของโพสต์นี้คือ “{goal}” โดยจะ{experience_tone}\n\n"
                "ไม่มีคำสัญญาเกินจริง มีเพียงการพัฒนาทักษะ การสร้างคุณค่า และการติดตามผลอย่างสม่ำเสมอ\n\n"
                f"หากสนใจเรื่อง {topic} ส่งข้อความมาพูดคุยกันได้ครับ\n\n"
                f"{knowledge_note}\n- {name}\n#ธุรกิจเครือข่าย #พัฒนาตนเอง #การตลาดออนไลน์"
            )
        if channel == "สคริปต์ TikTok":
            return (
                "[เปิดเรื่อง 0:00-0:03]\n"
                f"คนทำงานด้าน{occupation} จะเริ่มเรื่อง {topic} โดยมีเวลาวันละ {profile.daily_available_time:g} ชั่วโมงได้อย่างไร?\n\n"
                "[เนื้อหา 0:04-0:18]\n"
                f"ผมชื่อ{name} วันนี้ขอแชร์แนวทางเพื่อ{goal}: "
                f"{experience_tone} เริ่มจากหนึ่งเนื้อหาที่มีประโยชน์และหนึ่งบทสนทนาที่จริงใจ\n\n"
                "[เชิญชวน 0:19-0:25]\n"
                f"อยากได้แนวทางเรื่อง {topic} เพิ่มเติม พิมพ์คำว่า “สนใจ” ใต้คลิปได้เลยครับ\n\n"
                f"ข้อความบนหน้าจอ: {goal} | {topic}\n{knowledge_note}"
            )
        return (
            f"สวัสดีครับ จาก{name} ({occupation})\n\n"
            f"วันนี้ขอแบ่งปันเรื่อง “{topic}” เพื่อ{goal} เหมาะสำหรับผู้ที่มีเวลาพัฒนาธุรกิจวันละประมาณ "
            f"{profile.daily_available_time:g} ชั่วโมง\n\n"
            f"แนวทางของผมคือ{experience_tone} โดยเน้นข้อมูลที่เป็นประโยชน์และไม่กล่าวอ้างเกินจริง\n\n"
            f"สนใจรับรายละเอียดเรื่อง {topic} ตอบกลับคำว่า “สนใจ” ได้เลยครับ\n\n"
            f"{knowledge_note}\nด้วยความปรารถนาดี\n{name}"
        )

    def _content_knowledge_note(self, channel: str, goal: str, topic: str) -> str:
        if not self.knowledge_service:
            return "แนวทาง: ใช้ข้อมูลที่ตรวจสอบได้และปฏิบัติตามข้อกำหนดของบริษัท"
        matches = self.knowledge_service.search_text(f"{channel} {goal} {topic}", limit=1)
        if not matches:
            return "แนวทาง: ใช้ข้อมูลที่ตรวจสอบได้และปฏิบัติตามข้อกำหนดของบริษัท"
        return f"แนวทางจากคลังความรู้: {matches[0].document_name}"

    def reply(self, message: str, profile: MemberProfile | None) -> str:
        return self.answer_question(message, profile).answer

    def generate_dashboard_insight(self, profile: MemberProfile, context: str) -> str:
        return (
            "**จุดแข็งของสมาชิก**\n"
            "- มีการบันทึก Workplan ทำให้เห็นเป้าหมายและผลงานจริงอย่างเป็นระบบ\n"
            "- สามารถใช้คะแนน PP และสัดส่วนความสำเร็จเพื่อติดตามวินัยได้ชัดเจน\n\n"
            "**จุดที่ควรปรับปรุง**\n"
            "- เพิ่มจำนวนรายชื่อคุณภาพและติดตามผลรายชื่อ A/B อย่างสม่ำเสมอ\n"
            "- ทบทวนเป้าหมายที่ผลงานจริงยังต่ำกว่าแผน แล้วปรับกิจกรรมรายวันให้เหมาะกับเวลาที่มี\n\n"
            "**สิ่งที่ควรทำต่อใน 7 วันข้างหน้า**\n"
            "- ทำภารกิจแผน 30 วันต่อเนื่องทุกวันและบันทึกผลทันที\n"
            "- เริ่มบทสนทนาใหม่อย่างน้อยวันละ 2 ราย พร้อมกำหนดวันติดตามผล\n"
            "- สรุปผลสปอนเซอร์ คะแนนทีม และรายได้เมื่อครบ 7 วัน แล้วปรับแผนสัปดาห์ถัดไป"
        )

    def generate_team_insight(self, context: str) -> str:
        return rule_based_team_insight(context)

    def answer_team_question(
        self,
        question: str,
        context: str,
        history: Sequence[dict[str, Any]] = (),
    ) -> str:
        return (
            "**คำตอบจากโค้ช AI สำหรับทีม**\n"
            "- ใช้คะแนน PP ความคืบหน้า Workplan และข้อมูลผู้มุ่งหวังเพื่อจัดลำดับงานของทีม\n"
            "- ให้ความสำคัญกับสมาชิกที่ความคืบหน้าต่ำ และผู้มุ่งหวังเกรด A/B ที่อยู่ในช่วงตัดสินใจ\n"
            "- บันทึกกิจกรรมหลังลงมือทำ เพื่อให้การวิเคราะห์รอบถัดไปแม่นยำขึ้น"
        )

    def answer_question(
        self,
        message: str,
        profile: MemberProfile | None,
        history: Sequence[dict[str, Any]] = (),
        activity_context: MemberActivityContext | None = None,
    ) -> CoachAnswer:
        if is_workplan_question(message):
            if not activity_context or not activity_context.has_data:
                return CoachAnswer(no_workplan_message(self._detect_language(message)))
            return self._workplan_answer(profile, activity_context)
        if self.knowledge_service is None:
            return self._not_found_answer()
        matches = self.knowledge_service.search_text(message, limit=4)
        if not matches:
            return self._not_found_answer()

        first_name = profile.name.split()[0] if profile and profile.name else "สมาชิก"
        useful_matches = [match for match in matches if len(self._clean_excerpt(match.text)) >= 50]
        if not useful_matches:
            return self._not_found_answer()

        points = [self._summary_point(match.text) for match in useful_matches[:3]]
        lines = [
            "**สรุปคำตอบ**",
            f"คุณ{first_name} คลังความรู้มีแนวทางที่เกี่ยวข้องกับคำถามนี้ โดยเน้นการวางแผนให้ชัดเจนและลงมือทำอย่างสม่ำเสมอ",
            "\n**ประเด็นสำคัญ**",
            *(f"- {point}" for point in points if point),
            "\n**แนวทางนำไปใช้**",
            "- เลือกหนึ่งแนวทางที่สอดคล้องกับเป้าหมายของคุณ",
            "- กำหนดกิจกรรมที่ทำได้ภายในเวลาที่มีในแต่ละวัน",
            "- บันทึกผลและทบทวนเพื่อปรับแผนในรอบถัดไป",
        ]
        sources = tuple(dict.fromkeys(match.document_name for match in useful_matches))
        return CoachAnswer(self._append_source_section("\n".join(lines), sources), sources)

    @staticmethod
    def _detect_language(text: str) -> str:
        if re.search(r"[\u1000-\u109F]", text):
            return "my"
        if re.search(r"[A-Za-z]", text) and not re.search(r"[\u0E00-\u0E7F]", text):
            return "en"
        return "th"

    @staticmethod
    def _workplan_answer(
        profile: MemberProfile | None,
        activity_context: MemberActivityContext,
    ) -> CoachAnswer:
        first_name = profile.name.split()[0] if profile and profile.name else "สมาชิก"
        return CoachAnswer(
            "**สรุปคำตอบ**\n"
            f"คุณ{first_name} ระบบพบข้อมูล Workplan และความคืบหน้าแผน 30 วันของคุณแล้ว\n\n"
            "**ประเด็นสำคัญ**\n"
            f"{activity_context.summary}\n\n"
            "**แนวทางนำไปใช้**\n"
            "- เริ่มติดตามตามลำดับแนะนำในข้อมูล CRM โดยให้ความสำคัญกับรายชื่อเกรด A/B ที่ครบกำหนดก่อน\n"
            "- เปรียบเทียบผลงานจริงกับเป้าหมายประจำสัปดาห์ แล้วกำหนดกิจกรรมชดเชยที่ทำได้จริง\n"
            "- ทำภารกิจในแผน 30 วันต่อเนื่องเพื่อเพิ่มคะแนน PP และรักษาวินัย"
        )

    @staticmethod
    def _clean_excerpt(text: str, limit: int = 420) -> str:
        cleaned = " ".join(text.replace("�", "").split()).strip(" -|•")
        if len(cleaned) <= limit:
            return cleaned
        shortened = cleaned[:limit].rsplit(" ", 1)[0]
        return f"{shortened}..."

    @classmethod
    def _summary_point(cls, text: str, limit: int = 220) -> str:
        cleaned = cls._clean_excerpt(text, limit=limit)
        cleaned = re.sub(r"^(?:คู่มือ|สารบัญ|จัดทำโดย|ผู้จัดทำ)\s*[:：-]?\s*", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" -|•")

    @staticmethod
    def _append_source_section(answer: str, sources: Sequence[str]) -> str:
        if sources:
            source_lines = "\n".join(f"- {source}" for source in dict.fromkeys(sources))
        else:
            source_lines = "- ไม่พบเอกสารในคลังความรู้ที่เกี่ยวข้องเพียงพอ"
        return f"{answer.rstrip()}\n\n---\n**แหล่งข้อมูลอ้างอิง**\n{source_lines}"

    @staticmethod
    def _not_found_answer() -> CoachAnswer:
        message = (
            "ฐานความรู้ยังไม่มีข้อมูลเพียงพอสำหรับตอบคำถามนี้ กรุณาลองระบุหัวข้อให้ชัดขึ้น เช่น "
            "5 โมดูล, แผนงาน MLM, LINE OA, TikTok, Canva, Blogger, Facebook Page, Google Form "
            "หรือการเล่าเรื่องผลิตภัณฑ์สุขภาพ"
        )
        return CoachAnswer(LocalCoachService._append_source_section(message, ()))

    @staticmethod
    def _daily_tasks(
        day: int,
        minutes: int,
        outreach_target: int,
        content_days: set[int],
        presentation_days: set[int],
    ) -> list[str]:
        if day == 1:
            return ["กำหนดเป้าหมายที่ต้องการ", "เขียนเป้าหมายรายได้และเหตุผลส่วนตัว", "กำหนดช่วงเวลาลงมือทำประจำวัน"]
        if day == 2:
            return ["กำหนดกลุ่มเป้าหมายให้ชัดเจน", "อธิบายลักษณะลูกค้าเป้าหมายหนึ่งกลุ่ม", "ระบุปัญหา 3 เรื่องที่คุณช่วยแก้ไขได้"]
        if day == 30:
            return ["สรุปผลการทำงานครบ 30 วัน", "เปรียบเทียบกิจกรรมกับผลลัพธ์", "กำหนดเป้าหมายสำหรับ 30 วันถัดไป"]
        if day in content_days:
            return ["สร้างความไว้วางใจผ่านคอนเทนต์", "เผยแพร่เรื่องราวหรือเคล็ดลับที่มีประโยชน์ 1 ชิ้น", f"สร้างปฏิสัมพันธ์อย่างมีคุณภาพ {max(10, minutes // 4)} นาที"]
        if day in presentation_days:
            return ["พัฒนาบทสนทนาไปสู่ขั้นต่อไป", f"ติดตามผู้สนใจ {outreach_target} ราย", "นำเสนอภาพรวมผลิตภัณฑ์หรือโอกาสทางธุรกิจแบบกระชับ"]
        if day in {7, 13, 20, 29}:
            return ["ทบทวนและพัฒนา", "บันทึกผลสำเร็จและบทเรียน", "ปรับเป้าหมายกิจกรรมสำหรับสัปดาห์ถัดไป"]
        return ["ขยายฐานความสัมพันธ์", f"เริ่มบทสนทนาอย่างจริงใจกับผู้สนใจ {outreach_target} ราย", "อัปเดตบันทึกและกำหนดวันติดตามผล"]

    @staticmethod
    def _metric(day: int, outreach_target: int, content_days: set[int], presentation_days: set[int]) -> str:
        if day == 30:
            return "จัดทำสรุปผล 30 วันและเป้าหมายรอบถัดไปเรียบร้อย"
        if day in content_days:
            return "เผยแพร่คอนเทนต์ 1 ชิ้น และสร้างปฏิสัมพันธ์ที่มีคุณภาพ 3 ครั้ง"
        if day in presentation_days:
            return f"ติดตามผล {outreach_target} ราย และเชิญรับฟังข้อมูล 1 ราย"
        if day in {1, 2, 7, 13, 20, 29, 30}:
            return "บันทึกผลลัพธ์เป็นลายลักษณ์อักษรเรียบร้อย"
        return f"บันทึกบทสนทนาใหม่ {outreach_target} ราย"


def rule_based_team_insight(context: str) -> str:
    return (
        "**สมาชิกที่ทำผลงานดีที่สุด**\n"
        "- พิจารณาสมาชิกอันดับต้นจากคะแนน PP จำนวนผู้มุ่งหวัง และความต่อเนื่องของแผน 30 วัน\n\n"
        "**สมาชิกที่ต้องการความช่วยเหลือ**\n"
        "- โค้ชสมาชิกที่ความคืบหน้ายังต่ำด้วยเป้าหมายรายวันขนาดเล็กและติดตามผลอย่างใกล้ชิด\n\n"
        "**ความคืบหน้าของทีม**\n"
            "- ใช้ค่าเฉลี่ยแผน 30 วันและจำนวนสมาชิกที่ใช้งานอยู่เพื่อติดตามวินัยของทีมอย่างสม่ำเสมอ\n\n"
        "**งานที่ควรโฟกัสในสัปดาห์นี้**\n"
        "- เพิ่มรายชื่อเกรด A/B กำหนดวันติดตาม และทบทวน PP ของสมาชิกทุกคนเมื่อจบสัปดาห์"
    )
