"""
Repository: SQL operations for `events`.

This file contains only DB interaction code. It maps Pydantic models
to SQL parameters and converts DB rows to plain Python dicts suitable
for JSON responses. Keep business rules out of this module.

Important notes:
- SQL strings are simple and use positional parameters for psycopg.
- We convert `payload` using `Jsonb` so Postgres stores native JSONB.
- `insert_events` commits after executing the batch; callers expect
  that the DB write is durable after the method returns.
"""

from typing import List, Dict, Any
from psycopg.types.json import Jsonb
from db import get_conn
from models import EventIn


class EventRepo:
    """DB access only. No business logic here.

    Responsibilities:
    - Map `EventIn` -> SQL parameters
    - Execute queries and return plain dict objects
    - Keep transaction/commit boundaries local and explicit
    """

    def insert_events(self, events: List[EventIn]) -> int:
        """Batch-insert a list of events.

        Returns the number of inserted rows. This function performs a
        single executemany() call and commits once to reduce round trips.
        """

        rows = [
            (e.user_id, e.ts, e.type, e.source, Jsonb(e.payload)) for e in events
        ]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO events (user_id, ts, type, source, payload) VALUES (%s, %s, %s, %s, %s)",
                    rows,
                )
            conn.commit()
        return len(rows)

    def fetch_timeline(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch the most recent `limit` events for `user_id`.

        Returns a list of dicts with keys: id, user_id, ts (ISO string),
        type, source, payload (parsed JSON). The ordering is newest-first.
        """

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, user_id, ts, type, source, payload "
                    "FROM events WHERE user_id=%s ORDER BY ts DESC LIMIT %s",
                    (user_id, limit),
                )
                out: List[Dict[str, Any]] = []
                for r in cur.fetchall():
                    out.append({
                        "id": str(r[0]),
                        "user_id": r[1],
                        "ts": r[2].isoformat(),
                        "type": r[3],
                        "source": r[4],
                        "payload": r[5],
                    })
                return out

    def ping(self) -> None:
        """Lightweight DB health check. Raises on error.

        Used by the top-level `/health` endpoint to validate DB reachability.
        """

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
