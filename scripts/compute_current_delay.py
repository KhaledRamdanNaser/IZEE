# --- KHALED EDIT START ---
"""
scripts/compute_current_delay.py

Step 12A: Compute current_delay for each segment_completed training event.

Algorithm per event:
  1. Find the most recent stop_departure for the same vehicle strictly before
     this event's timestamp (loaded into memory for O(log N) binary search).
  2. Remap segment_id via SEGMENT_MERGE_MAP (imported from segment_stats).
  3. Look up avg_travel_time from segment_statistics (loaded into memory dict).
  4. Compute:
       elapsed_seconds = completion_timestamp - departure_timestamp (seconds)
       current_delay   = elapsed_seconds - avg_travel_time

Training days: Monday, Tuesday, Wednesday, Thursday, Saturday
  (Friday and Sunday excluded — Friday is test day, Sunday mapped weekday but
   excluded here per training split decision.)

Output: scripts/feature_data/current_delay.csv
"""
# --- KHALED EDIT END ---

import csv
import os
import statistics
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text

from database.connection import SessionLocal
from scripts.segment_stats import DAY_TYPE_MAP, SEGMENT_MERGE_MAP

# --- KHALED EDIT START ---
TRAINING_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Saturday")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "feature_data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current_delay.csv")

CSV_COLUMNS = [
    "event_id",
    "vehicle_id",
    "route_id",
    "direction",
    "segment_id",
    "remapped_segment_id",
    "day_of_week",
    "day_type",
    "time_period",
    "timestamp",
    "actual_travel_time",
    "avg_travel_time",
    "elapsed_seconds",
    "current_delay",
]
# --- KHALED EDIT END ---


def load_stop_departures(db):
    """
    Load all stop_departure timestamps into memory, grouped by vehicle_id.
    ISO8601 strings sort lexicographically == chronologically, so each list
    is kept as sorted strings for bisect_left lookups.

    Returns: dict[vehicle_id -> sorted list[str]]
    """
    # --- KHALED EDIT START ---
    result = db.execute(text("""
        SELECT vehicle_id, timestamp
        FROM transit_events
        WHERE event_type = 'stop_departure'
        ORDER BY vehicle_id, timestamp
    """))
    # --- KHALED EDIT START ---
    departures = defaultdict(list)
    for row in result:
        vehicle_id = row[0]
        timestamp = row[1]
        date = timestamp[:10]
        key = (vehicle_id, date)
        departures[key].append(timestamp)
    # --- KHALED EDIT END ---
    print(f"  stop_departure events loaded for {len(departures)} vehicle-day combinations")
    return dict(departures)
    # --- KHALED EDIT END ---


def load_segment_statistics(db):
    """
    Load segment_statistics into a lookup dict.
    Key: (segment_id, route_id, direction, day_type, time_period)
    Value: avg_travel_time (float, seconds)
    """
    # --- KHALED EDIT START ---
    result = db.execute(text("""
        SELECT segment_id, route_id, direction,
               day_type, time_period, avg_travel_time
        FROM segment_statistics
    """))
    stats = {}
    for row in result:
        key = (row[0], row[1], int(row[2]), row[3], row[4])
        stats[key] = float(row[5])
    print(f"  segment_statistics rows loaded: {len(stats)}")
    return stats
    # --- KHALED EDIT END ---


def fetch_training_events(db):
    """
    Fetch segment_completed events for training days with valid travel_time.
    Ordered by timestamp so progress prints are chronological.
    """
    # --- KHALED EDIT START ---
    result = db.execute(text("""
        SELECT
            event_id,
            vehicle_id,
            route_id,
            direction,
            segment_id,
            day_of_week,
            time_period,
            timestamp,
            (metrics->>'travel_time')::float AS actual_travel_time
        FROM transit_events
        WHERE event_type = 'segment_completed'
        AND day_of_week IN ('Monday','Tuesday','Wednesday','Thursday','Saturday')
        AND (metrics->>'travel_time') IS NOT NULL
        AND (metrics->>'travel_time')::float > 30
        AND (metrics->>'travel_time')::float < 3600
        ORDER BY timestamp
    """))
    return result.fetchall()
    # --- KHALED EDIT END ---


def find_last_departure(sorted_timestamps, completion_ts_str):
    """
    Binary search for the most recent stop_departure timestamp
    strictly before completion_ts_str (ISO8601 string comparison).
    Returns the timestamp string, or None if no departure precedes it.
    """
    # --- KHALED EDIT START ---
    idx = bisect_left(sorted_timestamps, completion_ts_str) - 1
    if idx < 0:
        return None
    return sorted_timestamps[idx]
    # --- KHALED EDIT END ---


def remap_segment(segment_id, route_id, direction):
    """
    Apply SEGMENT_MERGE_MAP for this (route_id, direction) if an entry exists.
    Returns the merged segment_id, or the original if no mapping applies.
    """
    # --- KHALED EDIT START ---
    sub = SEGMENT_MERGE_MAP.get((route_id, direction))
    if sub is None:
        return segment_id
    return sub.get(segment_id, segment_id)
    # --- KHALED EDIT END ---


def main():
    # --- KHALED EDIT START ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db = SessionLocal()
    try:
        print("Loading stop_departure events into memory...")
        departures = load_stop_departures(db)

        print("Loading segment_statistics into memory...")
        seg_stats = load_segment_statistics(db)

        print("Fetching training-day segment_completed events...")
        events = fetch_training_events(db)
        print(f"  {len(events)} events fetched")
    finally:
        db.close()

    no_departure   = 0
    no_stats_match = 0
    rows_out       = []

    for ev in events:
        (event_id, vehicle_id, route_id, direction,
         segment_id, day_of_week, time_period,
         completion_ts_str, actual_travel_time) = ev

        # Map day_of_week -> day_type
        day_type = DAY_TYPE_MAP.get(day_of_week)
        if day_type is None:
            no_departure += 1
            continue

        # Find most recent stop_departure for this vehicle on the same calendar date
        # --- KHALED EDIT START ---
        date = completion_ts_str[:10]
        veh_deps = departures.get((vehicle_id, date))
        # --- KHALED EDIT END ---
        if not veh_deps:
            no_departure += 1
            continue
        departure_ts_str = find_last_departure(veh_deps, completion_ts_str)
        if departure_ts_str is None:
            no_departure += 1
            continue

        # Remap segment_id via SEGMENT_MERGE_MAP
        remapped_segment_id = remap_segment(segment_id, route_id, int(direction))

        # Look up avg_travel_time from segment_statistics
        stats_key = (remapped_segment_id, route_id, int(direction), day_type, time_period)
        avg_travel_time = seg_stats.get(stats_key)
        if avg_travel_time is None:
            no_stats_match += 1
            continue

        # Compute elapsed and current_delay
        completion_dt  = datetime.fromisoformat(completion_ts_str)
        departure_dt   = datetime.fromisoformat(departure_ts_str)
        elapsed_seconds = (completion_dt - departure_dt).total_seconds()
        current_delay   = elapsed_seconds - avg_travel_time

        rows_out.append({
            "event_id":            event_id,
            "vehicle_id":          vehicle_id,
            "route_id":            route_id,
            "direction":           direction,
            "segment_id":          segment_id,
            "remapped_segment_id": remapped_segment_id,
            "day_of_week":         day_of_week,
            "day_type":            day_type,
            "time_period":         time_period,
            "timestamp":           completion_ts_str,
            "actual_travel_time":  round(actual_travel_time, 4),
            "avg_travel_time":     round(avg_travel_time, 4),
            "elapsed_seconds":     round(elapsed_seconds, 4),
            "current_delay":       round(current_delay, 4),
        })

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows_out)

    # Summary
    n      = len(rows_out)
    delays = [r["current_delay"] for r in rows_out]

    print()
    print("=" * 52)
    print("CURRENT DELAY COMPUTATION SUMMARY")
    print("=" * 52)
    print(f"Total events processed:          {len(events)}")
    print(f"Skipped — no departure found:    {no_departure}")
    print(f"Skipped — no stats match:        {no_stats_match}")
    print(f"Successfully computed:           {n}")
    if delays:
        print(f"Mean current_delay (s):         {statistics.mean(delays):.2f}")
        print(f"Std  current_delay (s):         {statistics.stdev(delays):.2f}")
        print(f"Min  current_delay (s):         {min(delays):.2f}")
        print(f"Max  current_delay (s):         {max(delays):.2f}")
    print(f"Output: {OUTPUT_FILE}")
    # --- KHALED EDIT END ---


if __name__ == "__main__":
    main()
