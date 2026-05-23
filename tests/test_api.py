from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.audio import TranscriptionResult
from app.config import get_settings
from app.database import get_session
from app.main import app
from app.services import seed_demo_data


def use_in_memory_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with Session(engine) as session:
        seed_demo_data(session)


def test_root_and_dashboard_contracts() -> None:
    with TestClient(app) as client:
        assert client.get("/").json()["name"] == "VaaniAI Backend"
        assert client.get("/app").status_code == 200
        assert client.post("/demo/seed").json() == {"status": "seeded"}

        metrics = client.get("/dashboard/metrics").json()
        assert "total_calls_today" in metrics
        assert "language_distribution" in metrics


def test_tts_placeholder_contract(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "stub")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post("/tts", json={"text": "Hello", "language": "en"})

    assert response.status_code == 200
    assert response.json()["status"] in {
        "tts_not_configured",
        "tts_dependency_missing",
        "tts_speaker_missing",
        "tts_credentials_missing",
        "tts_voice_missing",
    }


def test_chat_booking_logs_sms_attempt(monkeypatch) -> None:
    call_id = f"api-sms-flow-{uuid4().hex}"
    monkeypatch.setenv("SMS_PROVIDER", "stub")
    get_settings.cache_clear()
    use_in_memory_database()
    try:
        with TestClient(app) as client:
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "I need a dentist appointment"},
            )
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "Tomorrow 10 am"},
            )
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "My name is Test Patient"},
            )
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "yes"},
            )
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "male"},
            )
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "30"},
            )
            client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "9876543210"},
            )
            response = client.post(
                "/chat",
                json={"call_id": call_id, "user_phone": call_id, "message": "Confirm"},
            )
            notifications = client.get("/notifications").json()

        assert response.status_code == 200
        assert response.json()["notification_status"] == "sms_not_configured"
        assert notifications[0]["appointment_id"] == response.json()["appointment_id"]
    finally:
        app.dependency_overrides.clear()


def test_transcribe_can_store_user_transcript(monkeypatch) -> None:
    call_id = f"phase-4-store-{uuid4().hex}"

    def fake_transcribe(audio_bytes: bytes, filename: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(text="I need a dentist appointment", language="en", status="transcribed")

    monkeypatch.setattr("app.main.stt_service.transcribe", fake_transcribe)

    with TestClient(app) as client:
        response = client.post(
            "/transcribe",
            params={"call_id": call_id, "user_phone": call_id},
            files={"audio": ("request.wav", b"audio-bytes", "audio/wav")},
        )
        transcripts = client.get("/transcripts", params={"call_id": call_id}).json()

    assert response.status_code == 200
    assert response.json()["text"] == "I need a dentist appointment"
    assert response.json()["chat"] is None
    assert transcripts[0]["turns"][0]["text"] == "I need a dentist appointment"


def test_transcribe_can_feed_chat(monkeypatch) -> None:
    call_id = f"phase-4-chat-{uuid4().hex}"

    def fake_transcribe(audio_bytes: bytes, filename: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(text="I need a skin doctor appointment", language="en", status="transcribed")

    monkeypatch.setattr("app.main.stt_service.transcribe", fake_transcribe)

    with TestClient(app) as client:
        client.post("/demo/seed")
        response = client.post(
            "/transcribe",
            params={"call_id": call_id, "user_phone": call_id, "auto_chat": True},
            files={"audio": ("request.wav", b"audio-bytes", "audio/wav")},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "transcribed"
    assert payload["chat"]["next_state"] == "show_slots"
    assert payload["chat"]["action"] == "show_slots"


def test_session_start_and_reset() -> None:
    use_in_memory_database()
    try:
        with TestClient(app) as client:
            start = client.post(
                "/session/start",
                json={"call_id": "web-session-1", "user_phone": "9000000000", "language": "en"},
            )
            assert start.status_code == 200
            assert start.json()["state"] == "idle"

            client.post(
                "/chat",
                json={"call_id": "web-session-1", "user_phone": "9000000000", "message": "I need a dentist appointment"},
            )
            state = client.get("/session/web-session-1").json()
            assert state["state"] == "show_slots"
            assert state["slot_options"] is not None

            reset = client.post("/session/web-session-1/reset")
            assert reset.status_code == 200
            assert reset.json()["state"] == "idle"
            assert reset.json()["selected_specialization"] is None
    finally:
        app.dependency_overrides.clear()


def test_session_start_fresh_resets_old_web_state() -> None:
    use_in_memory_database()
    try:
        with TestClient(app) as client:
            client.post(
                "/chat",
                json={"call_id": "web-refresh-test", "user_phone": "9000000002", "message": "I need a dentist appointment"},
            )
            stale = client.get("/session/web-refresh-test").json()
            assert stale["state"] == "show_slots"

            fresh = client.post(
                "/session/start",
                json={"call_id": "web-refresh-test", "user_phone": "9000000002", "language": "en", "fresh": True},
            )
            assert fresh.status_code == 200
            assert fresh.json()["state"] == "idle"
            assert fresh.json()["slot_options"] is None
            assert fresh.json()["selected_specialization"] is None
    finally:
        app.dependency_overrides.clear()


def test_doctors_include_symptoms_column() -> None:
    use_in_memory_database()
    try:
        with TestClient(app) as client:
            doctors = client.get("/doctors").json()

        cardiologist = next(doctor for doctor in doctors if doctor["specialization"] == "cardiologist")
        specializations = {doctor["specialization"] for doctor in doctors}
        assert "chest pain" in cardiologist["symptoms"]
        assert {"neurologist", "orthopedic", "ophthalmologist", "pulmonologist"}.issubset(specializations)
    finally:
        app.dependency_overrides.clear()


def test_voice_turn_orchestration(monkeypatch) -> None:
    call_id = f"voice-turn-{uuid4().hex}"
    use_in_memory_database()

    def fake_transcribe(audio_bytes: bytes, filename: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(text="I need a skin doctor appointment", language="en", status="transcribed")

    monkeypatch.setattr("app.main.stt_service.transcribe", fake_transcribe)

    class _TtsResult:
        def __init__(self):
            self.audio_url = "http://127.0.0.1:8000/audio/demo.wav"
            self.status = "synthesized"
            self.detail = "Speech generated with XTTS."

    monkeypatch.setattr("app.main.tts_service.synthesize", lambda *_args, **_kwargs: _TtsResult())

    try:
        with TestClient(app) as client:
            response = client.post(
                "/voice/turn",
                params={"call_id": call_id, "user_phone": "9111111111", "synthesize_reply": True},
                files={"audio": ("request.wav", b"audio-bytes", "audio/wav")},
            )
        payload = response.json()
        assert response.status_code == 200
        assert payload["stt_status"] == "transcribed"
        assert payload["chat"]["next_state"] == "show_slots"
        assert payload["tts"]["status"] == "synthesized"
    finally:
        app.dependency_overrides.clear()


def test_audio_upload_rejects_unsupported_content_type() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/transcribe",
            files={"audio": ("request.txt", b"not-audio", "text/plain")},
        )

    assert response.status_code == 415
    assert "Unsupported audio content type" in response.json()["detail"]


def test_audio_upload_allows_browser_webm_codec_content_type(monkeypatch) -> None:
    def fake_transcribe(audio_bytes: bytes, filename: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(text="hello", language="en", status="transcribed")

    monkeypatch.setattr("app.main.stt_service.transcribe", fake_transcribe)

    with TestClient(app) as client:
        response = client.post(
            "/transcribe",
            files={"audio": ("request.webm", b"audio-bytes", "audio/webm;codecs=opus")},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "transcribed"


def test_api_key_is_required_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "local-secret")
    get_settings.cache_clear()
    use_in_memory_database()
    try:
        with TestClient(app) as client:
            missing = client.post(
                "/chat",
                json={"call_id": "protected-1", "user_phone": "9000000001", "message": "I need a dentist appointment"},
            )
            allowed = client.post(
                "/chat",
                headers={"X-API-Key": "local-secret"},
                json={"call_id": "protected-1", "user_phone": "9000000001", "message": "I need a dentist appointment"},
            )

        assert missing.status_code == 401
        assert allowed.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
