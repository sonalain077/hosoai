from typing import Any

import pytest
from fastapi.testclient import TestClient

from hosoai.llm import FakeLLMClient
from hosoai.main import app, get_llm
from tests.conftest import FIXTURES

MATCH = FIXTURES / "match"
client = TestClient(app)


def _ask(name: str, query: str) -> dict[str, Any]:
    app.dependency_overrides[get_llm] = lambda: FakeLLMClient(MATCH / f"{name}.json")
    try:
        resp = client.post("/ask", json={"query": query})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    data: dict[str, Any] = resp.json()
    return data


def test_single_match_returns_sourced_candidate() -> None:
    body = _ask("passport", "Tôi cần làm hộ chiếu mới")
    assert body["status"] == "matched"
    [c] = body["candidates"]
    assert c["slug"] == "passport"
    assert ".gov.vn" in c["source"]["url"]


def test_several_matches_are_ambiguous_and_tolerate_chatty_reply() -> None:
    body = _ask("id-card-ambiguous", "I lost my ID card")
    assert body["status"] == "ambiguous"
    assert [c["slug"] for c in body["candidates"]] == ["id-card-reissue", "id-card-exchange"]
    assert all(c["source"]["url"] for c in body["candidates"])


@pytest.mark.parametrize("fixture", ["none", "invented", "not-json"])
def test_no_official_match_says_not_found(fixture: str) -> None:
    body = _ask(fixture, "Tôi muốn xin giấy phép câu cá")
    assert body["status"] == "not_found"
    assert body["candidates"] == []
    assert "không tìm thấy" in body["message"]


def test_prompt_lists_only_known_procedures_and_the_query() -> None:
    fake = FakeLLMClient(MATCH / "passport.json")
    app.dependency_overrides[get_llm] = lambda: fake
    try:
        client.post("/ask", json={"query": "hộ chiếu"})
    finally:
        app.dependency_overrides.clear()
    [messages] = fake.calls
    prompt = messages[-1].content
    assert "passport |" in prompt and "hộ chiếu" in prompt


def test_empty_query_rejected() -> None:
    fake = FakeLLMClient(MATCH / "passport.json")
    app.dependency_overrides[get_llm] = lambda: fake
    try:
        assert client.post("/ask", json={"query": ""}).status_code == 422
    finally:
        app.dependency_overrides.clear()
    assert fake.calls == []
