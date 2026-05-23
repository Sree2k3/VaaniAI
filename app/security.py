from collections import defaultdict, deque
from time import monotonic

from fastapi import Header, HTTPException, Request, UploadFile

from app.config import get_settings


_request_log: dict[str, deque[float]] = defaultdict(deque)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Valid X-API-Key header is required")


def rate_limit(request: Request) -> None:
    settings = get_settings()
    if settings.rate_limit_per_minute <= 0:
        return

    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_id = forwarded_for.split(",", 1)[0].strip()
    if not client_id and request.client:
        client_id = request.client.host
    client_id = client_id or "unknown"

    now = monotonic()
    window_start = now - 60
    hits = _request_log[client_id]
    while hits and hits[0] < window_start:
        hits.popleft()
    if len(hits) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    hits.append(now)


async def read_validated_audio(audio: UploadFile) -> bytes:
    settings = get_settings()
    if not audio.filename:
        raise HTTPException(status_code=400, detail="audio file is required")

    allowed_types = {
        content_type.strip().lower()
        for content_type in settings.allowed_audio_content_types.split(",")
        if content_type.strip()
    }
    content_type = (audio.content_type or "application/octet-stream").lower()
    base_content_type = content_type.split(";", 1)[0].strip()
    if allowed_types and content_type not in allowed_types and base_content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported audio content type: {content_type}")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="audio file is empty")
    if len(audio_bytes) > settings.max_audio_upload_bytes:
        raise HTTPException(status_code=413, detail="audio file is too large")
    return audio_bytes
