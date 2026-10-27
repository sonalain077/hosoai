from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import hosoai.profile.models  # noqa: F401  (registers the table)

FIXTURES = Path(__file__).parent / "fixtures" / "llm"


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any accidental real LLM call in tests fails loudly instead of hitting a service."""

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Tests must use FakeLLMClient, not a real LLM")

    monkeypatch.setattr("hosoai.llm.client.OpenAICompatibleClient.__init__", _blocked)


@pytest.fixture(autouse=True)
def _memory_db() -> Iterator[None]:
    """Each test gets an empty in-memory database; the real hosoai.db is never touched."""
    from hosoai.main import app
    from hosoai.profile.store import get_db

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def _db() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    yield
    app.dependency_overrides.pop(get_db, None)
