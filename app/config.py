from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VaaniAI Backend"
    database_url: str = "sqlite:///./vaaniai.db"
    demo_mode: bool = True
    public_base_url: str = "http://127.0.0.1:8000"
    api_key: str | None = None
    rate_limit_per_minute: int = 120
    max_audio_upload_bytes: int = 10 * 1024 * 1024
    allowed_audio_content_types: str = "audio/wav,audio/x-wav,audio/mpeg,audio/mp3,audio/mp4,audio/webm,audio/ogg,application/octet-stream"

    stt_provider: str = "stub"
    stt_model_size: str = "small"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_language: str | None = None

    tts_provider: str = "stub"
    tts_model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_speaker_wav: str | None = None
    generated_audio_dir: str = "generated_audio"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_fallback_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    elevenlabs_stt_model: str = "scribe_v2"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_sts_model: str = "eleven_multilingual_sts_v2"
    elevenlabs_output_format: str = "mp3_44100_128"

    gemini_api_key: str | None = None
    llm_provider: str = "stub"
    openrouter_api_key: str | None = None
    openrouter_model: str = "deepseek/deepseek-chat-v3-0324:free"
    voice_agent_polish_replies: bool = False
    vapi_api_key: str | None = None
    vapi_assistant_id: str | None = None
    groq_api_key: str | None = None
    groq_stt_model: str = "whisper-large-v3-turbo"

    sms_provider: str = "stub"
    clinic_name: str = "Pawani Medicals"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    fast2sms_api_key: str | None = None
    fast2sms_route: str = "q"
    fast2sms_language: str = "english"
    fast2sms_sender_id: str | None = None

    calendar_provider: str = "disabled"
    google_calendar_id: str | None = None
    google_calendar_credentials_file: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
