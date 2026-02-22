#!/usr/bin/env python3
"""
Migration Script: Load Apple Health export.xml into normalized SQL schema.

Usage:
    python migrate_to_schema.py

Prerequisites:
    - PostgreSQL running with pulsecontext database
    - schema.sql already applied (creates all tables)
    - export.xml in parent directory
"""

import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
import psycopg
from psycopg.types.json import Jsonb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from settings import settings


def parse_date(date_str: str):
    """Parse Apple Health date string."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
    except Exception:
        try:
            return datetime.fromisoformat(date_str)
        except Exception:
            return None


def load_health_records(conn, user_id, export_path):
    """Stream-parse export.xml and insert into health_record table."""
    print(f"Loading health records from {export_path}...")
    
    batch = []
    batch_size = 1000
    inserted = 0
    
    for event, elem in ET.iterparse(export_path, events=("end",)):
        tag = elem.tag
        
        if tag == 'Record':
            record_type = elem.attrib.get('type', 'unknown')
            source = elem.attrib.get('sourceName') or elem.attrib.get('source', 'unknown')
            start_date = elem.attrib.get('startDate')
            value = elem.attrib.get('value')
            unit = elem.attrib.get('unit')
            
            if start_date and value:
                dt = parse_date(start_date)
                if dt:
                    try:
                        batch.append((
                            user_id,
                            record_type,
                            source,
                            dt,
                            float(value),
                            unit
                        ))
                    except Exception as e:
                        print(f"  ⚠️  Skipped record: {e}")
            
            if len(batch) >= batch_size:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO health_record 
                        (user_id, record_type, source, ts, value, unit)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        batch
                    )
                inserted += len(batch)
                print(f"  ...inserted {inserted} records")
                conn.commit()
                batch.clear()
        
        elem.clear()
    
    # Final batch
    if batch:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO health_record 
                (user_id, record_type, source, ts, value, unit)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                batch
            )
        inserted += len(batch)
        conn.commit()
    
    print(f"✓ Loaded {inserted} health records")
    return inserted


def compute_daily_summaries(conn, user_id):
    """Compute daily_summary from health_record."""
    print("Computing daily summaries...")
    
    with conn.cursor() as cur:
        # Clear old summaries
        cur.execute("DELETE FROM daily_summary WHERE user_id = %s", (user_id,))
        
        # Insert new summaries
        cur.execute("""
            INSERT INTO daily_summary 
            (user_id, date, 
             resting_hr_bpm, min_hr_bpm, max_hr_bpm, avg_hr_bpm,
             avg_hrv_ms, steps, active_minutes, active_energy_cal,
             stress_score, created_at)
            SELECT
                %s,
                DATE(ts),
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY value)
                  FILTER (WHERE record_type LIKE '%%HeartRate%%'),
                MIN(value) FILTER (WHERE record_type LIKE '%%HeartRate%%'),
                MAX(value) FILTER (WHERE record_type LIKE '%%HeartRate%%'),
                AVG(value) FILTER (WHERE record_type LIKE '%%HeartRate%%'),
                AVG(value) FILTER (WHERE record_type LIKE '%%HRV%%' 
                                OR record_type LIKE '%%HeartRateVariability%%'),
                SUM(value) FILTER (WHERE record_type LIKE '%%StepCount%%'),
                COUNT(DISTINCT DATE_TRUNC('minute', ts))::INT 
                  FILTER (WHERE record_type LIKE '%%Active%%' 
                          OR value > 100),
                SUM(value) FILTER (WHERE record_type LIKE '%%ActiveEnergyBurned%%'),
                NULL,
                NOW()
            FROM health_record
            WHERE user_id = %s
            GROUP BY DATE(ts)
            ORDER BY DATE(ts) DESC
        """, (user_id, user_id))
        
        conn.commit()
    
    print("✓ Daily summaries calculated")


def compute_hr_baselines(conn, user_id):
    """Compute HR baselines (7-day rolling averages per hour/day-of-week)."""
    print("Computing HR baselines...")
    
    with conn.cursor() as cur:
        # Clear old baselines
        cur.execute("DELETE FROM hr_baselines WHERE user_id = %s", (user_id,))
        
        # Compute and insert baselines
        cur.execute("""
            INSERT INTO hr_baselines
            (user_id, hour_of_day, day_of_week, baseline_hr, baseline_std, 
             sample_count, last_updated)
            SELECT
                %s,
                EXTRACT(HOUR FROM ts)::INT,
                EXTRACT(DOW FROM ts)::INT - 1,
                ROUND(AVG(value)::NUMERIC, 1),
                ROUND(STDDEV(value)::NUMERIC, 1),
                COUNT(*),
                NOW()
            FROM health_record
            WHERE user_id = %s
                AND record_type LIKE '%%HeartRate%%'
                AND ts >= NOW() - INTERVAL '30 days'
            GROUP BY EXTRACT(HOUR FROM ts), EXTRACT(DOW FROM ts)
        """, (user_id, user_id))
        
        conn.commit()
    
    print("✓ HR baselines calculated")


def compute_activity_patterns(conn, user_id):
    """Compute activity patterns (time-of-day + motion type histograms)."""
    print("Computing activity patterns...")
    
    with conn.cursor() as cur:
        # Clear old patterns
        cur.execute("DELETE FROM activity_patterns WHERE user_id = %s", (user_id,))
        
        # Compute patterns from step count / motion data
        cur.execute("""
            INSERT INTO activity_patterns
            (user_id, day_of_week, hour_of_day, motion_type, frequency_count, last_updated)
            SELECT
                %s,
                EXTRACT(DOW FROM ts)::INT - 1,
                EXTRACT(HOUR FROM ts)::INT,
                CASE 
                    WHEN value IS NULL THEN 'unknown'
                    WHEN value > 500 THEN 'high_activity'
                    WHEN value > 100 THEN 'walking'
                    ELSE 'sedentary'
                END,
                COUNT(*),
                NOW()
            FROM health_record
            WHERE user_id = %s
                AND (record_type LIKE '%%StepCount%%' 
                     OR record_type LIKE '%%Motion%%'
                     OR record_type LIKE '%%WalkingSpeed%%')
            GROUP BY 
                EXTRACT(DOW FROM ts),
                EXTRACT(HOUR FROM ts),
                CASE WHEN value IS NULL THEN 'unknown'
                     WHEN value > 500 THEN 'high_activity'
                     WHEN value > 100 THEN 'walking'
                     ELSE 'sedentary' END
        """, (user_id, user_id))
        
        conn.commit()
    
    print("✓ Activity patterns calculated")


def compute_hrv_baselines(conn, user_id):
    """Compute 30-day HRV baseline."""
    print("Computing HRV baselines...")
    
    with conn.cursor() as cur:
        # Clear old baselines
        cur.execute("DELETE FROM hrv_baselines WHERE user_id = %s", (user_id,))
        
        # Compute 30-day rolling baseline
        cur.execute("""
            INSERT INTO hrv_baselines
            (user_id, period_start_date, period_end_date,
             baseline_hrv_30day_avg, baseline_hrv_std, z_score_threshold, last_updated)
            SELECT
                %s,
                (CURRENT_DATE - INTERVAL '30 days')::DATE,
                CURRENT_DATE,
                ROUND(AVG(value)::NUMERIC, 2),
                ROUND(STDDEV(value)::NUMERIC, 2),
                2.0,  -- threshold for anomaly detection
                NOW()
            FROM health_record
            WHERE user_id = %s
                AND (record_type LIKE '%%HRV%%'
                     OR record_type LIKE '%%HeartRateVariability%%')
                AND ts >= NOW() - INTERVAL '30 days'
        """, (user_id, user_id))
        
        conn.commit()
    
    print("✓ HRV baselines calculated")


def insert_device_sources(conn, user_id):
    """Register data sources (Apple Watch, iPhone, etc.)."""
    print("Registering device sources...")
    
    sources = [
        ('Apple Watch', 'wearable', 'Adithya\'s Apple Watch'),
        ('iPhone', 'phone', 'iPhone'),
        ('Oura', 'wearable', 'Oura'),
        ('Garmin', 'wearable', 'Garmin'),
    ]
    
    with conn.cursor() as cur:
        for device_name, device_type, source_label in sources:
            cur.execute("""
                INSERT INTO device_sources (user_id, device_name, device_type, source_label)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, device_name, source_label) DO NOTHING
            """, (user_id, device_name, device_type, source_label))
        
        conn.commit()
    
    print("✓ Device sources registered")


def main():
    export_path = r'C:\projects\pulsecontext\export.xml'
    user_id = 'adithya'
    
    if not os.path.exists(export_path):
        print(f"ERROR: {export_path} not found")
        sys.exit(1)
    
    print(f"Connecting to {settings.db_url}...")
    try:
        conn = psycopg.connect(settings.db_url, connect_timeout=5)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)
    
    # Ensure user exists
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users (user_id, name, timezone)
            VALUES (%s, 'Adithya', 'America/New_York')
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id,))
        conn.commit()
    
    try:
        # 1. Load raw data
        load_health_records(conn, user_id, export_path)
        
        # 2. Compute aggregates
        compute_daily_summaries(conn, user_id)
        compute_hr_baselines(conn, user_id)
        compute_hrv_baselines(conn, user_id)
        compute_activity_patterns(conn, user_id)
        
        # 3. Register sources
        insert_device_sources(conn, user_id)
        
        print("\n" + "=" * 80)
        print("✓ MIGRATION COMPLETE!")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. Manually create location_clusters (home, work, gym, etc.)")
        print("  2. Import calendar events via Google Calendar API or .ics file")
        print("  3. Execute example queries from notebook to validate data")
        print("  4. Test suggestion engine with Use Case #1 (Morning Commute)")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
