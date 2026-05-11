"""Schemas for run timeline events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from packages.schemas.common import BaseSchema, EventType


class AgentEvent(BaseSchema):
    id: int | None = None
    run_id: str
    event_type: EventType
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    step: str | None = None
    iteration: int = 0
    created_at: datetime

