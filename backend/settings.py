"""
Centralized runtime configuration for the backend.

This module uses `python-dotenv` to read a local `.env` file during
development and exposes a Pydantic `Settings` model named `settings`.

Why this exists:
- Keeps configuration in one place so other modules import `settings`.
- Provides typed fields with defaults and simple validation.

Environment variables used:
- `DB_URL` — PostgreSQL connection URL used by `db.get_conn()`.
- `USER_ID` — default demo user for the `/seed` route.
- `MAX_BATCH_SIZE` — safety limit for ingest batch sizes.
- `MAX_TIMELINE_LIMIT` — maximum `limit` allowed for timeline queries.

Example `.env`:
DB_URL=postgresql://pulse:pulse@localhost:5432/pulsecontext
USER_ID=adithya

"""

from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    """Typed settings container.

    All downstream code should import `settings` from this module. Use
    these attributes (not os.getenv) so tests can monkeypatch `settings`.
    """

    db_url: str = os.getenv(
        "DB_URL", "postgresql://pulse:pulse@localhost:5432/pulsecontext"
    )
    default_user: str = os.getenv("USER_ID", "adithya")
    max_batch_size: int = int(os.getenv("MAX_BATCH_SIZE", "5000"))
    max_timeline_limit: int = int(os.getenv("MAX_TIMELINE_LIMIT", "1000"))


settings = Settings()
