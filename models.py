from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemberProfile:
    name: str = ""
    age: int = 25
    occupation: str = ""
    daily_available_time: float = 1.0
    income_goal: float = 30000.0
    online_marketing_experience: str = "ยังไม่มีประสบการณ์"
    team_name: str = ""
    team_id: str = ""
    team_leader: str = ""
    sponsor: str = ""
    role: str = "Member"
    invited_by: str = ""
    joined_at: str = ""
    referrer_user_id: str = ""
    referrer_role_at_signup: str = ""
    referral_rate_at_signup: float = 0.0
    referral_source: str = ""
    partner_status: str = ""
    partner_approved_by: str = ""
    partner_approved_at: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.name.strip() and self.occupation.strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemberProfile":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass(frozen=True)
class Team:
    name: str
    team_id: str
    leader: str
    primary_sponsor: str = ""
    notes: str = ""
    leader_email: str = ""
    invite_code: str = ""
    invite_owner_role: str = ""
    invite_referral_rate: float = 0.0
    invite_owner_user_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Team":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass(frozen=True)
class AppUser:
    email: str
    full_name: str
    role: str = "Member"
    password_hash: str = ""
    subscription_status: str = "active"
    subscription_plan: str = "Member"
    subscription_started_at: str = ""
    subscription_expires_at: str = ""
    last_payment_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    trial_started_at: str = ""
    trial_ends_at: str = ""
    trial_used: bool = False
    marketing_email_opt_in: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppUser":
        data = dict(data)
        aliases = {
            "membership_status": "subscription_status",
            "membership_plan": "subscription_plan",
            "membership_started_at": "subscription_started_at",
            "membership_expires_at": "subscription_expires_at",
        }
        for source, target in aliases.items():
            if source in data and not data.get(target):
                data[target] = data[source]
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def public_dict(self) -> dict[str, str]:
        return {
            key: value for key, value in self.to_dict().items()
            if key != "password_hash"
        }


@dataclass(frozen=True)
class ActionItem:
    day: int
    phase: str
    focus: str
    tasks: tuple[str, ...]
    success_metric: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionItem":
        return cls(
            day=int(data.get("day", 0)),
            phase=str(data.get("phase", "")),
            focus=str(data.get("focus", "")),
            tasks=tuple(str(task) for task in data.get("tasks", ())),
            success_metric=str(data.get("success_metric", "")),
        )


@dataclass(frozen=True)
class KnowledgeDocument:
    name: str
    category: str
    size_bytes: int
    path: Path

    @property
    def display_size(self) -> str:
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"


@dataclass(frozen=True)
class KnowledgeMatch:
    document_name: str
    category: str
    page_number: int
    text: str
    score: float


@dataclass(frozen=True)
class CoachAnswer:
    answer: str
    sources: tuple[str, ...] = ()
