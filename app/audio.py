import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
from urllib import error, request

from app.config import get_settings


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class SpeechResult:
    audio_url: str | None
    status: str
    detail: str


class SpeechToTextService:
    def __init__(self) -> None:
        self._model = None

    def transcribe(self, audio_bytes: bytes, filename: str | None = None) -> TranscriptionResult:
        settings = get_settings()
        provider = settings.stt_provider.lower().strip()
        if provider == "groq":
            if not settings.groq_api_key:
                return TranscriptionResult(
                    text="",
                    language="unknown",
                    status="stt_credentials_missing",
                    detail="Missing GROQ_API_KEY.",
                )
            return self._transcribe_groq(audio_bytes, filename, settings.groq_api_key, settings.groq_stt_model)

        if provider == "elevenlabs":
            if not settings.elevenlabs_api_key:
                return TranscriptionResult(
                    text="",
                    language="unknown",
                    status="stt_credentials_missing",
                    detail="Missing ELEVENLABS_API_KEY.",
                )
            return self._transcribe_elevenlabs(
                audio_bytes=audio_bytes,
                filename=filename,
                api_key=settings.elevenlabs_api_key,
                model=settings.elevenlabs_stt_model,
                language=settings.stt_language,
            )

        if provider != "faster_whisper":
            return TranscriptionResult(
                text="",
                language="unknown",
                status="stt_not_configured",
                detail="Set STT_PROVIDER=faster_whisper, STT_PROVIDER=groq, or STT_PROVIDER=elevenlabs to enable transcription.",
            )

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            return TranscriptionResult(
                text="",
                language="unknown",
                status="stt_dependency_missing",
                detail="Install faster-whisper to enable STT.",
            )

        if self._model is None:
            self._model = WhisperModel(
                settings.stt_model_size,
                device=settings.stt_device,
                compute_type=settings.stt_compute_type,
            )

        suffix = Path(filename or "audio.wav").suffix or ".wav"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = Path(temp_audio.name)

        try:
            language = settings.stt_language or None
            segments, info = self._model.transcribe(str(temp_path), language=language)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            detected_language = getattr(info, "language", None) or settings.stt_language or "unknown"
            return TranscriptionResult(
                text=text,
                language=detected_language,
                status="transcribed" if text else "no_speech_detected",
            )
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _transcribe_groq(
        audio_bytes: bytes,
        filename: str | None,
        api_key: str,
        model: str,
    ) -> TranscriptionResult:
        file_name = filename or "audio.wav"
        boundary = f"----VaaniAIGroqBoundary{uuid4().hex}"
        payload = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="model"\r\n\r\n'
            f"{model}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + audio_bytes + f"\r\n--{boundary}--\r\n".encode()

        groq_request = request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            with request.urlopen(groq_request, timeout=20) as response:
                response_body = json.loads(response.read().decode())
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return TranscriptionResult(text="", language="unknown", status="stt_failed", detail=detail)
        except OSError as exc:
            return TranscriptionResult(text="", language="unknown", status="stt_failed", detail=str(exc))

        text = (response_body.get("text") or "").strip()
        language = (response_body.get("language") or "unknown").strip() or "unknown"
        return TranscriptionResult(
            text=text,
            language=language,
            status="transcribed" if text else "no_speech_detected",
        )

    @staticmethod
    def _transcribe_elevenlabs(
        audio_bytes: bytes,
        filename: str | None,
        api_key: str,
        model: str,
        language: str | None,
    ) -> TranscriptionResult:
        fields = {"model_id": model}
        if language:
            fields["language_code"] = language
        payload, content_type = _build_multipart_payload(
            fields=fields,
            file_field="file",
            filename=filename or "audio.webm",
            file_bytes=audio_bytes,
        )
        elevenlabs_request = request.Request(
            "https://api.elevenlabs.io/v1/speech-to-text",
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": content_type,
            },
            method="POST",
        )

        try:
            with request.urlopen(elevenlabs_request, timeout=25) as response:
                response_body = json.loads(response.read().decode())
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return TranscriptionResult(text="", language="unknown", status="stt_failed", detail=detail)
        except (OSError, json.JSONDecodeError) as exc:
            return TranscriptionResult(text="", language="unknown", status="stt_failed", detail=str(exc))

        text = (response_body.get("text") or "").strip()
        detected_language = (response_body.get("language_code") or response_body.get("language") or "unknown").strip()
        return TranscriptionResult(
            text=text,
            language=detected_language or "unknown",
            status="transcribed" if text else "no_speech_detected",
        )


class TextToSpeechService:
    def __init__(self) -> None:
        self._model = None

    def synthesize(self, text: str, language: str) -> SpeechResult:
        settings = get_settings()
        if settings.tts_provider.lower() == "elevenlabs":
            if not settings.elevenlabs_api_key:
                return SpeechResult(
                    audio_url=None,
                    status="tts_credentials_missing",
                    detail="Missing ELEVENLABS_API_KEY.",
                )
            if not settings.elevenlabs_voice_id:
                return SpeechResult(
                    audio_url=None,
                    status="tts_voice_missing",
                    detail="Set ELEVENLABS_VOICE_ID to the assistant voice ID.",
                )
            return self._synthesize_elevenlabs(
                text=text,
                language=language,
                api_key=settings.elevenlabs_api_key,
                voice_id=settings.elevenlabs_voice_id,
                fallback_voice_id=settings.elevenlabs_fallback_voice_id,
                model=settings.elevenlabs_tts_model,
                output_format=settings.elevenlabs_output_format,
                output_dir=settings.generated_audio_dir,
                public_base_url=settings.public_base_url,
            )

        if settings.tts_provider.lower() != "xtts":
            return SpeechResult(
                audio_url=None,
                status="tts_not_configured",
                detail="Set TTS_PROVIDER=xtts or TTS_PROVIDER=elevenlabs to enable speech generation.",
            )

        if not settings.tts_speaker_wav:
            return SpeechResult(
                audio_url=None,
                status="tts_speaker_missing",
                detail="Set TTS_SPEAKER_WAV to a short reference voice WAV file.",
            )

        try:
            from TTS.api import TTS
        except ImportError:
            return SpeechResult(
                audio_url=None,
                status="tts_dependency_missing",
                detail="Install coqui TTS to enable XTTS.",
            )

        if self._model is None:
            self._model = TTS(settings.tts_model_name)

        output_dir = Path(settings.generated_audio_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{uuid4().hex}.wav"
        xtts_language = self._normalize_language(language)
        self._model.tts_to_file(
            text=text,
            speaker_wav=settings.tts_speaker_wav,
            language=xtts_language,
            file_path=str(output_path),
        )
        return SpeechResult(
            audio_url=f"/audio/{output_path.name}",
            status="synthesized",
            detail="Speech generated with XTTS.",
        )

    @staticmethod
    def _normalize_language(language: str) -> str:
        normalized = (language or "").lower().strip().replace("_", "-")
        if normalized in {"hi", "hin", "hindi", "hi-in", "hinglish"}:
            return "hi"
        return "en"

    @staticmethod
    def _synthesize_elevenlabs(
        text: str,
        language: str,
        api_key: str,
        voice_id: str,
        fallback_voice_id: str,
        model: str,
        output_format: str,
        output_dir: str,
        public_base_url: str,
    ) -> SpeechResult:
        language_code = TextToSpeechService._normalize_language(language)
        voice_id = voice_id.strip()
        fallback_voice_id = fallback_voice_id.strip()
        payload = json.dumps(
            {
                "text": text,
                "model_id": model,
                "language_code": language_code,
                "voice_settings": {
                    "stability": 0.35,
                    "similarity_boost": 0.8,
                    "style": 0.35,
                    "use_speaker_boost": True,
                },
            }
        ).encode()
        audio_bytes = TextToSpeechService._request_elevenlabs_tts(
            api_key=api_key,
            voice_id=voice_id,
            output_format=output_format,
            payload=payload,
        )
        if isinstance(audio_bytes, SpeechResult):
            if (
                fallback_voice_id
                and fallback_voice_id != voice_id
                and "paid_plan_required" in audio_bytes.detail
            ):
                fallback_audio = TextToSpeechService._request_elevenlabs_tts(
                    api_key=api_key,
                    voice_id=fallback_voice_id,
                    output_format=output_format,
                    payload=payload,
                )
                if not isinstance(fallback_audio, SpeechResult):
                    audio_bytes = fallback_audio
                else:
                    return fallback_audio
            else:
                return audio_bytes

        output_path = _write_generated_audio(audio_bytes, output_dir, output_format)
        return SpeechResult(
            audio_url=f"/audio/{output_path.name}",
            status="synthesized",
            detail="Speech generated with ElevenLabs.",
        )

    @staticmethod
    def _request_elevenlabs_tts(
        api_key: str,
        voice_id: str,
        output_format: str,
        payload: bytes,
    ) -> bytes | SpeechResult:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={output_format}"
        elevenlabs_request = request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )

        try:
            with request.urlopen(elevenlabs_request, timeout=25) as response:
                return response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return SpeechResult(audio_url=None, status="tts_failed", detail=detail)
        except OSError as exc:
            return SpeechResult(audio_url=None, status="tts_failed", detail=str(exc))


class SpeechToSpeechService:
    def convert(self, audio_bytes: bytes, filename: str | None = None) -> SpeechResult:
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            return SpeechResult(
                audio_url=None,
                status="sts_credentials_missing",
                detail="Missing ELEVENLABS_API_KEY.",
            )
        if not settings.elevenlabs_voice_id:
            return SpeechResult(
                audio_url=None,
                status="sts_voice_missing",
                detail="Set ELEVENLABS_VOICE_ID to the target voice ID.",
            )

        payload, content_type = _build_multipart_payload(
            fields={"model_id": settings.elevenlabs_sts_model},
            file_field="audio",
            filename=filename or "audio.webm",
            file_bytes=audio_bytes,
        )
        url = (
            f"https://api.elevenlabs.io/v1/speech-to-speech/{settings.elevenlabs_voice_id}"
            f"?output_format={settings.elevenlabs_output_format}"
        )
        elevenlabs_request = request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": content_type,
                "Accept": "audio/mpeg",
            },
            method="POST",
        )

        try:
            with request.urlopen(elevenlabs_request, timeout=25) as response:
                converted_audio = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            return SpeechResult(audio_url=None, status="sts_failed", detail=detail)
        except OSError as exc:
            return SpeechResult(audio_url=None, status="sts_failed", detail=str(exc))

        output_path = _write_generated_audio(
            converted_audio,
            settings.generated_audio_dir,
            settings.elevenlabs_output_format,
        )
        return SpeechResult(
            audio_url=f"/audio/{output_path.name}",
            status="converted",
            detail="Speech converted with ElevenLabs.",
        )


def _build_multipart_payload(
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    boundary = f"----VaaniAIElevenLabsBoundary{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )

    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode()
    )
    chunks.append(file_bytes)
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _write_generated_audio(audio_bytes: bytes, output_dir: str, output_format: str) -> Path:
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    extension = ".mp3"
    if output_format.startswith("wav_"):
        extension = ".wav"
    elif output_format.startswith("pcm_"):
        extension = ".pcm"
    output_path = output_directory / f"{uuid4().hex}{extension}"
    output_path.write_bytes(audio_bytes)
    return output_path


stt_service = SpeechToTextService()
tts_service = TextToSpeechService()
sts_service = SpeechToSpeechService()
