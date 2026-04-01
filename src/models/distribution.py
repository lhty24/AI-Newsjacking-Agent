import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DistributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    variant_id: str
    platform: str = "twitter"
    platform_post_id: str | None = None
    status: Literal["posted", "failed", "pending"] = "pending"
    posted_at: datetime | None = None
    error: str | None = None
