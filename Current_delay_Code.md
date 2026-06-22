# --- KHALED EDIT START ---
"""
scripts/compute_current_delay.py

Step 12A: Compute current_delay for each segment_completed event
(both TRAIN and TEST days).

CORRECT FORMULA (offline, completed segment):
    current_delay = actual_travel_time - avg_travel_time

Derivation from the original design:
    Design:   current_delay = actual_elapsed_on_segment - (avg * segment_progress)
    Offline:  segment is fully completed → segment_progress = 1.0
              actual_elapsed_on_segment = metrics['travel_time'] (already exact)
    Therefore: current_delay = actual_travel_time - avg_travel_time × 1.0
                             = actual_travel_time - avg_travel_time

Why NOT using stop_departure timestamps:
    - stop_departure.segment_id is NULL for 100% of rows in DB
    - stop_departure.from_stop_id is NULL for 100% of rows in DB
    - The old bisect_left approach returned ANY prior departure, spanning
      multiple segments, causing elapsed_seconds up to 87x actual_travel_time
    - segment_completed.metrics['travel_time'] is already computed by
      traversal_lifecycle.py as (completion_time - segment_entry_time)
      making it the canonical single-segment elapsed time

Why NOT using VehicleState.segment_progress:
    - transition_tracker and traversal_tracker are in-memory only
    - vehicle_live_state has only 306 rows (current snapshot, not history)
    - Offline replay cannot reconstruct historical segment_progress values

Coverage guarantees:
    - 100% of valid segment_completed events get a non-fallback value
      (as long as segment_statistics has a matching cell)
    - Both TRAIN and TEST events are processed identically
    - No train/test distribution shift

Days covered: Monday, Tuesday, Wednesday, Thursday, Saturday (TRAIN)
              + Friday, Sunday (TEST)

Output: scripts/feature_data/current_delay.csv
"""
# --- KHALED EDIT END ---

import csv
import os
import statistics
from collections import defaultdict

from sqlalchemy import text

from database.connection import SessionLocal
from scripts.segment_stats import DAY_TYPE_MAP, SEGMENT_MERGE_MAP

# --- KHALED EDIT START ---
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "feature_data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "current_delay.csv")

# Include ALL valid days (train + test) so the same file serves both splits
ALL_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Saturday", "Friday", "Sunday")

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
    "current_delay",
]
# --- KHALED EDIT END ---


# ===========================================================================
# LOADERS
# ===========================================================================

def load_segment_statistics(db) -> dict:
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
        key = (str(row[0]), str(row[1]), int(row[2]), str(row[3]), str(row[4]))
        stats[key] = float(row[5])
    print(f"  segment_statistics rows loaded: {len(stats)}")
    return stats
    # --- KHALED EDIT END ---


def fetch_all_events(db) -> list:
    """
    Fetch segment_completed events for ALL days (train + test) with valid travel_time.
    Returns rows ordered by timestamp.

    NOTE: travel_time lower bound is 10s (not 30s) to match feature_engineering.py
    filtering. Upper bound 3600s is consistent with segment_stats.py.
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
        AND day_of_week IN (
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Saturday',
            'Friday', 'Sunday'
        )
        AND (metrics->>'travel_time') IS NOT NULL
        AND (metrics->>'travel_time')::float > 10
        AND (metrics->>'travel_time')::float < 3600
        ORDER BY timestamp
    """))
    return result.fetchall()
    # --- KHALED EDIT END ---


# ===========================================================================
# SEGMENT REMAP
# ===========================================================================

def remap_segment(segment_id: str, route_id: str, direction: int) -> str:
    """Apply SEGMENT_MERGE_MAP. Returns original if no mapping exists."""
    # --- KHALED EDIT START ---
    sub = SEGMENT_MERGE_MAP.get((route_id, direction))
    if sub is None:
        return segment_id
    return sub.get(segment_id, segment_id)
    # --- KHALED EDIT END ---


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    # --- KHALED EDIT START ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db = SessionLocal()
    try:
        print("Loading segment_statistics into memory...")
        seg_stats = load_segment_statistics(db)

        print("Fetching segment_completed events (all days)...")
        events = fetch_all_events(db)
        print(f"  {len(events)} events fetched")
    finally:
        db.close()

    no_day_type    = 0
    no_stats_match = 0
    rows_out       = []

    for ev in events:
        (event_id, vehicle_id, route_id, direction,
         segment_id, day_of_week, time_period,
         timestamp, actual_travel_time) = ev

        # Map day_of_week → day_type
        day_type = DAY_TYPE_MAP.get(day_of_week)
        if day_type is None:
            no_day_type += 1
            continue

        # Apply SEGMENT_MERGE_MAP before lookup
        direction_int = int(direction) if direction is not None else 0
        remapped_segment_id = remap_segment(segment_id, route_id, direction_int)

        # Look up avg_travel_time from segment_statistics
        stats_key = (remapped_segment_id, route_id, direction_int, day_type, time_period)
        avg_travel_time = seg_stats.get(stats_key)
        if avg_travel_time is None:
            no_stats_match += 1
            continue

        # -----------------------------------------------------------------------
        # CORRECT FORMULA:
        #   current_delay = actual_travel_time - avg_travel_time
        #
        # This is the offline instantiation of the design formula:
        #   current_delay = actual_elapsed_on_segment - (avg × segment_progress)
        # with segment_progress = 1.0 (segment is fully completed).
        #
        # actual_travel_time = metrics['travel_time'], which was stored by
        # traversal_lifecycle.py as (completion_time - segment_entry_time),
        # meaning it is already bounded to exactly ONE segment.
        # No stop_departure matching needed.
        # -----------------------------------------------------------------------
        current_delay = actual_travel_time - avg_travel_time

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
            "timestamp":           timestamp,
            "actual_travel_time":  round(actual_travel_time, 4),
            "avg_travel_time":     round(avg_travel_time, 4),
            "current_delay":       round(current_delay, 4),
        })

    # Write CSV
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows_out)

    # --- Summary ---
    n      = len(rows_out)
    delays = [r["current_delay"] for r in rows_out]

    # Split stats
    train_delays = [r["current_delay"] for r in rows_out if r["day_of_week"] in ("Monday","Tuesday","Wednesday","Thursday","Saturday")]
    test_delays  = [r["current_delay"] for r in rows_out if r["day_of_week"] in ("Friday","Sunday")]

    print()
    print("=" * 60)
    print("CURRENT DELAY COMPUTATION SUMMARY")
    print("=" * 60)
    print(f"Total events fetched:           {len(events)}")
    print(f"Skipped — unknown day_type:     {no_day_type}")
    print(f"Skipped — no stats match:       {no_stats_match}")
    print(f"Successfully computed:          {n}")
    print(f"  TRAIN rows: {len(train_delays)}")
    print(f"  TEST  rows: {len(test_delays)}")
    print()
    if train_delays:
        print(f"TRAIN current_delay stats:")
        print(f"  Mean   : {statistics.mean(train_delays):.2f}s")
        print(f"  Median : {statistics.median(train_delays):.2f}s")
        print(f"  Std    : {statistics.stdev(train_delays):.2f}s")
        print(f"  Min    : {min(train_delays):.2f}s")
        print(f"  Max    : {max(train_delays):.2f}s")
    if test_delays:
        print()
        print(f"TEST current_delay stats:")
        print(f"  Mean   : {statistics.mean(test_delays):.2f}s")
        print(f"  Median : {statistics.median(test_delays):.2f}s")
        print(f"  Std    : {statistics.stdev(test_delays):.2f}s")
        print(f"  Min    : {min(test_delays):.2f}s")
        print(f"  Max    : {max(test_delays):.2f}s")
    print()

    # SANITY CHECK: no elapsed > 2x avg (was a mass violation before)
    violations = sum(1 for r in rows_out if abs(r["current_delay"]) > 2 * r["avg_travel_time"])
    pct_viol = violations / n * 100 if n > 0 else 0
    print(f"Sanity check — |delay| > 2×avg_travel_time: {violations}/{n} ({pct_viol:.1f}%)")

    # DISTRIBUTION SIMILARITY CHECK
    if train_delays and test_delays:
        train_mean = statistics.mean(train_delays)
        test_mean  = statistics.mean(test_delays)
        train_std  = statistics.stdev(train_delays)
        test_std   = statistics.stdev(test_delays)
        mean_diff  = abs(train_mean - test_mean)
        std_diff   = abs(train_std - test_std)
        print()
        print("Distribution similarity (train vs test):")
        print(f"  Mean diff : {mean_diff:.2f}s  {'[OK]' if mean_diff < 30 else '[CHECK]'}")
        print(f"  Std  diff : {std_diff:.2f}s  {'[OK]' if std_diff < 30 else '[CHECK]'}")

    print(f"\nOutput: {OUTPUT_FILE}")
    # --- KHALED EDIT END ---


if __name__ == "__main__":
    main()