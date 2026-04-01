from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    news_item_id: str
    sentiment: Literal["bullish", "bearish", "neutral"]
    topics: list[str]
    summary: str
    signal: str
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
