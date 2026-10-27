from datetime import datetime

from pydantic import BaseModel, HttpUrl


class Source(BaseModel):
    """Citation to an official source. Every piece of procedural info must carry one."""

    url: HttpUrl
    title: str
    document_number: str | None = None  # procedure code or legal document number
    publisher: str | None = None  # e.g. "Cổng Dịch vụ công - Bộ Công an"
    retrieved_at: datetime
