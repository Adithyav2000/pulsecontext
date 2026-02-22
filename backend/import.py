import xml.etree.ElementTree as ET
from datetime import datetime
import sys

from psycopg.types.json import Jsonb
from db import get_conn
from settings import settings

# Keep only Apple Watch relevant metrics for now
KEEP_RECORD_TYPES = {
    "HKQuantityTypeIdentifierHeartRate": "heart_rate_bpm",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv_sdnn_ms",
}

BATCH_SIZE = 1000

def parse_date(date_str: str) -> datetime:
    # Example format: "2025-02-10 08:45:23 -0500"
    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")

def main(export_path: str):
    print(f"Importing Apple Health data from: {export_path}")
    total_inserted = 0
    batch = []

    with get_conn() as conn:
        with conn.cursor() as cur:

            # Stream parse (does NOT load entire file into memory)
            for event, elem in ET.iterparse(export_path, events=("end",)):

                if elem.tag == "Record":
                    record_type = elem.attrib.get("type")

                    if record_type in KEEP_RECORD_TYPES:
                        ts = parse_date(elem.attrib["startDate"])
                        value = float(elem.attrib["value"])

                        batch.append((
                            settings.default_user,
                            ts,
                            "health_metric",
                            "apple_health_export",
                            Jsonb({
                                "v": 1,
                                "metric": KEEP_RECORD_TYPES[record_type],
                                "raw_type": record_type,
                                "value": value,
                                "provider": "apple_health"
                            })
                        ))

                elif elem.tag == "Workout":
                    ts = parse_date(elem.attrib["startDate"])
                    end = parse_date(elem.attrib["endDate"])
                    workout_type = elem.attrib.get("workoutActivityType")

                    batch.append((
                        settings.default_user,
                        ts,
                        "workout",
                        "apple_health_export",
                        Jsonb({
                            "v": 1,
                            "workout_type": workout_type,
                            "end": end.isoformat(),
                            "provider": "apple_health"
                        })
                    ))

                if len(batch) >= BATCH_SIZE:
                    cur.executemany(
                        "INSERT INTO events (user_id, ts, type, source, payload) VALUES (%s,%s,%s,%s,%s)",
                        batch,
                    )
                    conn.commit()
                    total_inserted += len(batch)
                    print(f"Inserted {total_inserted} events...")
                    batch.clear()

                elem.clear()

            # Insert remaining
            if batch:
                cur.executemany(
                    "INSERT INTO events (user_id, ts, type, source, payload) VALUES (%s,%s,%s,%s,%s)",
                    batch,
                )
                conn.commit()
                total_inserted += len(batch)

    print(f"Import complete. Total events inserted: {total_inserted}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_health.py <path_to_export.xml>")
        sys.exit(1)

    main(sys.argv[1])