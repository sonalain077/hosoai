"""The only LLM client in the app. Talks to any OpenAI-compatible API (Ollama in dev)."""

from typing import Literal, Protocol

from openai import OpenAI
from pydantic import BaseModel

from hosoai.settings import Settings


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient(Protocol):
    def chat(self, messages: list[ChatMessage], *, vision: bool = False) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._client = OpenAI(
            base_url=self._settings.llm_base_url, api_key=self._settings.llm_api_key
        )

    def chat(self, messages: list[ChatMessage], *, vision: bool = False) -> str:
        model = self._settings.llm_vision_model if vision else self._settings.llm_model
        resp = self._client.chat.completions.create(
            model=model,
            messages=[m.model_dump() for m in messages],  # type: ignore[misc]
        )
        return resp.choices[0].message.content or ""
