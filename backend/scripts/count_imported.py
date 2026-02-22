from settings import settings
import psycopg

with psycopg.connect(settings.db_url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM events WHERE source=%s", ("apple_health_export",))
        print('apple_health_export rows:', cur.fetchone()[0])
