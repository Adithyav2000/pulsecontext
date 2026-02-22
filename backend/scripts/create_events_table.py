from settings import settings
import psycopg

DDL = '''
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    type TEXT NOT NULL,
    source TEXT,
    payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events (user_id, ts DESC);
'''

print('Connecting to', settings.db_url)
with psycopg.connect(settings.db_url, connect_timeout=5) as conn:
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
print('DDL applied')
