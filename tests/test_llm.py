import json

from app.config import get_settings
from app.llm import LlmService


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps({"choices": [{"message": {"content": "Hello from Vaani."}}]}).encode()


def test_openrouter_temperature_is_sent_from_settings(monkeypatch) -> None:
    captured_payload = {}

    def fake_urlopen(openrouter_request, timeout=0):
        nonlocal captured_payload
        captured_payload = json.loads(openrouter_request.data.decode())
        return _FakeResponse()

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "demo-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("OPENROUTER_TEMPERATURE", "0.65")
    monkeypatch.setattr("app.llm.request.urlopen", fake_urlopen)
    get_settings.cache_clear()

    result = LlmService().generate_reply("hello", "clinic context")

    assert result.status == "llm_generated"
    assert captured_payload["model"] == "openai/gpt-oss-120b"
    assert captured_payload["temperature"] == 0.65


def test_openrouter_temperature_is_clamped(monkeypatch) -> None:
    captured_payload = {}

    def fake_urlopen(openrouter_request, timeout=0):
        nonlocal captured_payload
        captured_payload = json.loads(openrouter_request.data.decode())
        return _FakeResponse()

    monkeypatch.setattr("app.llm.request.urlopen", fake_urlopen)

    result = LlmService._send_openrouter_request(
        api_key="demo-key",
        model="demo-model",
        prompt="hello",
        temperature=8,
    )

    assert result.status == "llm_generated"
    assert captured_payload["temperature"] == 2.0
