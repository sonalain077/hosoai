from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hosoai.agent.sessions import SessionStore, get_sessions
from hosoai.llm import FakeLLMClient
from hosoai.main import app, get_llm
from tests.conftest import FIXTURES

client = TestClient(app)
Json = dict[str, Any]


@pytest.fixture
def agent() -> Iterator[Callable[[str], FakeLLMClient]]:
    """Use one recorded conversation for the whole test, with a fresh session store."""

    def _use(name: str) -> FakeLLMClient:
        fake = FakeLLMClient(FIXTURES / "agent" / f"{name}.json")
        app.dependency_overrides[get_llm] = lambda: fake
        return fake

    sessions = SessionStore()
    app.dependency_overrides[get_sessions] = lambda: sessions
    yield _use
    app.dependency_overrides.pop(get_llm, None)
    app.dependency_overrides.pop(get_sessions, None)


def start(query: str) -> Json:
    r = client.post("/agent", json={"query": query})
    assert r.status_code == 200, r.text
    data: Json = r.json()
    return data


def reply(session_id: str, answer: str) -> Json:
    r = client.post(f"/agent/{session_id}", json={"answer": answer})
    assert r.status_code == 200, r.text
    data: Json = r.json()
    return data


def statuses(body: Json) -> dict[str, str]:
    return {d["id"]: d["status"] for d in body["dossier"]["documents"]}


def test_passport_conversation_builds_grounded_dossier(agent: Callable[..., Any]) -> None:
    agent("passport-two-questions")
    q1 = start("Tôi cần làm hộ chiếu")
    assert q1["type"] == "question"
    assert q1["question"]["number"] == 1
    # unknown document ids are dropped; the rest carry official text
    assert [d["id"] for d in q1["question"]["about"]] == ["d1", "d2"]
    assert "giấy khai sinh" in q1["question"]["about"][0]["name"]

    q2 = reply(q1["session_id"], "Đã đủ 14 tuổi")
    assert q2["type"] == "question" and q2["question"]["number"] == 2

    done = reply(q1["session_id"], "Chưa từng")
    assert done["type"] == "dossier"
    s = statuses(done)
    assert s["d1"] == "not_needed" and s["d3"] == "not_needed"
    assert s["d2"] == "unsure"  # "not_needed" with no answer cited is downgraded
    assert s["d5"] == "needed"
    assert "d42" not in s
    d1 = next(d for d in done["dossier"]["documents"] if d["id"] == "d1")
    assert d1["because"] == [
        {
            "number": 1,
            "question": "Người làm hộ chiếu đã đủ 14 tuổi chưa?",
            "answer": "Đã đủ 14 tuổi",
        }
    ]


def test_every_dossier_item_keeps_its_official_source(agent: Callable[..., Any]) -> None:
    agent("no-questions")
    body = start("Làm căn cước lần đầu")
    assert body["type"] == "dossier"
    docs = body["dossier"]["documents"]
    assert docs and all(".gov.vn" in d["document"]["source"]["url"] for d in docs)
    assert body["dossier"]["procedure"]["source"]["url"]


def test_unmentioned_documents_are_unsure_not_dropped(agent: Callable[..., Any]) -> None:
    agent("no-questions")
    s = statuses(start("Làm căn cước lần đầu"))
    assert s["d1"] == "needed" and s["d2"] == "needed"
    assert all(v == "unsure" for k, v in s.items() if k not in ("d1", "d2"))


@pytest.mark.parametrize("fixture", ["not-found", "invented-slug"])
def test_no_official_match_ends_in_not_found(agent: Callable[..., Any], fixture: str) -> None:
    agent(fixture)
    body = start("giấy phép câu cá")
    assert body["type"] == "not_found"
    assert "không tìm thấy" in body["message"]


def test_request_itself_can_justify_excluding_a_document(agent: Callable[..., Any]) -> None:
    agent("uses-request-as-answer-0")
    body = start("Tôi chưa từng có hộ chiếu")
    d3 = next(d for d in body["dossier"]["documents"] if d["id"] == "d3")
    assert d3["status"] == "not_needed"
    assert d3["because"][0]["number"] == 0
    assert d3["because"][0]["answer"] == "Tôi chưa từng có hộ chiếu"


def test_ambiguous_request_lets_user_choose(agent: Callable[..., Any]) -> None:
    agent("ambiguous-then-choose")
    q = start("căn cước")
    assert q["type"] == "question"
    assert q["question"]["kind"] == "choose_procedure"
    options = q["question"]["options"]
    assert len(options) == 2
    bad = client.post(f"/agent/{q['session_id']}", json={"answer": "something else"})
    assert bad.status_code == 422
    body = reply(q["session_id"], options[0])
    assert body["dossier"]["procedure"]["slug"] == "id-card-reissue"


def test_model_that_never_answers_properly_shows_full_list(agent: Callable[..., Any]) -> None:
    fake = agent("garbage")
    body = start("căn cước")
    assert body["type"] == "dossier"
    assert set(statuses(body).values()) == {"unsure"}
    assert len(fake.calls) == 1 + 4  # routing + bounded loop


def test_unknown_action_is_corrected(agent: Callable[..., Any]) -> None:
    agent("unknown-action")
    body = start("căn cước")
    assert body["dossier"]["procedure"]["slug"] == "id-card-new"
    assert statuses(body)["d1"] == "needed"


def test_question_limit_is_enforced(agent: Callable[..., Any]) -> None:
    agent("too-many-questions")
    body = start("hộ chiếu")
    for _ in range(4):
        assert body["type"] == "question"
        body = reply(body["session_id"], "a")
    assert body["type"] == "dossier"
    assert statuses(body)["d1"] == "not_needed"


def test_answer_without_pending_question_is_rejected(agent: Callable[..., Any]) -> None:
    agent("no-questions")
    body = start("căn cước")
    assert client.post(f"/agent/{body['session_id']}", json={"answer": "x"}).status_code == 409
    assert client.post("/agent/nope", json={"answer": "x"}).status_code == 404
