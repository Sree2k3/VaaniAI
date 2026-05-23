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
