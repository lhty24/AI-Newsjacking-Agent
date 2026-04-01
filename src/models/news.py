import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    title: str
    content: str
    url: str | None = None
    published_at: datetime
    tickers: list[str]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
