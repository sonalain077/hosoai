"""Fake LLM client for tests. Replays recorded replies from tests/fixtures/llm/<name>.json."""

import json
from pathlib import Path

from hosoai.llm.client import ChatMessage


class FakeLLMClient:
    def __init__(self, fixture: Path) -> None:
        self._replies: list[str] = json.loads(fixture.read_text(encoding="utf-8"))["replies"]
        self.calls: list[list[ChatMessage]] = []

    def chat(self, messages: list[ChatMessage], *, vision: bool = False) -> str:
        self.calls.append(messages)
        if not self._replies:
            raise RuntimeError("FakeLLMClient: no recorded replies left")
        return self._replies.pop(0)
