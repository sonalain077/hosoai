import pytest
from fastapi.testclient import TestClient

from hosoai.llm import ChatMessage, FakeLLMClient, OpenAICompatibleClient
from hosoai.main import app
from tests.conftest import FIXTURES


def test_health() -> None:
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_fake_llm_replays_fixture() -> None:
    llm = FakeLLMClient(FIXTURES / "example.json")
    assert llm.chat([ChatMessage(role="user", content="hi")]) == "Xin chào"


def test_real_llm_blocked_in_tests() -> None:
    with pytest.raises(RuntimeError):
        OpenAICompatibleClient()
