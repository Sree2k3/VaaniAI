from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AppointmentStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class CallOutcome(str, Enum):
    booked = "booked"
    fallback = "fallback"
    error = "error"
    active = "active"


class Speaker(str, Enum):
    user = "user"
    assistant = "assistant"


class ConversationState(str, Enum):
    idle = "idle"
    collect_specialization = "collect_specialization"
    show_slots = "show_slots"
    collect_name = "collect_name"
    confirm_name = "confirm_name"
    collect_gender = "collect_gender"
    collect_age = "collect_age"
    collect_phone = "collect_phone"
    review_booking = "review_booking"
    confirm_booking = "confirm_booking"
    booked = "booked"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = None
    phone: str = Field(index=True)
    gender: Optional[str] = None
    age: Optional[int] = None
    language_preference: str = "en"
    preferred_doctor_id: Optional[int] = Field(default=None, foreign_key="doctor.id")
    last_appointment_id: Optional[int] = Field(default=None, foreign_key="appointment.id")
    created_at: datetime = Field(default_factory=utc_now)


class Doctor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    specialization: str = Field(index=True)
    symptoms: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    languages: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


class Slot(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("doctor_id", "start_time", name="uq_doctor_slot_time"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    start_time: datetime = Field(index=True)
    end_time: datetime
    is_booked: bool = False


class Appointment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    doctor_id: int = Field(foreign_key="doctor.id", index=True)
    slot_id: int = Field(foreign_key="slot.id", unique=True)
    status: AppointmentStatus = AppointmentStatus.confirmed
    calendar_event_id: Optional[str] = None
    calendar_status: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class CallLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    call_sid: str = Field(index=True, unique=True)
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: Optional[datetime] = None
    language_detected: Optional[str] = None
    outcome: CallOutcome = CallOutcome.active
    current_state: ConversationState = Field(
        default=ConversationState.idle,
        sa_column=Column(String(64), nullable=False, default=ConversationState.idle.value),
    )
    selected_specialization: Optional[str] = None
    selected_doctor_id: Optional[int] = Field(default=None, foreign_key="doctor.id")
    selected_slot_id: Optional[int] = Field(default=None, foreign_key="slot.id")
    patient_name: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_age: Optional[int] = None
    patient_phone: Optional[str] = None


class Transcript(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    call_id: int = Field(foreign_key="calllog.id", index=True)
    speaker: Speaker
    text: str
    language: str = "en"
    timestamp: datetime = Field(default_factory=utc_now)


class NotificationLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointment.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    channel: str = "sms"
    recipient: str
    message: str
    status: str
    provider_message_id: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
