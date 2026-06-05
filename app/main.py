from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, text

from app.audio import stt_service, sts_service, tts_service
from app.config import get_settings
from app.database import engine, get_session, init_db
from app.models import Doctor
from app.schemas import (
    BookingRequest,
    BookingResponse,
    ChatRequest,
    ChatResponse,
    DashboardMetrics,
    DoctorRead,
    HealthResponse,
    NotificationRead,
    RecentBooking,
    SessionStartRequest,
    SessionStateResponse,
    SmsTestRequest,
    SmsTestResponse,
    SlotRead,
    TranscriptRead,
    TTSRequest,
    TTSResponse,
    TranscriptionResponse,
    VoiceTurnResponse,
)
from app.security import rate_limit, read_validated_audio, require_api_key
from app.services import (
    book_appointment,
    get_dashboard_metrics,
    get_session_state,
    handle_chat,
    list_available_slots,
    list_doctors,
    list_notifications,
    list_recent_bookings,
    list_transcripts,
    record_user_transcript,
    reset_session,
    reset_demo_database,
    reset_test_bookings,
    seed_demo_data,
    send_booking_confirmation,
    start_or_resume_session,
)
from app.messaging import sms_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if get_settings().demo_mode:
        with Session(engine) as session:
            seed_demo_data(session)
    yield


app = FastAPI(title="VaaniAI Backend", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.mount("/audio", StaticFiles(directory=settings.generated_audio_dir, check_dir=False), name="audio")
app.mount("/static", StaticFiles(directory="frontend", check_dir=False), name="static")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "VaaniAI Backend",
        "app": "/app",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/app", include_in_schema=False)
def web_app() -> FileResponse:
    index_path = Path("frontend/index.html")
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend is not available")
    return FileResponse(
        index_path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@app.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)) -> HealthResponse:
    session.exec(text("SELECT 1"))
    return HealthResponse(status="ok", database="ok")


@app.get("/diagnostics/config")
def diagnostics_config() -> dict[str, object]:
    runtime_settings = get_settings()
    generated_audio_dir = Path(runtime_settings.generated_audio_dir)
    stt_provider = runtime_settings.stt_provider.lower().strip()
    tts_provider = runtime_settings.tts_provider.lower().strip()
    return {
        "app": runtime_settings.app_name,
        "demo_mode": runtime_settings.demo_mode,
        "database": "configured" if runtime_settings.database_url else "missing",
        "public_base_url": runtime_settings.public_base_url,
        "stt_provider": runtime_settings.stt_provider,
        "stt_ready": (
            (stt_provider not in {"elevenlabs", "cartesia", "casteria"})
            or (stt_provider == "elevenlabs" and bool(runtime_settings.elevenlabs_api_key))
            or (stt_provider in {"cartesia", "casteria"} and bool(runtime_settings.cartesia_api_key))
        ),
        "tts_provider": runtime_settings.tts_provider,
        "tts_ready": (
            (tts_provider not in {"elevenlabs", "cartesia", "casteria"})
            or (
                tts_provider == "elevenlabs"
                and bool(runtime_settings.elevenlabs_api_key and runtime_settings.elevenlabs_voice_id)
            )
            or (
                tts_provider in {"cartesia", "casteria"}
                and bool(runtime_settings.cartesia_api_key and runtime_settings.cartesia_voice_id)
            )
        ),
        "elevenlabs_api_key_set": bool(runtime_settings.elevenlabs_api_key),
        "elevenlabs_voice_id_set": bool(runtime_settings.elevenlabs_voice_id),
        "cartesia_api_key_set": bool(runtime_settings.cartesia_api_key),
        "cartesia_voice_id_set": bool(runtime_settings.cartesia_voice_id),
        "llm_provider": runtime_settings.llm_provider,
        "openrouter_model": runtime_settings.openrouter_model,
        "openrouter_temperature": runtime_settings.openrouter_temperature,
        "openrouter_key_set": bool(runtime_settings.openrouter_api_key),
        "sms_provider": runtime_settings.sms_provider,
        "fast2sms_key_set": bool(runtime_settings.fast2sms_api_key),
        "calendar_provider": runtime_settings.calendar_provider,
        "generated_audio_dir": str(generated_audio_dir),
    }


@app.post("/demo/seed")
def seed_demo(
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    seed_demo_data(session)
    return {"status": "seeded"}


@app.post("/demo/reset-bookings")
def reset_bookings(
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    reset_test_bookings(session)
    return {"status": "reset"}


@app.post("/demo/reset-db")
def reset_db(
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    reset_demo_database(session)
    return {"status": "database_reset"}


@app.get("/doctors", response_model=list[DoctorRead])
def doctors(session: Session = Depends(get_session)) -> list[Doctor]:
    return list_doctors(session)


@app.get("/available-slots", response_model=list[SlotRead])
def available_slots(specialization: str | None = None, session: Session = Depends(get_session)) -> list[SlotRead]:
    return list_available_slots(session, specialization)


@app.post("/book-appointment", response_model=BookingResponse)
def create_booking(
    request: BookingRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> BookingResponse:
    appointment = book_appointment(session, request.user_id, request.doctor_id, request.slot_id)
    notification = send_booking_confirmation(session, appointment)
    return BookingResponse(
        appointment_id=appointment.id,
        status=appointment.status.value,
        notification_status=notification.status,
        token_number=appointment.token_number,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    return handle_chat(session, request.call_id, request.user_phone, request.message, request.language)


@app.post("/session/start", response_model=SessionStateResponse)
def session_start(
    request: SessionStartRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> SessionStateResponse:
    return start_or_resume_session(session, request.call_id, request.user_phone, request.language, request.fresh)


@app.get("/session/{call_id}", response_model=SessionStateResponse)
def session_state(call_id: str, user_phone: str = "demo", language: str = "en", session: Session = Depends(get_session)) -> SessionStateResponse:
    return get_session_state(session, call_id, user_phone, language)


@app.post("/session/{call_id}/reset", response_model=SessionStateResponse)
def session_reset(
    call_id: str,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> SessionStateResponse:
    return reset_session(session, call_id)


@app.get("/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(session: Session = Depends(get_session)) -> dict:
    return get_dashboard_metrics(session)


@app.get("/dashboard/recent-bookings", response_model=list[RecentBooking])
def recent_bookings(limit: int = 10, session: Session = Depends(get_session)) -> list[dict]:
    return list_recent_bookings(session, limit)


@app.get("/transcripts", response_model=list[TranscriptRead])
def transcripts(call_id: str | None = None, limit: int = 10, session: Session = Depends(get_session)) -> list[dict]:
    return list_transcripts(session, call_id, limit)


@app.get("/notifications", response_model=list[NotificationRead])
def notifications(limit: int = 20, session: Session = Depends(get_session)) -> list:
    return list_notifications(session, limit)


@app.post("/sms/test", response_model=SmsTestResponse)
def test_sms(
    request: SmsTestRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
) -> SmsTestResponse:
    result = sms_service.send_sms(request.phone, request.message)
    print(
        f"sms_test status={result.status} provider_id={result.provider_message_id} detail={result.detail[:200]}",
        flush=True,
    )
    return SmsTestResponse(
        status=result.status,
        provider_message_id=result.provider_message_id,
        detail=result.detail,
    )


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(...),
    call_id: str = "",
    user_phone: str = "demo",
    language: str = "en",
    auto_chat: bool = False,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> TranscriptionResponse:
    audio_bytes = await read_validated_audio(audio)
    result = stt_service.transcribe(audio_bytes, audio.filename)
    transcript_language = result.language if result.language != "unknown" else language
    chat_response = None

    if result.text and call_id:
        if auto_chat:
            chat_response = handle_chat(session, call_id, user_phone, result.text, transcript_language)
        else:
            record_user_transcript(session, call_id, user_phone, result.text, transcript_language)

    return TranscriptionResponse(
        text=result.text,
        language=result.language,
        call_id=call_id,
        status=result.status,
        detail=result.detail,
        chat=chat_response,
    )


@app.post("/tts", response_model=TTSResponse)
def text_to_speech(
    request: TTSRequest,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
) -> TTSResponse:
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="text is required")
    result = tts_service.synthesize(request.text, request.language)
    print(
        f"tts status={result.status} audio={bool(result.audio_url)} detail={result.detail[:160]}",
        flush=True,
    )
    return TTSResponse(audio_url=result.audio_url, status=result.status, detail=result.detail)


@app.post("/speech-to-speech", response_model=TTSResponse)
async def speech_to_speech(
    audio: UploadFile = File(...),
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
) -> TTSResponse:
    audio_bytes = await read_validated_audio(audio)
    result = sts_service.convert(audio_bytes, audio.filename)
    return TTSResponse(audio_url=result.audio_url, status=result.status, detail=result.detail)


@app.post("/voice/turn", response_model=VoiceTurnResponse)
async def voice_turn(
    audio: UploadFile = File(...),
    call_id: str = "",
    user_phone: str = "demo",
    language: str = "en",
    synthesize_reply: bool = True,
    _: None = Depends(require_api_key),
    __: None = Depends(rate_limit),
    session: Session = Depends(get_session),
) -> VoiceTurnResponse:
    if not call_id:
        raise HTTPException(status_code=400, detail="call_id is required")

    audio_bytes = await read_validated_audio(audio)
    stt_result = stt_service.transcribe(audio_bytes, audio.filename)
    transcript_language = stt_result.language if stt_result.language != "unknown" else language
    chat_response = None
    tts_response = None

    if stt_result.text:
        chat_response = handle_chat(session, call_id, user_phone, stt_result.text, transcript_language)
        if synthesize_reply and chat_response.reply:
            tts_result = tts_service.synthesize(chat_response.reply, transcript_language)
            tts_response = TTSResponse(
                audio_url=tts_result.audio_url,
                status=tts_result.status,
                detail=tts_result.detail,
            )

    print(
        "voice_turn "
        f"call_id={call_id} "
        f"stt_status={stt_result.status} "
        f"stt_language={transcript_language} "
        f"text_present={bool(stt_result.text)} "
        f"chat_state={getattr(chat_response, 'next_state', None)} "
        f"tts_status={tts_response.status if tts_response else None} "
        f"stt_detail={stt_result.detail[:160]}",
        flush=True,
    )

    return VoiceTurnResponse(
        call_id=call_id,
        user_phone=user_phone,
        language=transcript_language,
        stt_text=stt_result.text,
        stt_status=stt_result.status,
        stt_detail=stt_result.detail,
        chat=chat_response,
        tts=tts_response,
    )
