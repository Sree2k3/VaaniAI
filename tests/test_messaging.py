from app.config import get_settings
from app.messaging import MessageResult, SmsService


def test_fast2sms_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "fast2sms")
    monkeypatch.setenv("FAST2SMS_API_KEY", "")
    get_settings.cache_clear()

    result = SmsService().send_sms("9999999999", "test")

    assert result.status == "sms_credentials_missing"
    assert "FAST2SMS_API_KEY" in result.detail


def test_fast2sms_provider_dispatch(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "fast2sms")
    monkeypatch.setenv("FAST2SMS_API_KEY", "demo-key")
    get_settings.cache_clear()

    def fake_send(*args, **kwargs):
        return MessageResult(status="sms_sent", provider_message_id="req-1", detail="SMS sent.")

    monkeypatch.setattr(SmsService, "_send_fast2sms_sms", staticmethod(fake_send))
    result = SmsService().send_sms("9999999999", "test")

    assert result.status == "sms_sent"
    assert result.provider_message_id == "req-1"


def test_fast2sms_rejects_invalid_recipient(monkeypatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "fast2sms")
    monkeypatch.setenv("FAST2SMS_API_KEY", "demo-key")
    get_settings.cache_clear()

    result = SmsService().send_sms("abc", "test")

    assert result.status == "sms_invalid_recipient"


def test_fast2sms_uses_form_encoded_post(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"return": true, "request_id": "req-123", "message": ["Message sent successfully"]}'

    def fake_urlopen(request_obj, timeout):
        captured["timeout"] = timeout
        captured["headers"] = dict(request_obj.header_items())
        captured["data"] = request_obj.data.decode()
        return FakeResponse()

    monkeypatch.setattr("app.messaging.request.urlopen", fake_urlopen)

    result = SmsService._send_fast2sms_sms(
        api_key="demo-key",
        route="q",
        language="english",
        sender_id=None,
        to_phone="+91 98765 43210",
        body="Appointment confirmed",
    )

    assert result.status == "sms_sent"
    assert result.provider_message_id == "req-123"
    assert captured["timeout"] == 10
    assert captured["headers"]["Authorization"] == "demo-key"
    assert captured["headers"]["Content-type"] == "application/x-www-form-urlencoded"
    assert "route=q" in captured["data"]
    assert "language=english" in captured["data"]
    assert "numbers=9876543210" in captured["data"]
    assert "message=Appointment+confirmed" in captured["data"]
