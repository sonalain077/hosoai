"""Profile: saved once, reused. Fake data only."""

from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from hosoai.agent.sessions import SessionStore, get_sessions
from hosoai.llm import FakeLLMClient
from hosoai.main import app, get_llm
from hosoai.profile.models import ProfileData, age_on, agent_facts
from tests.conftest import FIXTURES

client = TestClient(app)

FAKE: dict[str, Any] = {
    "full_name": "Nguyễn Văn Thử",
    "date_of_birth": "1990-05-20",
    "sex": "Nam",
    "id_number": "000000000000",
    "nationality": "Việt Nam",
    "current_address": "Số 1 Đường Giả, Phường Mẫu",
    "phone": "0900000000",
    "email": "test@example.com",
}


def test_profile_starts_empty_then_round_trips() -> None:
    assert client.get("/profile").json()["full_name"] is None
    saved = client.put("/profile", json=FAKE).json()
    assert saved["full_name"] == "Nguyễn Văn Thử"
    assert client.get("/profile").json()["date_of_birth"] == "1990-05-20"


def test_profile_rejects_bad_values() -> None:
    assert client.put("/profile", json={"email": "not-an-email"}).status_code == 422
    assert client.put("/profile", json={"sex": "X"}).status_code == 422


def test_age() -> None:
    assert age_on(date(1990, 5, 20), date(2026, 5, 19)) == 35
    assert age_on(date(1990, 5, 20), date(2026, 5, 20)) == 36


def test_agent_only_sees_age_and_nationality() -> None:
    facts = agent_facts(ProfileData.model_validate(FAKE), date(2026, 10, 27))
    assert facts == "age 36, nationality Việt Nam"
    assert agent_facts(ProfileData(), date(2026, 10, 27)) is None


def test_profile_facts_reach_the_agent_but_not_personal_details() -> None:
    client.put("/profile", json=FAKE)
    fake = FakeLLMClient(FIXTURES / "agent" / "no-questions.json")
    app.dependency_overrides[get_llm] = lambda: fake
    app.dependency_overrides[get_sessions] = SessionStore
    try:
        client.post("/agent", json={"query": "căn cước"})
    finally:
        app.dependency_overrides.pop(get_llm, None)
        app.dependency_overrides.pop(get_sessions, None)
    sent = "\n".join(m.content for call in fake.calls for m in call)
    assert "Answer -1: age" in sent and "nationality Việt Nam" in sent
    for secret in ("Nguyễn Văn Thử", "000000000000", "0900000000", "Đường Giả", "example.com"):
        assert secret not in sent


def test_storage_columns_match_api_fields() -> None:
    from hosoai.profile.models import Profile

    assert set(Profile.model_fields) - {"id"} == set(ProfileData.model_fields)
