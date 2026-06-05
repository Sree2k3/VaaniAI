from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.models import ConversationState


class HealthResponse(BaseModel):
    status: str
    database: str


class ChatRequest(BaseModel):
    call_id: str
    user_phone: str = "demo"
    message: str
    language: str = "en"


class SessionStartRequest(BaseModel):
    call_id: str
    user_phone: str
    language: str = "en"
    fresh: bool = False


class SessionStateResponse(BaseModel):
    call_id: str
    user_phone: str
    language: str
    state: ConversationState
    selected_specialization: Optional[str] = None
    selected_doctor_id: Optional[int] = None
    selected_slot_id: Optional[int] = None
    patient_name: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_age: Optional[int] = None
    patient_phone: Optional[str] = None
    booking_review: Optional["BookingReview"] = None
    slot_options: Optional[list["SlotOption"]] = None
    selected_slot: Optional["SlotOption"] = None
    last_assistant_reply: Optional[str] = None


class SlotOption(BaseModel):
    slot_id: int
    availability_id: int
    doctor_name: str
    specialization: str
    available_date: date
    start_time: datetime
    end_time: datetime
    max_patients: int
    booked_count: int
    remaining_slots: int
    fully_booked: bool
    label: str


class BookingReview(BaseModel):
    name: str
    gender: str
    age: int
    phone: str
    doctor_name: str
    specialization: str
    slot_time: str
    token_number: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    next_state: ConversationState
    intent: str
    action: Optional[str] = None
    appointment_id: Optional[int] = None
    notification_status: Optional[str] = None
    booking_review: Optional[BookingReview] = None
    slot_options: Optional[list[SlotOption]] = None
    selected_slot: Optional[SlotOption] = None


class BookingRequest(BaseModel):
    user_id: int
    doctor_id: int
    slot_id: int


class BookingResponse(BaseModel):
    appointment_id: int
    status: str
    notification_status: Optional[str] = None
    token_number: Optional[int] = None


class SmsTestRequest(BaseModel):
    phone: str
    message: str = "VaaniAI SMS test from Pawani Medicals."


class SmsTestResponse(BaseModel):
    status: str
    provider_message_id: Optional[str] = None
    detail: str = ""


class SlotRead(BaseModel):
    id: int
    availability_id: int
    doctor_id: int
    doctor_name: str
    specialization: str
    available_date: date
    start_time: datetime
    end_time: datetime
    max_patients: int
    booked_count: int
    remaining_slots: int
    fully_booked: bool


class DoctorRead(BaseModel):
    id: int
    name: str
    specialization: str
    symptoms: list[str]
    languages: list[str]


class DashboardMetrics(BaseModel):
    total_calls_today: int
    total_bookings_today: int
    booking_conversion_percent: float
    top_language: Optional[str] = None
    language_distribution: dict[str, int]
    doctor_demand: dict[str, int]


class RecentBooking(BaseModel):
    appointment_id: int
    created_at: datetime
    patient_name: Optional[str] = None
    doctor_name: str
    specialization: str
    slot_start: datetime
    status: str


class TranscriptTurn(BaseModel):
    speaker: str
    text: str
    language: str
    timestamp: datetime


class TranscriptRead(BaseModel):
    call_id: int
    call_sid: str
    started_at: datetime
    language_detected: Optional[str] = None
    outcome: str
    turns: list[TranscriptTurn]


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


class TTSResponse(BaseModel):
    audio_url: Optional[str] = None
    status: str
    detail: str


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    call_id: str
    status: str
    detail: str = ""
    chat: Optional[ChatResponse] = None


class VoiceTurnResponse(BaseModel):
    call_id: str
    user_phone: str
    language: str
    stt_text: str
    stt_status: str
    stt_detail: str = ""
    chat: Optional[ChatResponse] = None
    tts: Optional[TTSResponse] = None


class NotificationRead(BaseModel):
    id: int
    appointment_id: int
    user_id: int
    channel: str
    recipient: str
    message: str
    status: str
    provider_message_id: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime


SessionStateResponse.model_rebuild()
