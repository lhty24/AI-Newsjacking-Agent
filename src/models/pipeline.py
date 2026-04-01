import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class PipelineRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trigger: Literal["cli", "api", "scheduler"]
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    status: Literal["running", "completed", "failed"] = "running"
    news_count: int = 0
    variants_generated: int = 0
    variants_posted: int = 0
    error: str | None = None
