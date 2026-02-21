"""
Pydantic models used across the backend.

Only input shapes belong here. These models provide validation at the
FastAPI route boundary and are reused in service/repo layers.

Guidelines:
- Keep models minimal and stable. If you need DB-specific fields
    (like `id`), create a separate model (e.g., `EventOut`) rather than
    re-using `EventIn`.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict
from datetime import datetime


class EventIn(BaseModel):
        """Input shape for an event sent by clients.

        Fields:
        - `user_id`: string identifier for the user who generated the event.
        - `ts`: ISO-8601 timestamp. Service enforces timezone-awareness.
        - `type`: semantic event type (validated by `EventService`).
        - `source`: short tag of data source (e.g., `simulator`, `apple_health`).
        - `payload`: arbitrary JSON payload. Service may attach a `v` version.
        """

        user_id: str
        ts: datetime
        type: str
        source: str
        payload: Dict[str, Any] = Field(default_factory=dict)
