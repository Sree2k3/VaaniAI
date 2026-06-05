import re
import unicodedata
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, and_, select, text

from app.calendar import calendar_service
from app.config import get_settings
from app.intent import IntentResult, detect_intent
from app.llm import llm_service
from app.messaging import MessageResult, sms_service
from app.models import (
    Appointment,
    CallLog,
    CallOutcome,
    ConversationState,
    Doctor,
    NotificationLog,
    Slot,
    Speaker,
    Transcript,
    User,
)
from app.schemas import BookingReview, ChatResponse, SessionStateResponse, SlotOption, SlotRead


DOCTOR_SYMPTOMS = {
    "dermatologist": [
        "skin rash",
        "itching",
        "acne",
        "pimples",
        "allergy on skin",
        "eczema",
        "fungal infection",
        "hair fall",
        "dandruff",
        "dark spots",
        "twacha problem",
        "chamdi khujli",
        "skin infection",
    ],
    "general physician": [
        "fever",
        "cold",
        "cough",
        "body pain",
        "headache",
        "stomach pain",
        "vomiting",
        "loose motion",
        "weakness",
        "throat pain",
        "viral fever",
        "pet dard",
        "bukhar",
        "sardi",
    ],
    "dentist": [
        "tooth pain",
        "teeth pain",
        "cavity",
        "gum swelling",
        "bleeding gums",
        "root canal",
        "bad breath",
        "mouth ulcer",
        "daant dard",
        "masude dard",
    ],
    "cardiologist": [
        "chest pain",
        "chest tightness",
        "heart pain",
        "palpitations",
        "breathlessness",
        "high blood pressure",
        "low blood pressure",
        "dizziness with chest pain",
        "seene mein dard",
        "dil ki dhadkan",
    ],
    "pediatrician": [
        "child fever",
        "baby fever",
        "child cough",
        "vaccination",
        "child stomach pain",
        "baby not eating",
        "child vomiting",
        "kids allergy",
        "bachcha bukhar",
        "baby checkup",
    ],
    "orthopedic": [
        "bone pain",
        "joint pain",
        "back pain",
        "knee pain",
        "shoulder pain",
        "fracture",
        "sprain",
        "arthritis",
        "neck pain",
        "sports injury",
        "haddi dard",
        "ghutna dard",
        "kamar dard",
    ],
    "neurologist": [
        "migraine",
        "severe headache",
        "dizziness",
        "fits",
        "seizure",
        "numbness",
        "tingling",
        "memory loss",
        "nerve pain",
        "weakness in limbs",
        "sir dard",
        "chakkar",
    ],
    "ent specialist": [
        "ear pain",
        "throat pain",
        "nose blockage",
        "sinus",
        "hearing problem",
        "tonsils",
        "voice change",
        "ear discharge",
        "sore throat",
        "kaan dard",
        "gala dard",
        "naak band",
    ],
    "gynecologist": [
        "period pain",
        "irregular periods",
        "pregnancy",
        "pcos",
        "white discharge",
        "menstrual cramps",
        "fertility concern",
        "women health",
        "pelvic pain",
        "mahila doctor",
    ],
    "ophthalmologist": [
        "eye pain",
        "red eyes",
        "blurred vision",
        "watery eyes",
        "eye infection",
        "dry eyes",
        "spectacles",
        "cataract",
        "aankh dard",
        "aankh lal",
    ],
    "psychiatrist": [
        "anxiety",
        "depression",
        "panic attack",
        "stress",
        "sleep problem",
        "mood swings",
        "mental health",
        "overthinking",
        "insomnia",
    ],
    "endocrinologist": [
        "diabetes",
        "thyroid",
        "hormone problem",
        "weight gain",
        "weight loss",
        "sugar problem",
        "pcod",
        "insulin",
    ],
    "pulmonologist": [
        "breathing problem",
        "asthma",
        "wheezing",
        "chronic cough",
        "shortness of breath",
        "lung infection",
        "chest congestion",
        "saans phoolna",
    ],
}

DEMO_DOCTOR_CATALOG = [
    ("Dr. Meera Sharma", "dermatologist", ["hi", "en"]),
    ("Dr. Arjun Rao", "general physician", ["en", "hi"]),
    ("Dr. Nisha Khan", "dentist", ["hi", "en"]),
    ("Dr. Kabir Sen", "cardiologist", ["en", "hi"]),
    ("Dr. Priya Menon", "pediatrician", ["en", "hi"]),
    ("Dr. Rohan Iyer", "orthopedic", ["en", "hi"]),
    ("Dr. Aditi Kapoor", "neurologist", ["en", "hi"]),
    ("Dr. Farah Siddiqui", "ent specialist", ["en", "hi"]),
    ("Dr. Kavya Desai", "gynecologist", ["en", "hi"]),
    ("Dr. Vikram Malhotra", "ophthalmologist", ["en", "hi"]),
    ("Dr. Sameer Kulkarni", "psychiatrist", ["en", "hi"]),
    ("Dr. Neha Bansal", "endocrinologist", ["en", "hi"]),
    ("Dr. Omar Khan", "pulmonologist", ["en", "hi"]),
]

DEMO_SLOT_TIMES = [
    time(9, 0),
    time(10, 0),
    time(11, 0),
    time(12, 0),
    time(13, 0),
    time(14, 0),
    time(15, 0),
    time(16, 0),
    time(17, 0),
    time(18, 0),
]
DEMO_SLOT_DAY_OFFSETS = [1, 2]
SLOT_OPTIONS_LIMIT = 20


def get_or_create_user(session: Session, phone: str, language: str) -> User:
    user = session.exec(select(User).where(User.phone == phone)).first()
    if user:
        if language and user.language_preference != language:
            user.language_preference = language
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    user = User(phone=phone, language_preference=language or "en")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_or_create_call(session: Session, call_sid: str, user: User, language: str) -> CallLog:
    call = session.exec(select(CallLog).where(CallLog.call_sid == call_sid)).first()
    if call:
        return call

    call = CallLog(call_sid=call_sid, user_id=user.id, language_detected=language)
    session.add(call)
    session.commit()
    session.refresh(call)
    return call


def add_transcript(session: Session, call_id: int, speaker: Speaker, text: str, language: str) -> None:
    session.add(Transcript(call_id=call_id, speaker=speaker, text=text, language=language))
    session.commit()


def list_doctors(session: Session) -> list[Doctor]:
    return list(session.exec(select(Doctor).where(Doctor.active == True).order_by(Doctor.name)).all())


def list_available_slots(session: Session, specialization: str | None = None) -> list[SlotRead]:
    statement = (
        select(Slot, Doctor)
        .join(Doctor, Slot.doctor_id == Doctor.id)
        .where(and_(Slot.is_booked == False, Slot.start_time > datetime.now(timezone.utc), Doctor.active == True))
        .order_by(Slot.start_time)
    )
    if specialization:
        statement = statement.where(Doctor.specialization == specialization)

    rows = session.exec(statement).all()
    return [
        SlotRead(
            id=slot.id,
            doctor_id=doctor.id,
            doctor_name=doctor.name,
            specialization=doctor.specialization,
            start_time=slot.start_time,
            end_time=slot.end_time,
        )
        for slot, doctor in rows
    ]


def find_specialization_by_symptoms(session: Session, message: str) -> str | None:
    tokens = {token for token in re.findall(r"[a-zA-Z]+|[\u0900-\u097F]+", message.lower()) if len(token) > 2}
    if not tokens:
        return None
    doctors = session.exec(select(Doctor).where(Doctor.active == True)).all()
    best_specialization: str | None = None
    best_score = 0
    lowered = message.lower()
    for doctor in doctors:
        phrases = list(doctor.symptoms or []) + [doctor.specialization]
        score = 0
        for phrase in phrases:
            normalized = phrase.lower()
            phrase_tokens = {token for token in re.findall(r"[a-zA-Z]+|[\u0900-\u097F]+", normalized) if len(token) > 2}
            if normalized and normalized in lowered:
                score += 3
            score += len(tokens.intersection(phrase_tokens))
        if score > best_score:
            best_score = score
            best_specialization = doctor.specialization
    return best_specialization if best_score > 0 else None


def get_dashboard_metrics(session: Session) -> dict:
    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    total_calls = session.exec(select(func.count(CallLog.id)).where(CallLog.started_at >= today_start)).one()
    total_bookings = session.exec(select(func.count(Appointment.id)).where(Appointment.created_at >= today_start)).one()

    language_rows = session.exec(
        select(CallLog.language_detected, func.count(CallLog.id))
        .where(CallLog.started_at >= today_start)
        .group_by(CallLog.language_detected)
    ).all()
    language_distribution = {language or "unknown": count for language, count in language_rows}
    top_language = max(language_distribution, key=language_distribution.get) if language_distribution else None

    demand_rows = session.exec(
        select(Doctor.name, func.count(Appointment.id))
        .join(Appointment, Appointment.doctor_id == Doctor.id)
        .where(Appointment.created_at >= today_start)
        .group_by(Doctor.name)
        .order_by(func.count(Appointment.id).desc())
    ).all()
    doctor_demand = {doctor_name: count for doctor_name, count in demand_rows}

    conversion = round((total_bookings / total_calls) * 100, 2) if total_calls else 0.0
    return {
        "total_calls_today": total_calls,
        "total_bookings_today": total_bookings,
        "booking_conversion_percent": conversion,
        "top_language": top_language,
        "language_distribution": language_distribution,
        "doctor_demand": doctor_demand,
    }


def list_recent_bookings(session: Session, limit: int = 10) -> list[dict]:
    rows = session.exec(
        select(Appointment, User, Doctor, Slot)
        .join(User, Appointment.user_id == User.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .join(Slot, Appointment.slot_id == Slot.id)
        .order_by(Appointment.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "appointment_id": appointment.id,
            "created_at": appointment.created_at,
            "patient_name": user.name,
            "doctor_name": doctor.name,
            "specialization": doctor.specialization,
            "slot_start": slot.start_time,
            "status": appointment.status.value,
        }
        for appointment, user, doctor, slot in rows
    ]


def list_transcripts(session: Session, call_sid: str | None = None, limit: int = 10) -> list[dict]:
    statement = select(CallLog).order_by(CallLog.started_at.desc()).limit(limit)
    if call_sid:
        statement = select(CallLog).where(CallLog.call_sid == call_sid).order_by(CallLog.started_at.desc()).limit(1)
    calls = session.exec(statement).all()
    output = []
    for call in calls:
        turns = session.exec(
            select(Transcript).where(Transcript.call_id == call.id).order_by(Transcript.timestamp)
        ).all()
        output.append(
            {
                "call_id": call.id,
                "call_sid": call.call_sid,
                "started_at": call.started_at,
                "language_detected": call.language_detected,
                "outcome": call.outcome.value,
                "turns": [
                    {
                        "speaker": turn.speaker.value,
                        "text": turn.text,
                        "language": turn.language,
                        "timestamp": turn.timestamp,
                    }
                    for turn in turns
                ],
            }
        )
    return output


def list_notifications(session: Session, limit: int = 20) -> list[NotificationLog]:
    return list(session.exec(select(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit)).all())


def book_appointment(session: Session, user_id: int, doctor_id: int, slot_id: int) -> Appointment:
    slot = session.get(Slot, slot_id)
    if not slot or slot.doctor_id != doctor_id or slot.is_booked:
        raise HTTPException(status_code=409, detail="Selected slot is no longer available")

    appointment = Appointment(user_id=user_id, doctor_id=doctor_id, slot_id=slot_id)
    slot.is_booked = True
    session.add(slot)
    session.add(appointment)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Selected slot is no longer available") from exc

    session.refresh(appointment)
    user = session.get(User, user_id)
    if user:
        user.preferred_doctor_id = doctor_id
        user.last_appointment_id = appointment.id
        session.add(user)
        session.commit()
    return appointment


def send_booking_confirmation(
    session: Session,
    appointment: Appointment,
    recipient_phone: str | None = None,
) -> MessageResult:
    user = session.get(User, appointment.user_id)
    doctor = session.get(Doctor, appointment.doctor_id)
    slot = session.get(Slot, appointment.slot_id)
    if not user or not doctor or not slot:
        return MessageResult(status="sms_failed", detail="Booking confirmation data is incomplete.")

    body = build_booking_confirmation_message(appointment, user, doctor, slot)
    recipient = recipient_phone or user.phone
    result = sms_service.send_sms(recipient, body)
    session.add(
        NotificationLog(
            appointment_id=appointment.id,
            user_id=user.id,
            recipient=recipient,
            message=body,
            status=result.status,
            provider_message_id=result.provider_message_id,
            error_detail=result.detail,
        )
    )
    session.commit()
    return result


def sync_booking_calendar(
    session: Session,
    appointment: Appointment,
    recipient_phone: str | None = None,
) -> str:
    user = session.get(User, appointment.user_id)
    doctor = session.get(Doctor, appointment.doctor_id)
    slot = session.get(Slot, appointment.slot_id)
    if not user or not doctor or not slot:
        appointment.calendar_status = "calendar_data_missing"
        session.add(appointment)
        session.commit()
        return appointment.calendar_status

    result = calendar_service.create_appointment_event(appointment, user, doctor, slot, recipient_phone)
    appointment.calendar_status = result.status
    appointment.calendar_event_id = result.event_id
    session.add(appointment)
    session.commit()
    return result.status


def build_booking_confirmation_message(
    appointment: Appointment,
    user: User,
    doctor: Doctor,
    slot: Slot,
) -> str:
    patient = user.name or "Patient"
    clinic_name = get_settings().clinic_name
    return (
        f"{clinic_name}: Hi {patient}, your appointment with {doctor.name} "
        f"on {format_slot(slot.start_time)} is confirmed. Booking ID: {appointment.id}."
    )


def handle_chat(session: Session, call_sid: str, user_phone: str, message: str, language: str) -> ChatResponse:
    user = get_or_create_user(session, user_phone, language)
    call = get_or_create_call(session, call_sid, user, language)
    add_transcript(session, call.id, Speaker.user, message, language)

    intent = detect_intent(message)
    response = advance_conversation(session, user, call, message, intent)

    add_transcript(session, call.id, Speaker.assistant, response.reply, language)
    return response


def start_or_resume_session(
    session: Session,
    call_sid: str,
    user_phone: str,
    language: str,
    fresh: bool = False,
) -> SessionStateResponse:
    user = get_or_create_user(session, user_phone, language)
    call = get_or_create_call(session, call_sid, user, language)
    if fresh:
        reset_call_fields(call)
        session.add(call)
        session.commit()
    return get_session_state(session, call_sid, user.phone, language)


def get_session_state(
    session: Session,
    call_sid: str,
    fallback_user_phone: str = "demo",
    fallback_language: str = "en",
) -> SessionStateResponse:
    call = session.exec(select(CallLog).where(CallLog.call_sid == call_sid)).first()
    if not call:
        return SessionStateResponse(
            call_id=call_sid,
            user_phone=fallback_user_phone,
            language=fallback_language,
            state=ConversationState.idle,
        )

    user = session.get(User, call.user_id) if call.user_id else None
    current_state = normalize_conversation_state(call.current_state)
    review = build_booking_review(session, call)
    slot_options: list[SlotOption] | None = None
    if current_state in {ConversationState.show_slots, ConversationState.collect_name, ConversationState.confirm_name}:
        slot_options = build_slot_options(list_available_slots(session, call.selected_specialization))

    last_assistant = session.exec(
        select(Transcript)
        .where(and_(Transcript.call_id == call.id, Transcript.speaker == Speaker.assistant))
        .order_by(Transcript.timestamp.desc())
    ).first()

    return SessionStateResponse(
        call_id=call.call_sid,
        user_phone=(user.phone if user else fallback_user_phone),
        language=call.language_detected or (user.language_preference if user else fallback_language),
        state=current_state,
        selected_specialization=call.selected_specialization,
        selected_doctor_id=call.selected_doctor_id,
        selected_slot_id=call.selected_slot_id,
        patient_name=call.patient_name,
        patient_gender=call.patient_gender,
        patient_age=call.patient_age,
        patient_phone=call.patient_phone,
        booking_review=review,
        slot_options=slot_options,
        selected_slot=build_selected_slot_option(session, call),
        last_assistant_reply=last_assistant.text if last_assistant else None,
    )


def reset_session(session: Session, call_sid: str) -> SessionStateResponse:
    call = session.exec(select(CallLog).where(CallLog.call_sid == call_sid)).first()
    if not call:
        return SessionStateResponse(call_id=call_sid, user_phone="demo", language="en", state=ConversationState.idle)

    reset_call_fields(call)
    session.add(call)
    session.commit()

    user = session.get(User, call.user_id) if call.user_id else None
    return get_session_state(
        session,
        call_sid=call_sid,
        fallback_user_phone=user.phone if user else "demo",
        fallback_language=call.language_detected or (user.language_preference if user else "en"),
    )


def reset_call_fields(call: CallLog) -> None:
    call.current_state = ConversationState.idle.value
    call.selected_specialization = None
    call.selected_doctor_id = None
    call.selected_slot_id = None
    call.patient_name = None
    call.patient_gender = None
    call.patient_age = None
    call.patient_phone = None
    call.outcome = CallOutcome.active


def record_user_transcript(session: Session, call_sid: str, user_phone: str, text: str, language: str) -> None:
    user = get_or_create_user(session, user_phone, language)
    call = get_or_create_call(session, call_sid, user, language)
    add_transcript(session, call.id, Speaker.user, text, language)


def normalize_conversation_state(state: ConversationState | str | None) -> ConversationState:
    if isinstance(state, ConversationState):
        return state
    if isinstance(state, str):
        try:
            return ConversationState(state)
        except ValueError:
            return ConversationState.idle
    return ConversationState.idle


def advance_conversation(session: Session, user: User, call: CallLog, message: str, intent: IntentResult) -> ChatResponse:
    current_state = normalize_conversation_state(call.current_state)
    symptom_specialization = intent.specialization or find_specialization_by_symptoms(session, message)

    if intent.intent == "doctor_inquiry":
        return handle_inquiry(session, call, intent)

    if intent.intent == "language_switch":
        reply = "Of course. Tell me what you need help with, and I will guide you."
        return persist_call_response(session, call, ConversationState.idle, reply, intent.intent)

    if current_state == ConversationState.idle:
        if intent.intent == "repeat_last_doctor" and user.preferred_doctor_id:
            call.selected_doctor_id = user.preferred_doctor_id
            return present_slots_for_doctor(session, call, intent.intent)
        if intent.intent == "book_appointment" and symptom_specialization:
            return select_specialization(session, call, symptom_specialization, intent.intent)
        if intent.intent == "specialization_selected" and symptom_specialization:
            return select_specialization(session, call, symptom_specialization, intent.intent)
        if symptom_specialization:
            return select_specialization(session, call, symptom_specialization, "symptom_selected")
        if intent.intent in {"book_appointment", "doctor_inquiry"}:
            reply = "Sure. Please tell me the symptoms you are facing, or the specialist you would like to see."
            return persist_call_response(
                session, call, ConversationState.collect_specialization, reply, intent.intent, "ask_specialization"
            )

    if current_state == ConversationState.collect_specialization:
        if symptom_specialization:
            return select_specialization(session, call, symptom_specialization, intent.intent)

    if current_state == ConversationState.show_slots:
        if intent.intent == "slot_selected":
            slot = choose_available_slot(
                session,
                call.selected_doctor_id,
                intent.slot_hint,
                call.selected_specialization,
            )
            if slot:
                call.selected_doctor_id = slot.doctor_id
                call.selected_slot_id = slot.id
                reply = "That slot works. Can I have the patient's full name?"
                return persist_call_response(session, call, ConversationState.collect_name, reply, intent.intent, "collect_name")
            reply = "I could not match that time. Could you choose one of the options shown on screen?"
            return persist_call_response(session, call, ConversationState.show_slots, reply, intent.intent, "show_slots")

    if current_state == ConversationState.collect_name:
        if intent.intent == "slot_selected":
            slot = choose_available_slot(
                session,
                call.selected_doctor_id,
                intent.slot_hint,
                call.selected_specialization,
            )
            if slot:
                call.selected_doctor_id = slot.doctor_id
                call.selected_slot_id = slot.id
                reply = "I changed the slot. Please tell me the patient's full name."
                return persist_call_response(
                    session,
                    call,
                    ConversationState.collect_name,
                    reply,
                    intent.intent,
                    "collect_name",
                    slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
                )
            reply = "I could not match that slot. The available options are still on screen. Please tell me the patient's full name, or choose one of those slots."
            return persist_call_response(
                session,
                call,
                ConversationState.collect_name,
                reply,
                intent.intent,
                "fallback",
                slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
            )
        name = normalize_patient_name(intent.name or parse_name_from_state_input(message))
        if name:
            call.patient_name = name
            reply = f"I heard the name as {name}. Is that correct? You can say yes, no, or spell it for me in English."
            return persist_call_response(
                session,
                call,
                ConversationState.confirm_name,
                reply,
                intent.intent,
                "confirm_name",
                slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
            )

    if current_state == ConversationState.confirm_name:
        if intent.intent == "affirmative":
            user.name = call.patient_name
            session.add(user)
            reply = "Great. What gender should I add for the appointment?"
            return persist_call_response(session, call, ConversationState.collect_gender, reply, intent.intent, "collect_gender")
        if intent.intent == "negative":
            call.patient_name = None
            reply = "No problem. Please say the full name again slowly, or spell it letter by letter."
            return persist_call_response(
                session,
                call,
                ConversationState.collect_name,
                reply,
                intent.intent,
                "collect_name",
                slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
            )
        name = normalize_patient_name(intent.name or parse_name_from_state_input(message))
        if name:
            call.patient_name = name
            reply = f"Thanks. I heard {name}. Is that correct?"
            return persist_call_response(
                session,
                call,
                ConversationState.confirm_name,
                reply,
                intent.intent,
                "confirm_name",
                slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
            )

    if current_state == ConversationState.collect_gender:
        if intent.gender:
            call.patient_gender = intent.gender
            user.gender = intent.gender
            session.add(user)
            reply = "Got it. How old is the patient?"
            return persist_call_response(session, call, ConversationState.collect_age, reply, intent.intent, "collect_age")

    if current_state == ConversationState.collect_age:
        if intent.age is not None:
            call.patient_age = intent.age
            user.age = intent.age
            session.add(user)
            reply = "Thanks. What mobile number should we send the confirmation to?"
            return persist_call_response(session, call, ConversationState.collect_phone, reply, intent.intent, "collect_phone")

    if current_state == ConversationState.collect_phone:
        if intent.phone:
            call.patient_phone = intent.phone
            review = build_booking_review(session, call)
            if not review:
                reply = "I could not prepare the summary yet. Please pick the slot once more from the options."
                return persist_call_response(
                    session,
                    call,
                    ConversationState.show_slots,
                    reply,
                    intent.intent,
                    "show_slots",
                    slot_options=build_slot_options(
                        list_available_slots(session, call.selected_specialization),
                    ),
                )
            reply = "I have your details on screen. Please take a quick look and say confirm if everything is right."
            return persist_call_response(
                session,
                call,
                ConversationState.review_booking,
                reply,
                intent.intent,
                "review_details",
                booking_review=review,
            )

    if current_state in {ConversationState.review_booking, ConversationState.confirm_booking}:
        if intent.gender:
            call.patient_gender = intent.gender
            review = build_booking_review(session, call)
            reply = "I updated the gender. Please review the details again and say confirm if everything is right."
            return persist_call_response(
                session,
                call,
                ConversationState.review_booking,
                reply,
                intent.intent,
                "review_details",
                booking_review=review,
            )
        if intent.age is not None:
            call.patient_age = intent.age
            review = build_booking_review(session, call)
            reply = "I updated the age. Please review the details again and say confirm if everything is right."
            return persist_call_response(
                session,
                call,
                ConversationState.review_booking,
                reply,
                intent.intent,
                "review_details",
                booking_review=review,
            )
        if intent.phone:
            call.patient_phone = intent.phone
            review = build_booking_review(session, call)
            reply = "I updated the mobile number. Please review the details again and say confirm if everything is right."
            return persist_call_response(
                session,
                call,
                ConversationState.review_booking,
                reply,
                intent.intent,
                "review_details",
                booking_review=review,
            )
        corrected_name = normalize_patient_name(intent.name or parse_name_from_state_input(message))
        if corrected_name and intent.intent not in {"affirmative", "negative"}:
            call.patient_name = corrected_name
            reply = f"Thanks. I updated the name to {corrected_name}. Is that correct?"
            return persist_call_response(
                session,
                call,
                ConversationState.confirm_name,
                reply,
                "name_provided",
                "confirm_name",
                slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
            )
        if intent.intent == "affirmative":
            if not all([call.patient_name, call.patient_gender, call.patient_age, call.patient_phone]):
                reply = "I still need a few details before I can book this."
                return persist_call_response(
                    session, call, ConversationState.collect_name, reply, intent.intent, "collect_name"
                )

            # Keep user profile in sync with final confirmed intake data without making phone unique.
            user.name = call.patient_name
            user.gender = call.patient_gender
            user.age = call.patient_age
            session.add(user)
            session.commit()

            appointment = book_appointment(session, user.id, call.selected_doctor_id, call.selected_slot_id)
            notification = send_booking_confirmation(session, appointment, call.patient_phone)
            sync_booking_calendar(session, appointment, call.patient_phone)
            call.outcome = CallOutcome.booked
            reply = f"All set. Your appointment is confirmed, and your booking ID is {appointment.id}."
            return persist_call_response(
                session,
                call,
                ConversationState.booked,
                reply,
                intent.intent,
                "book_appointment",
                appointment.id,
                notification.status,
                booking_review=build_booking_review(session, call),
            )
        if intent.intent == "negative":
            call.patient_name = None
            call.patient_gender = None
            call.patient_age = None
            call.patient_phone = None
            reply = "No problem. I will correct the details. The slot options are still on screen. Please tell me the patient's full name again."
            return persist_call_response(
                session,
                call,
                ConversationState.collect_name,
                reply,
                intent.intent,
                "collect_name",
                slot_options=build_slot_options(list_available_slots(session, call.selected_specialization)),
            )

    reply = fallback_reply_for_state(current_state)
    llm_reply = generate_llm_reply(session, intent)
    if llm_reply and current_state == ConversationState.idle:
        reply = llm_reply
    call.outcome = CallOutcome.fallback
    return persist_call_response(session, call, current_state, reply, intent.intent, "fallback")


def fallback_reply_for_state(state: ConversationState) -> str:
    state = normalize_conversation_state(state)
    prompts = {
        ConversationState.collect_specialization: "Please tell me the symptoms you are facing, or the specialist you would like to see.",
        ConversationState.show_slots: "Choose one of the options on screen, or say the time that works for you.",
        ConversationState.collect_name: "What name should I put on the appointment?",
        ConversationState.confirm_name: "Please say yes if the name is correct, or say no and spell the name again.",
        ConversationState.collect_gender: "What gender should I add for the appointment?",
        ConversationState.collect_age: "How old is the patient?",
        ConversationState.collect_phone: "Please say the 10 digit mobile number slowly.",
        ConversationState.review_booking: "Please review the details on screen and say confirm if they look right.",
        ConversationState.confirm_booking: "Please review the details on screen and say confirm if they look right.",
        ConversationState.booked: "This appointment is already confirmed. You can start a new session for another booking.",
    }
    return prompts.get(state, "I missed that. Could you say it once more?")


def handle_inquiry(session: Session, call: CallLog, intent: IntentResult) -> ChatResponse:
    doctors = list_doctors(session)
    doctor_list = ", ".join(f"{doctor.name} ({doctor.specialization})" for doctor in doctors[:5])
    context = f"Available doctors: {doctor_list}. Clinic handles appointment booking and general inquiry support."
    llm_result = llm_service.generate_reply("Patient asked a clinic inquiry.", context=context)
    if llm_result.status == "llm_generated":
        reply = llm_result.text
    else:
        reply = "I can help with doctor availability, timings, and booking. What would you like to check?"
    return persist_call_response(session, call, call.current_state, reply, intent.intent, "inquiry")


def generate_llm_reply(session: Session, intent: IntentResult) -> str | None:
    if intent.intent != "unknown":
        return None
    context = "You can book appointments, ask doctor availability, and ask clinic inquiry questions."
    llm_result = llm_service.generate_reply("Patient utterance was unclear. Ask a clarifying question.", context=context)
    if llm_result.status != "llm_generated":
        return None
    return llm_result.text


def select_specialization(session: Session, call: CallLog, specialization: str, intent: str) -> ChatResponse:
    slots = list_available_slots(session, specialization)
    if not slots:
        reply = f"I do not see open {friendly_specialization(specialization)} slots right now. Would you like to try another specialist?"
        return persist_call_response(session, call, ConversationState.collect_specialization, reply, intent, "show_slots")

    call.selected_specialization = specialization
    call.selected_doctor_id = slots[0].doctor_id
    slot_options = build_slot_options(slots)
    doctor_names = sorted({option.doctor_name for option in slot_options})
    doctor_text = doctor_names[0] if len(doctor_names) == 1 else f"{len(doctor_names)} doctors"
    reply = (
        f"I found a few {friendly_specialization(specialization)} slots with {doctor_text}. "
        "They are on screen now. Which one works for you?"
    )
    return persist_call_response(
        session,
        call,
        ConversationState.show_slots,
        reply,
        intent,
        "show_slots",
        slot_options=slot_options,
    )


def present_slots_for_doctor(session: Session, call: CallLog, intent: str) -> ChatResponse:
    slot = choose_first_available_slot(session, call.selected_doctor_id)
    if not slot:
        reply = "I do not see open slots with your previous doctor right now. Which specialist should I check instead?"
        return persist_call_response(session, call, ConversationState.collect_specialization, reply, intent, "ask_specialization")
    doctor = session.get(Doctor, call.selected_doctor_id)
    call.selected_specialization = doctor.specialization if doctor else None
    reply = f"{doctor.name} has availability on screen. Which slot works for you?"
    return persist_call_response(session, call, ConversationState.show_slots, reply, intent, "show_slots")


def choose_first_available_slot(session: Session, doctor_id: int | None) -> Slot | None:
    return choose_available_slot(session, doctor_id)


def choose_available_slot(
    session: Session,
    doctor_id: int | None,
    slot_hint: str | None = None,
    specialization: str | None = None,
) -> Slot | None:
    if not doctor_id and not specialization:
        return None
    statement = (
        select(Slot, Doctor)
        .join(Doctor, Slot.doctor_id == Doctor.id)
        .where(and_(Slot.is_booked == False, Slot.start_time > datetime.now(timezone.utc), Doctor.active == True))
        .order_by(Slot.start_time)
    )
    if specialization:
        statement = statement.where(Doctor.specialization == specialization)
    elif doctor_id:
        statement = statement.where(Slot.doctor_id == doctor_id)
    rows = session.exec(statement).all()
    slots = [slot for slot, _doctor in rows]
    if not slots:
        return None
    if not slot_hint:
        return slots[0]

    slot_id = parse_requested_slot_id(slot_hint)
    if slot_id is not None:
        for slot in slots:
            if slot.id == slot_id:
                return slot

    target_hour = parse_requested_hour(slot_hint)
    target_date = parse_requested_date(slot_hint)
    if slot_id is None and target_hour is None and target_date is None:
        return None
    for slot in slots:
        if target_hour is not None and slot.start_time.hour != target_hour:
            continue
        if target_date is not None and slot.start_time.date() != target_date:
            continue
        return slot
    return None


def parse_requested_hour(slot_hint: str) -> int | None:
    lowered = slot_hint.lower()
    match = re.search(r"\b(\d{1,2})(?::\d{2})?\s*(am|pm)?\b", lowered)
    if not match:
        return None
    hour = int(match.group(1))
    suffix = match.group(2)
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if not suffix and hour <= 7:
        hour += 12
    return hour


def parse_requested_slot_id(slot_hint: str) -> int | None:
    match = re.search(r"(?:slot|id)\s*[:#-]?\s*(\d+)", slot_hint.lower())
    if not match:
        return None
    return int(match.group(1))


def parse_requested_date(slot_hint: str):
    lowered = slot_hint.lower()
    today = datetime.now(timezone.utc).date()
    if "tomorrow" in lowered or "kal" in lowered:
        return today + timedelta(days=1)
    if "today" in lowered or "aaj" in lowered:
        return today
    return None


def parse_name_from_state_input(message: str) -> str | None:
    if re.search(r"\[[^\]]+\]", message):
        return None
    cleaned = "".join(
        char if char.isalpha() or char.isspace() or unicodedata.category(char).startswith("M") else " "
        for char in message
    )
    words = [
        word
        for word in cleaned.split()
        if word.lower() not in {"my", "name", "is", "mera", "naam", "hai", "मेरा", "नाम", "है"}
    ]
    if not words:
        return None
    candidate = normalize_spelled_name(words)
    if len(candidate) < 2:
        return None
    return normalize_patient_name(candidate)


def normalize_patient_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"\s+", " ", name).strip()
    if not cleaned:
        return None
    if contains_devanagari(cleaned):
        cleaned = transliterate_devanagari(cleaned)
    cleaned = re.sub(r"[^A-Za-z\s.'-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) < 2:
        return None
    return cleaned.title()


def contains_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097f" for char in text)


def transliterate_devanagari(text: str) -> str:
    independent_vowels = {
        "अ": "a",
        "आ": "aa",
        "इ": "i",
        "ई": "ee",
        "उ": "u",
        "ऊ": "oo",
        "ए": "e",
        "ऐ": "ai",
        "ओ": "o",
        "औ": "au",
        "ऋ": "ri",
    }
    consonants = {
        "क": "k",
        "ख": "kh",
        "ग": "g",
        "घ": "gh",
        "च": "ch",
        "छ": "chh",
        "ज": "j",
        "झ": "jh",
        "ट": "t",
        "ठ": "th",
        "ड": "d",
        "ढ": "dh",
        "ण": "n",
        "त": "t",
        "थ": "th",
        "द": "d",
        "ध": "dh",
        "न": "n",
        "प": "p",
        "फ": "ph",
        "ब": "b",
        "भ": "bh",
        "म": "m",
        "य": "y",
        "र": "r",
        "ल": "l",
        "व": "v",
        "श": "sh",
        "ष": "sh",
        "स": "s",
        "ह": "h",
        "ळ": "l",
    }
    vowel_marks = {
        "ा": "aa",
        "ि": "i",
        "ी": "ee",
        "ु": "u",
        "ू": "oo",
        "े": "e",
        "ै": "ai",
        "ो": "o",
        "ौ": "au",
        "ृ": "ri",
    }
    nasal_marks = {"ं": "n", "ँ": "n"}
    output: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            output.append(" ")
            index += 1
            continue
        if char in independent_vowels:
            output.append(independent_vowels[char])
            index += 1
            continue
        if char in consonants:
            base = consonants[char]
            next_char = text[index + 1] if index + 1 < len(text) else ""
            if next_char == "्":
                output.append(base)
                index += 2
                continue
            if next_char in vowel_marks:
                output.append(base + vowel_marks[next_char])
                index += 2
                continue
            output.append(base + "a")
            index += 1
            continue
        if char in nasal_marks:
            output.append(nasal_marks[char])
        elif char == "़":
            pass
        else:
            output.append(char)
        index += 1
    transliterated = "".join(output)
    return re.sub(r"a\b", "", transliterated)


def normalize_spelled_name(words: list[str]) -> str:
    if len(words) >= 3 and all(len(word) == 1 and word.isascii() for word in words):
        return "".join(words)
    return " ".join(words).strip()


def build_slot_options(slots: list[SlotRead]) -> list[SlotOption]:
    options: list[SlotOption] = []
    for slot in slots[:SLOT_OPTIONS_LIMIT]:
        options.append(
            SlotOption(
                slot_id=slot.id,
                doctor_name=slot.doctor_name,
                specialization=slot.specialization,
                start_time=slot.start_time,
                label=f"Slot {slot.id}: {slot.doctor_name} ({slot.specialization}) on {format_slot(slot.start_time)}",
            )
        )
    return options


def build_selected_slot_option(session: Session, call: CallLog) -> SlotOption | None:
    if not call.selected_slot_id:
        return None
    slot = session.get(Slot, call.selected_slot_id)
    if not slot:
        return None
    doctor = session.get(Doctor, slot.doctor_id)
    if not doctor:
        return None
    return SlotOption(
        slot_id=slot.id,
        doctor_name=doctor.name,
        specialization=doctor.specialization,
        start_time=slot.start_time,
        label=f"Slot {slot.id}: {doctor.name} ({doctor.specialization}) on {format_slot(slot.start_time)}",
    )


def friendly_specialization(specialization: str | None) -> str:
    labels = {
        "cardiologist": "heart specialist",
        "dermatologist": "skin specialist",
        "general physician": "general physician",
        "dentist": "dentist",
        "pediatrician": "child specialist",
        "orthopedic": "bone and joint specialist",
        "neurologist": "neurologist",
        "ent specialist": "ENT specialist",
        "gynecologist": "gynecologist",
        "ophthalmologist": "eye specialist",
        "psychiatrist": "mental health specialist",
        "endocrinologist": "diabetes and hormone specialist",
        "pulmonologist": "lung specialist",
    }
    if not specialization:
        return "specialist"
    return labels.get(specialization, specialization)


def build_booking_review(session: Session, call: CallLog) -> BookingReview | None:
    if not all([call.patient_name, call.patient_gender, call.patient_age, call.patient_phone, call.selected_slot_id]):
        return None
    slot = session.get(Slot, call.selected_slot_id)
    if not slot:
        return None
    doctor = session.get(Doctor, slot.doctor_id)
    if not doctor:
        return None
    call.selected_doctor_id = doctor.id
    call.selected_specialization = doctor.specialization
    return BookingReview(
        name=call.patient_name,
        gender=call.patient_gender,
        age=call.patient_age,
        phone=call.patient_phone,
        doctor_name=doctor.name,
        specialization=doctor.specialization,
        slot_time=format_slot(slot.start_time),
    )


def persist_call_response(
    session: Session,
    call: CallLog,
    next_state: ConversationState | str,
    reply: str,
    intent: str,
    action: str | None = None,
    appointment_id: int | None = None,
    notification_status: str | None = None,
    booking_review: BookingReview | None = None,
    slot_options: list[SlotOption] | None = None,
) -> ChatResponse:
    next_state = normalize_conversation_state(next_state)
    reply = maybe_polish_voice_reply(
        raw_reply=reply,
        state=next_state,
        action=action,
        appointment_id=appointment_id,
        booking_review=booking_review,
        slot_options=slot_options,
    )
    call.current_state = next_state.value
    session.add(call)
    session.commit()
    session.refresh(call)
    return ChatResponse(
        reply=reply,
        next_state=next_state,
        intent=intent,
        action=action,
        appointment_id=appointment_id,
        notification_status=notification_status,
        booking_review=booking_review,
        slot_options=slot_options,
        selected_slot=build_selected_slot_option(session, call),
    )


def maybe_polish_voice_reply(
    raw_reply: str,
    state: ConversationState | str,
    action: str | None,
    appointment_id: int | None,
    booking_review: BookingReview | None,
    slot_options: list[SlotOption] | None,
) -> str:
    state = normalize_conversation_state(state)
    if not should_polish_voice_reply(raw_reply, action, appointment_id, booking_review, slot_options):
        return raw_reply
    result = llm_service.polish_voice_reply(raw_reply, state.value, action)
    if result.status != "llm_generated":
        return raw_reply
    polished = sanitize_polished_reply(result.text)
    if not polished:
        return raw_reply
    return polished


def should_polish_voice_reply(
    reply: str,
    action: str | None,
    appointment_id: int | None,
    booking_review: BookingReview | None,
    slot_options: list[SlotOption] | None,
) -> bool:
    if appointment_id or booking_review or slot_options:
        return False
    if action in {"show_slots", "book_appointment", "review_details"}:
        return False
    if any(char.isdigit() for char in reply):
        return False
    return True


def sanitize_polished_reply(text: str) -> str:
    cleaned = text.strip().strip('"').strip("'").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) > 220:
        return ""
    return cleaned


def format_slot(value: datetime) -> str:
    return value.strftime("%A %I:%M %p").replace(" 0", " ")


def seed_demo_data(session: Session) -> None:
    doctors = session.exec(select(Doctor).order_by(Doctor.id)).all()
    doctors_by_name = {doctor.name: doctor for doctor in doctors}
    for name, specialization, languages in DEMO_DOCTOR_CATALOG:
        symptoms = DOCTOR_SYMPTOMS[specialization]
        doctor = doctors_by_name.get(name)
        if not doctor:
            doctor = Doctor(name=name, specialization=specialization, symptoms=symptoms, languages=languages)
            session.add(doctor)
            continue
        doctor.specialization = specialization
        doctor.symptoms = symptoms
        doctor.languages = languages
        doctor.active = True
        session.add(doctor)
    session.commit()
    doctors = session.exec(select(Doctor).where(Doctor.active == True).order_by(Doctor.id)).all()

    slots: list[Slot] = []
    for doctor in doctors:
        for day_offset in DEMO_SLOT_DAY_OFFSETS:
            slot_date = datetime.now(timezone.utc).date() + timedelta(days=day_offset)
            for slot_time in DEMO_SLOT_TIMES:
                start_time = datetime.combine(slot_date, slot_time, tzinfo=timezone.utc)
                existing_slot = session.exec(
                    select(Slot).where(and_(Slot.doctor_id == doctor.id, Slot.start_time == start_time))
                ).first()
                if not existing_slot:
                    slots.append(
                        Slot(
                            doctor_id=doctor.id,
                            start_time=start_time,
                            end_time=start_time + timedelta(minutes=30),
                        )
                    )
    if slots:
        session.add_all(slots)
        session.commit()


def reset_test_bookings(session: Session) -> None:
    for user in session.exec(select(User)).all():
        user.last_appointment_id = None
        session.add(user)
    session.commit()
    session.exec(text("DELETE FROM notificationlog"))
    session.exec(text("DELETE FROM appointment"))
    session.exec(text("DELETE FROM transcript"))
    session.exec(text("DELETE FROM calllog"))
    for slot in session.exec(select(Slot)).all():
        slot.is_booked = False
        session.add(slot)
    session.commit()


def reset_demo_database(session: Session) -> None:
    reset_test_bookings(session)
    session.exec(delete(User))
    session.commit()
    seed_demo_data(session)


def seed_demo_operational_data(session: Session, doctors: list[Doctor]) -> None:
    now = datetime.now(timezone.utc)
    doctors_by_specialization = {doctor.specialization: doctor for doctor in doctors}

    demo_specs = [
        {
            "phone": "9876500001",
            "name": "Rahul Verma",
            "language": "hi",
            "specialization": "dermatologist",
            "call_sid": "demo-call-001",
            "call_minutes_ago": 95,
            "slot_day_offset": 2,
            "slot_hour": 11,
            "sms_status": "sms_sent",
        },
        {
            "phone": "9876500002",
            "name": "Priya Nair",
            "language": "en",
            "specialization": "dentist",
            "call_sid": "demo-call-002",
            "call_minutes_ago": 65,
            "slot_day_offset": 3,
            "slot_hour": 14,
            "sms_status": "sms_sent",
        },
        {
            "phone": "9876500003",
            "name": "Amit Singh",
            "language": "hi",
            "specialization": "general physician",
            "call_sid": "demo-call-003",
            "call_minutes_ago": 35,
            "slot_day_offset": 2,
            "slot_hour": 17,
            "sms_status": "sms_failed",
        },
    ]

    for index, spec in enumerate(demo_specs, start=1):
        doctor = doctors_by_specialization.get(spec["specialization"])
        if not doctor:
            continue

        user = session.exec(select(User).where(User.phone == spec["phone"])).first()
        if not user:
            user = User(
                phone=spec["phone"],
                name=spec["name"],
                language_preference=spec["language"],
                preferred_doctor_id=doctor.id,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        call = session.exec(select(CallLog).where(CallLog.call_sid == spec["call_sid"])).first()
        if not call:
            call = CallLog(
                call_sid=spec["call_sid"],
                user_id=user.id,
                started_at=now - timedelta(minutes=spec["call_minutes_ago"]),
                ended_at=now - timedelta(minutes=max(spec["call_minutes_ago"] - 5, 0)),
                language_detected=spec["language"],
                outcome=CallOutcome.booked if spec["sms_status"] == "sms_sent" else CallOutcome.fallback,
                current_state=ConversationState.booked if spec["sms_status"] == "sms_sent" else ConversationState.idle,
                selected_doctor_id=doctor.id,
                patient_name=spec["name"],
            )
            session.add(call)
            session.commit()
            session.refresh(call)

        if not session.exec(select(Transcript).where(Transcript.call_id == call.id)).first():
            transcript_turns = [
                (Speaker.user, f"I need a {doctor.specialization} appointment", spec["language"]),
                (Speaker.assistant, f"{doctor.name} is available soon. Which slot works for you?", spec["language"]),
                (Speaker.user, "Please book the suggested time", spec["language"]),
                (Speaker.assistant, "Your appointment has been booked.", spec["language"]),
            ]
            for speaker, text_value, language in transcript_turns:
                session.add(Transcript(call_id=call.id, speaker=speaker, text=text_value, language=language))
            session.commit()

        slot_start = datetime.combine(
            now.date() + timedelta(days=spec["slot_day_offset"]),
            time(spec["slot_hour"], 0),
            tzinfo=timezone.utc,
        )
        slot = session.exec(select(Slot).where(and_(Slot.doctor_id == doctor.id, Slot.start_time == slot_start))).first()
        if not slot:
            slot = Slot(
                doctor_id=doctor.id,
                start_time=slot_start,
                end_time=slot_start + timedelta(minutes=30),
                is_booked=False,
            )
            session.add(slot)
            session.commit()
            session.refresh(slot)

        appointment = session.exec(select(Appointment).where(Appointment.slot_id == slot.id)).first()
        if not appointment:
            appointment = Appointment(user_id=user.id, doctor_id=doctor.id, slot_id=slot.id)
            slot.is_booked = True
            session.add(slot)
            session.add(appointment)
            session.commit()
            session.refresh(appointment)

        user.preferred_doctor_id = doctor.id
        user.last_appointment_id = appointment.id
        session.add(user)
        session.commit()

        existing_notification = session.exec(
            select(NotificationLog).where(NotificationLog.appointment_id == appointment.id)
        ).first()
        if not existing_notification:
            session.add(
                NotificationLog(
                    appointment_id=appointment.id,
                    user_id=user.id,
                    recipient=user.phone,
                    message=(
                        f"Pawani Medicals: Hi {user.name}, your appointment with {doctor.name} "
                        f"on {format_slot(slot.start_time)} is confirmed. Booking ID: {appointment.id}."
                    ),
                    status=spec["sms_status"],
                    provider_message_id=f"demo-msg-{index}" if spec["sms_status"] == "sms_sent" else None,
                    error_detail="Provider timeout in demo data." if spec["sms_status"] != "sms_sent" else "SMS sent.",
                )
            )
            session.commit()
