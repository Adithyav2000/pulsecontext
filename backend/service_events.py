"""
Service / facade layer.

This module implements business rules and normalization before any DB
interaction. It is intentionally free of SQL — it calls `EventRepo` to
perform database operations. All write paths should go through this
service to ensure consistency and a single security chokepoint.

Key responsibilities:
- protect the system (max batch sizes)
- validate event semantics (allowed event `type` values)
- enforce timestamp rules (timezone-awareness + UTC normalization)
- apply payload versioning
- perform (future) permission checks using `caller_user`
"""

from typing import List
from datetime import timezone
from models import EventIn
from repo_events import EventRepo
from settings import settings


ALLOWED_TYPES = {
    "context_snapshot",
    "health_metric",
    "workout",
    "calendar_context",
}


class EventService:
    """Business rules + validation + normalization.

    Example usage:
        repo = EventRepo()
        svc = EventService(repo)
        svc.ingest_events(events, caller_user='alice')
    """

    def __init__(self, repo: EventRepo):
        self.repo = repo

    def ingest_events(self, events: List[EventIn], caller_user: str | None = None) -> int:
        """Validate and persist a batch of events.

        Steps:
        1. Quick guards (empty list, batch size limit).
        2. Validate and normalize each `EventIn` in-place.
        3. Delegate to `EventRepo.insert_events()` for the DB write.

        Raises:
        - `ValueError` for invalid inputs (bad type, missing tzinfo, too large)
        - `PermissionError` if `caller_user` attempts to write for another user
        """

        # 1) protect the system
        if len(events) == 0:
            return 0
        if len(events) > settings.max_batch_size:
            raise ValueError(
                f"Too many events in one request: {len(events)} (max {settings.max_batch_size})"
            )

        # 2) validate/normalize each event
        for e in events:
            if e.type not in ALLOWED_TYPES:
                raise ValueError(f"Unsupported event type: {e.type}")

            # Must be timezone-aware
            if e.ts.tzinfo is None:
                raise ValueError("Timestamp must include timezone info (e.g., 2026-02-20T10:00:00Z)")

            # Normalize to UTC — repository stores timestamps as UTC.
            e.ts = e.ts.astimezone(timezone.utc)

            # (Optional security rule for later)
            if caller_user and e.user_id != caller_user:
                raise PermissionError("Cannot write events for another user")

            # Payload versioning (helps future migrations + backwards compat)
            if "v" not in e.payload:
                e.payload["v"] = 1

        # 3) DB write via repository
        return self.repo.insert_events(events)

    def get_timeline(self, user_id: str, limit: int) -> list[dict]:
        """Return timeline for `user_id` capped by configured limits."""

        limit = max(1, min(limit, settings.max_timeline_limit))
        return self.repo.fetch_timeline(user_id, limit)

    def health_check(self) -> None:
        """Perform a lightweight DB ping via the repository."""

        self.repo.ping()
