from collections import Counter
from datetime import datetime
import xml.etree.ElementTree as ET
import sys
import os

EXPORT = sys.argv[1] if len(sys.argv) > 1 else r"C:\projects\pulsecontext\export.xml"

def parse_date(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except Exception:
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

print('File:', EXPORT)
print('Size (MB):', round(os.path.getsize(EXPORT) / (1024*1024), 2))

rec_count = 0
workout_count = 0
record_type_counts = Counter()
source_counts = Counter()
min_date = None
max_date = None
min_workout = None
max_workout = None

# stream parse
for event, elem in ET.iterparse(EXPORT, events=("end",)):
    tag = elem.tag
    if tag == 'Record':
        rec_count += 1
        t = elem.attrib.get('type')
        record_type_counts[t] += 1
        src = elem.attrib.get('sourceName') or elem.attrib.get('source')
        if src:
            source_counts[src] += 1
        sd = elem.attrib.get('startDate')
        if sd:
            d = parse_date(sd)
            if d:
                if min_date is None or d < min_date:
                    min_date = d
                if max_date is None or d > max_date:
                    max_date = d
    elif tag == 'Workout':
        workout_count += 1
        sd = elem.attrib.get('startDate')
        ed = elem.attrib.get('endDate')
        if sd:
            d = parse_date(sd)
            if d:
                if min_workout is None or d < min_workout:
                    min_workout = d
                if max_workout is None or d > max_workout:
                    max_workout = d
        if ed:
            d2 = parse_date(ed)
            if d2:
                if min_workout is None or d2 < min_workout:
                    min_workout = d2
                if max_workout is None or d2 > max_workout:
                    max_workout = d2
    # clear to keep memory low
    elem.clear()

print('\nTotals:')
print('  Record elements:', rec_count)
print('  Workout elements:', workout_count)
print('  Unique record types:', len(record_type_counts))
print('\nTop 20 Record types:')
for t, c in record_type_counts.most_common(20):
    print(f'  {c:8d}  {t}')

print('\nTop 10 sources:')
for s, c in source_counts.most_common(10):
    print(f'  {c:8d}  {s}')

print('\nDate range for Record startDate:')
print('  earliest:', min_date.isoformat() if min_date else 'N/A')
print('  latest:  ', max_date.isoformat() if max_date else 'N/A')

print('\nDate range for Workouts (start/end):')
print('  earliest:', min_workout.isoformat() if min_workout else 'N/A')
print('  latest:  ', max_workout.isoformat() if max_workout else 'N/A')
