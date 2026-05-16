from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WebhookAcceptedResponse(BaseModel):
    status: Literal["accepted"] = Field(description="Webhook ingestion acknowledgement state.")
    request_id: str = Field(description="Unique request identifier for this webhook delivery.")