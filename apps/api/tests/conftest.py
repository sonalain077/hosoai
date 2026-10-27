from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "llm"


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any accidental real LLM call in tests fails loudly instead of hitting a service."""

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Tests must use FakeLLMClient, not a real LLM")

    monkeypatch.setattr("hosoai.llm.client.OpenAICompatibleClient.__init__", _blocked)
