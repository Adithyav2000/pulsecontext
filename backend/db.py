"""
Database connection helper.

This module centralizes how connections are created. Right now we use
`psycopg.connect(settings.db_url)` which opens a new connection per call.

Why this exists:
- Single place to swap connection strategy (pooling, async driver, etc.).
- Keeps repository code focused on SQL and row mapping.

Usage:
    from db import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")

Note: switching to a connection pool or async DB driver will change the
`get_conn()` implementation — repository code should remain unchanged.
"""

import psycopg
from settings import settings


def get_conn():
    """Return a new psycopg connection using `settings.db_url`.

    We add a short `connect_timeout` so HTTP requests don't hang
    indefinitely if the database is unreachable. Adjust the timeout
    as needed for your environment or replace with a pool.
    """

    return psycopg.connect(settings.db_url, connect_timeout=5)
