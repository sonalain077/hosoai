"""Fake LLM client for tests. Replays recorded replies from tests/fixtures/llm/<name>.json."""

import json
from pathlib import Path

from hosoai.llm.client import ChatMessage


class FakeLLMClient:
    def __init__(self, fixture: Path) -> None:
        self._replies: list[str] = json.loads(fixture.read_text(encoding="utf-8"))["replies"]
        self.calls: list[list[ChatMessage]] = []
        self.vision: list[bool] = []  # the vision flag of each call

    def chat(self, messages: list[ChatMessage], *, vision: bool = False) -> str:
        self.calls.append(list(messages))
        self.vision.append(vision)
        if not self._replies:
            raise RuntimeError("FakeLLMClient: no recorded replies left")
        return self._replies.pop(0)
