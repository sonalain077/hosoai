"""The user's personal details, entered once and reused to fill forms.

Personal data: never log it, never put real values in tests or fixtures, and only send
the LLM what a task needs (see agent_facts).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Field as DbField
from sqlmodel import SQLModel


class ProfileData(BaseModel):
    """What the API accepts and returns (validated)."""

    full_name: str | None = Field(default=None, max_length=120)
    date_of_birth: date | None = None
    sex: Literal["Nam", "Nữ"] | None = None
    id_number: str | None = Field(default=None, max_length=20)  # số định danh cá nhân / CCCD
    nationality: str | None = Field(default=None, max_length=60)
    ethnicity: str | None = Field(default=None, max_length=60)
    religion: str | None = Field(default=None, max_length=60)
    place_of_birth: str | None = Field(default=None, max_length=200)
    hometown: str | None = Field(default=None, max_length=200)  # quê quán
    permanent_address: str | None = Field(default=None, max_length=300)
    current_address: str | None = Field(default=None, max_length=300)
    occupation: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    passport_number: str | None = Field(default=None, max_length=20)


class Profile(SQLModel, table=True):
    """Storage row. Single local user, so id is always 1. Columns mirror ProfileData."""

    id: int = DbField(default=1, primary_key=True)
    full_name: str | None = None
    date_of_birth: date | None = None
    sex: str | None = None
    id_number: str | None = None
    nationality: str | None = None
    ethnicity: str | None = None
    religion: str | None = None
    place_of_birth: str | None = None
    hometown: str | None = None
    permanent_address: str | None = None
    current_address: str | None = None
    occupation: str | None = None
    phone: str | None = None
    email: str | None = None
    passport_number: str | None = None


def age_on(born: date, today: date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def agent_facts(p: ProfileData, today: date) -> str | None:
    """The only profile facts the agent sees: age and nationality. No names, no numbers."""
    facts = []
    if p.date_of_birth:
        facts.append(f"age {age_on(p.date_of_birth, today)}")
    if p.nationality:
        facts.append(f"nationality {p.nationality}")
    return ", ".join(facts) or None
