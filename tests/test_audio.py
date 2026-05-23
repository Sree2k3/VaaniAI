from app.audio import SpeechResult, SpeechToTextService, TextToSpeechService, TranscriptionResult
from app.config import get_settings


def test_groq_stt_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()

    result = SpeechToTextService().transcribe(b"audio-bytes", "test.wav")

    assert result.status == "stt_credentials_missing"


def test_groq_stt_dispatch(monkeypatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "demo-key")
    monkeypatch.setenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
    get_settings.cache_clear()

    def fake_transcribe(*args, **kwargs):
        return TranscriptionResult(text="hello", language="en", status="transcribed")

    monkeypatch.setattr(SpeechToTextService, "_transcribe_groq", staticmethod(fake_transcribe))
    result = SpeechToTextService().transcribe(b"audio-bytes", "test.wav")

    assert result.status == "transcribed"
    assert result.text == "hello"


def test_elevenlabs_stt_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    get_settings.cache_clear()

    result = SpeechToTextService().transcribe(b"audio-bytes", "test.webm")

    assert result.status == "stt_credentials_missing"


def test_elevenlabs_stt_dispatch(monkeypatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "demo-key")
    monkeypatch.setenv("ELEVENLABS_STT_MODEL", "scribe_v2")
    get_settings.cache_clear()

    def fake_transcribe(*args, **kwargs):
        return TranscriptionResult(text="hello", language="en", status="transcribed")

    monkeypatch.setattr(SpeechToTextService, "_transcribe_elevenlabs", staticmethod(fake_transcribe))
    result = SpeechToTextService().transcribe(b"audio-bytes", "test.webm")

    assert result.status == "transcribed"
    assert result.text == "hello"


def test_elevenlabs_tts_requires_voice_id(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "demo-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "")
    get_settings.cache_clear()

    result = TextToSpeechService().synthesize("Hello", "en")

    assert result.status == "tts_voice_missing"


def test_elevenlabs_tts_dispatch(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "demo-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-id")
    get_settings.cache_clear()

    def fake_synthesize(*args, **kwargs):
        return SpeechResult(audio_url="http://test/audio.mp3", status="synthesized", detail="ok")

    monkeypatch.setattr(TextToSpeechService, "_synthesize_elevenlabs", staticmethod(fake_synthesize))
    result = TextToSpeechService().synthesize("Hello", "en")

    assert result.status == "synthesized"
    assert result.audio_url == "http://test/audio.mp3"


def test_elevenlabs_tts_allows_empty_fallback_voice(monkeypatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "demo-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-id")
    monkeypatch.setenv("ELEVENLABS_FALLBACK_VOICE_ID", "")
    get_settings.cache_clear()

    monkeypatch.setattr(
        TextToSpeechService,
        "_request_elevenlabs_tts",
        staticmethod(lambda *_args, **_kwargs: b"mp3-bytes"),
    )

    result = TextToSpeechService().synthesize("Hello", "en")

    assert result.status == "synthesized"
    assert result.audio_url is not None
