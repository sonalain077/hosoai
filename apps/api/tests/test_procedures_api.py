from pathlib import Path

from fastapi.testclient import TestClient

from hosoai.main import app
from hosoai.procedures.store import ProcedureStore, get_store
from hosoai.settings import Settings

client = TestClient(app)


def test_list_returns_every_parsed_procedure_with_source() -> None:
    parsed = Settings().data_dir / "procedures" / "parsed"
    body = client.get("/procedures").json()
    assert {p["slug"] for p in body} == {f.stem for f in parsed.glob("*.json")}
    for p in body:
        assert p["source"]["url"].startswith("https://")
        assert ".gov.vn" in p["source"]["url"]


def test_get_procedure_has_sources_on_every_item() -> None:
    body = client.get("/procedures/passport").json()
    assert body["slug"] == "passport"
    assert body["source"]["url"]
    for key in ("steps", "documents", "legal_basis", "methods", "forms"):
        for item in body[key]:
            assert item["source"]["url"], key
    for key in ("fee", "processing_time", "agency"):
        if body[key] is not None:
            assert body[key]["source"]["url"], key


def test_unknown_procedure_says_not_found() -> None:
    resp = client.get("/procedures/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found_in_official_sources"


def test_empty_store_returns_empty_list(tmp_path: Path) -> None:
    app.dependency_overrides[get_store] = lambda: ProcedureStore(tmp_path)
    try:
        assert client.get("/procedures").json() == []
        assert client.get("/procedures/passport").status_code == 404
    finally:
        app.dependency_overrides.pop(get_store, None)
