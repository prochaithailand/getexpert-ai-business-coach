from __future__ import annotations

import hashlib
from dataclasses import dataclass

from models import MemberProfile


@dataclass(frozen=True)
class PlanProgressSummary:
    total_days: int
    completed_days: int
    remaining_days: int
    percentage: float
    pp_score: int
    status_level: str


def member_progress_key(profile: MemberProfile) -> str:
    identity = f"{profile.name.strip().casefold()}|{profile.age}|{profile.occupation.strip().casefold()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def calculate_plan_progress(statuses: dict[str, bool], total_days: int = 30) -> PlanProgressSummary:
    completed = sum(1 for day in range(1, total_days + 1) if statuses.get(str(day), False))
    percentage = (completed / total_days * 100) if total_days else 0.0
    if percentage <= 25:
        level = "เริ่มต้น"
    elif percentage <= 50:
        level = "กำลังสร้างวินัย"
    elif percentage <= 75:
        level = "นักปฏิบัติ"
    else:
        level = "ผู้สร้างผลลัพธ์"
    return PlanProgressSummary(
        total_days=total_days,
        completed_days=completed,
        remaining_days=total_days - completed,
        percentage=percentage,
        pp_score=completed * 10,
        status_level=level,
    )
