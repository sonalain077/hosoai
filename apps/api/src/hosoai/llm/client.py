"""The only LLM client in the app. Talks to any OpenAI-compatible API (Ollama in dev)."""

from typing import Any, Literal, Protocol

from openai import OpenAI
from pydantic import BaseModel

from hosoai.settings import Settings


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    images: list[
        str
    ] = []  # base64 PNGs, for the vision model (a blank form page, never a scan of an ID)


def to_openai(m: ChatMessage) -> dict[str, Any]:
    """OpenAI chat format; images become data-URL parts (also understood by Ollama)."""
    if not m.images:
        return {"role": m.role, "content": m.content}
    parts: list[dict[str, Any]] = [{"type": "text", "text": m.content}]
    parts += [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
        for img in m.images
    ]
    return {"role": m.role, "content": parts}


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
            messages=[to_openai(m) for m in messages],  # type: ignore[misc]
            temperature=self._settings.llm_temperature,
        )
        return resp.choices[0].message.content or ""
