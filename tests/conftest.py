import os

from app.config import get_settings


def pytest_runtest_setup() -> None:
    os.environ.setdefault("VOICE_AGENT_POLISH_REPLIES", "false")
    get_settings.cache_clear()
