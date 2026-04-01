import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ContentVariant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analysis_id: str
    style: Literal["analytical", "meme", "contrarian"]
    text: str
    prompt_template: str
    score: float | None = None
    score_breakdown: dict | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
