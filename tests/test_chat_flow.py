from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.config import get_settings
from app.llm import LlmResult
from app.models import Appointment, ConversationState, DoctorAvailability, NotificationLog, User
from app.services import book_appointment, handle_chat, maybe_polish_voice_reply, parse_name_from_state_input, seed_demo_data


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    seed_demo_data(session)
    return session


def test_spelled_name_is_joined_for_voice_collection() -> None:
    assert parse_name_from_state_input("S R I K A N T") == "Srikant"


def test_hindi_name_is_stored_in_english_script() -> None:
    assert parse_name_from_state_input("श्रीकांत पटनायक") == "Shreekaant Patanaayak"


def test_voice_polish_accepts_database_string_state(monkeypatch) -> None:
    def fake_polish(raw_reply: str, state: str, action: str | None = None, patient_text: str = "") -> LlmResult:
        assert state == "collect_name"
        return LlmResult(text="May I have the patient's full name?", status="llm_generated")

    monkeypatch.setattr("app.services.llm_service.polish_voice_reply", fake_polish)

    reply = maybe_polish_voice_reply(
        "What name should I put on the appointment?",
        "collect_name",
        "fallback",
        None,
        None,
        None,
    )

    assert reply == "May I have the patient's full name?"


def test_text_booking_flow_confirms_appointment(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    first = handle_chat(session, "call-1", "9999999999", "Mujhe skin doctor ka appointment chahiye", "hi")
    second = handle_chat(session, "call-1", "9999999999", "Kal 10 baje", "hi")
    third = handle_chat(session, "call-1", "9999999999", "Mera naam Rahul hai", "hi")
    fourth = handle_chat(session, "call-1", "9999999999", "yes", "en")
    fifth = handle_chat(session, "call-1", "9999999999", "male", "en")
    sixth = handle_chat(session, "call-1", "9999999999", "29", "en")
    seventh = handle_chat(session, "call-1", "9999999999", "9876543210", "en")
    eighth = handle_chat(session, "call-1", "9999999999", "Yes confirm", "en")

    assert first.next_state == ConversationState.show_slots
    assert second.next_state == ConversationState.collect_name
    assert third.next_state == ConversationState.confirm_name
    assert fourth.next_state == ConversationState.collect_gender
    assert fifth.next_state == ConversationState.collect_age
    assert sixth.next_state == ConversationState.collect_phone
    assert seventh.next_state == ConversationState.review_booking
    assert seventh.booking_review is not None
    assert eighth.next_state == ConversationState.booked
    assert eighth.appointment_id is not None
    assert eighth.notification_status == "sms_not_configured"
    notification = session.exec(
        select(NotificationLog).where(NotificationLog.appointment_id == eighth.appointment_id)
    ).first()
    assert notification is not None


def test_slot_hint_selects_requested_hour(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    handle_chat(session, "call-2", "8888888888", "I need a skin doctor appointment", "en")
    handle_chat(session, "call-2", "8888888888", "Tomorrow 10 am", "en")
    handle_chat(session, "call-2", "8888888888", "My name is Emily", "en")
    handle_chat(session, "call-2", "8888888888", "yes", "en")
    handle_chat(session, "call-2", "8888888888", "female", "en")
    handle_chat(session, "call-2", "8888888888", "31", "en")
    handle_chat(session, "call-2", "8888888888", "9123456789", "en")
    result = handle_chat(session, "call-2", "8888888888", "Confirm", "en")

    appointment = session.get(Appointment, result.appointment_id)
    availability = session.get(DoctorAvailability, appointment.availability_id)

    assert result.next_state == ConversationState.booked
    assert availability.start_time.hour == 10
    assert availability.end_time.hour == 23
    assert appointment.token_number == 1


def test_availability_can_be_selected_by_option_date_or_time_window(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()

    session_by_option = make_session()
    handle_chat(session_by_option, "call-option", "8111111111", "I need an ENT specialist", "en")
    option_result = handle_chat(session_by_option, "call-option", "8111111111", "first option", "en")
    assert option_result.next_state == ConversationState.collect_name
    assert option_result.selected_slot is not None
    assert option_result.selected_slot.available_date.isoformat() == "2026-06-10"

    session_by_date = make_session()
    handle_chat(session_by_date, "call-date", "8111111112", "I need an ENT specialist", "en")
    date_result = handle_chat(session_by_date, "call-date", "8111111112", "June 12", "en")
    assert date_result.next_state == ConversationState.collect_name
    assert date_result.selected_slot is not None
    assert date_result.selected_slot.available_date.isoformat() == "2026-06-12"

    session_by_time = make_session()
    handle_chat(session_by_time, "call-time", "8111111113", "I need an ENT specialist", "en")
    time_result = handle_chat(session_by_time, "call-time", "8111111113", "3 pm", "en")
    assert time_result.next_state == ConversationState.collect_name
    assert time_result.selected_slot is not None


def test_availability_tokens_increment_and_capacity_blocks(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    availability = session.exec(select(DoctorAvailability)).first()
    availability.max_patients = 2
    session.add(availability)
    session.commit()

    first_user = User(phone="7000000001")
    second_user = User(phone="7000000002")
    third_user = User(phone="7000000003")
    session.add(first_user)
    session.add(second_user)
    session.add(third_user)
    session.commit()
    session.refresh(first_user)
    session.refresh(second_user)
    session.refresh(third_user)

    first = book_appointment(session, first_user.id, availability.doctor_id, availability.id)
    second = book_appointment(session, second_user.id, availability.doctor_id, availability.id)

    assert first.token_number == 1
    assert second.token_number == 2

    try:
        book_appointment(session, third_user.id, availability.doctor_id, availability.id)
    except Exception as exc:
        assert "fully booked" in str(exc).lower()
    else:
        raise AssertionError("Expected full availability to reject the booking")


def test_unclear_reply_preserves_active_booking_state(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    handle_chat(session, "call-fallback", "8777777777", "I need a skin doctor appointment", "en")
    handle_chat(session, "call-fallback", "8777777777", "Tomorrow 10 am", "en")
    result = handle_chat(session, "call-fallback", "8777777777", "12345", "en")

    assert result.next_state == ConversationState.collect_name
    assert result.action == "fallback"
    assert "name" in result.reply.lower()


def test_voice_transcript_style_detail_collection(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    handle_chat(session, "call-voice", "8666666666", "I am having chest pain", "en")
    handle_chat(session, "call-voice", "8666666666", "I want tomorrow 10:00 AM", "en")
    name = handle_chat(session, "call-voice", "8666666666", "श्रीकांत पटनायक", "hi")
    name_confirm = handle_chat(session, "call-voice", "8666666666", "हाँ", "hi")
    gender = handle_chat(session, "call-voice", "8666666666", "M A L E", "en")
    age = handle_chat(session, "call-voice", "8666666666", "Twenty-three years", "en")
    phone = handle_chat(session, "call-voice", "8666666666", "eight two nine three zero one four seven eight seven", "en")

    assert name.next_state == ConversationState.confirm_name
    assert name_confirm.next_state == ConversationState.collect_gender
    assert gender.next_state == ConversationState.collect_age
    assert age.next_state == ConversationState.collect_phone
    assert phone.next_state == ConversationState.review_booking
    assert phone.booking_review is not None
    assert phone.booking_review.name == "Shreekaant Patanaayak"
    assert phone.booking_review.gender == "male"
    assert phone.booking_review.age == 23
    assert phone.booking_review.phone == "8293014787"


def test_voice_agent_polishes_safe_collection_prompt(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    monkeypatch.setenv("VOICE_AGENT_POLISH_REPLIES", "true")
    get_settings.cache_clear()
    session = make_session()

    def fake_polish(*_args, **_kwargs):
        return LlmResult(text="Sure, may I have the patient's full name?", status="llm_generated")

    monkeypatch.setattr("app.services.llm_service.polish_voice_reply", fake_polish)

    handle_chat(session, "call-polish", "8555555555", "I am having chest pain", "en")
    result = handle_chat(session, "call-polish", "8555555555", "Tomorrow 10 am", "en")

    assert result.next_state == ConversationState.collect_name
    assert result.reply == "Sure, may I have the patient's full name?"


def test_name_can_be_rejected_and_recollected(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    handle_chat(session, "call-name-fix", "8333333333", "I have chest pain", "en")
    handle_chat(session, "call-name-fix", "8333333333", "Tomorrow 10 am", "en")
    first_name = handle_chat(session, "call-name-fix", "8333333333", "Adam", "en")
    rejected = handle_chat(session, "call-name-fix", "8333333333", "no", "en")
    corrected = handle_chat(session, "call-name-fix", "8333333333", "Rahul Sharma", "en")

    assert first_name.next_state == ConversationState.confirm_name
    assert rejected.next_state == ConversationState.collect_name
    assert rejected.slot_options is not None
    assert corrected.next_state == ConversationState.confirm_name
    assert "Rahul Sharma" in corrected.reply


def test_review_rejection_clears_details_but_keeps_slot_options(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    session = make_session()

    handle_chat(session, "call-review-fix", "8222222222", "I have chest pain", "en")
    handle_chat(session, "call-review-fix", "8222222222", "Tomorrow 10 am", "en")
    handle_chat(session, "call-review-fix", "8222222222", "Adam", "en")
    handle_chat(session, "call-review-fix", "8222222222", "yes", "en")
    handle_chat(session, "call-review-fix", "8222222222", "male", "en")
    handle_chat(session, "call-review-fix", "8222222222", "42", "en")
    handle_chat(session, "call-review-fix", "8222222222", "8293014787", "en")
    rejected = handle_chat(session, "call-review-fix", "8222222222", "no", "en")

    assert rejected.next_state == ConversationState.collect_name
    assert rejected.slot_options is not None
    assert rejected.booking_review is None


def test_voice_agent_does_not_polish_slot_lists(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    monkeypatch.setenv("VOICE_AGENT_POLISH_REPLIES", "true")
    get_settings.cache_clear()
    session = make_session()

    def fake_polish(*_args, **_kwargs):
        return LlmResult(text="Changed unsafe slot list", status="llm_generated")

    monkeypatch.setattr("app.services.llm_service.polish_voice_reply", fake_polish)

    result = handle_chat(session, "call-no-polish", "8444444444", "I am having chest pain", "en")

    assert result.next_state == ConversationState.show_slots
    assert result.slot_options is not None
    assert "on screen" in result.reply
    assert result.reply != "Changed unsafe slot list"
