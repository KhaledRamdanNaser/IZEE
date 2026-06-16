# --- KHALED EDIT START ---
"""
scripts/segment_stats.py

Aggregates transit_events segment_completed rows into the
segment_statistics table (Option C: 5-column grouping key —
segment_id, route_id, direction, day_type, time_period).

Each run performs a FULL recompute of every grouping cell from the
current transit_events table, then upserts (INSERT ... ON CONFLICT
DO UPDATE) into segment_statistics keyed on the uq_segment_statistics
constraint. This makes the script safe to re-run any number of times
(e.g. after more days are replayed) — re-running always overwrites
each cell with stats computed from ALL currently matching rows, it
never accumulates/double-counts across runs.
"""
# --- KHALED EDIT END ---

import statistics
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import SessionLocal
from models.segment_statistics import SegmentStatistics

# --- KHALED EDIT START ---
DAY_TYPE_MAP = {
    "Monday": "weekday",
    "Tuesday": "weekday",
    "Wednesday": "weekday",
    "Thursday": "weekday",
    "Sunday": "weekday",
    "Friday": "friday",
    "Saturday": "saturday",
}

MIN_SAMPLES = 30
# --- KHALED EDIT END ---


def fetch_segment_completed_rows(db):
    """
    Pull segment_completed rows with a sane travel_time range.
    30s/3600s bounds reject degenerate/runaway segment durations
    that would otherwise skew avg/median/std for a cell.
    """
    # --- KHALED EDIT START ---
    result = db.execute(text("""
        SELECT
            segment_id,
            route_id,
            direction,
            day_of_week,
            time_period,
            (metrics->>'travel_time')::float AS travel_time
        FROM transit_events
        WHERE event_type = 'segment_completed'
        AND (metrics->>'travel_time') IS NOT NULL
        AND (metrics->>'travel_time')::float > 30
        AND (metrics->>'travel_time')::float < 3600
    """))
    return result.fetchall()
    # --- KHALED EDIT END ---


def build_groups(rows):
    """Group travel_time samples by the 5-column Option C key."""
    # --- KHALED EDIT START ---
    groups = defaultdict(list)
    skipped_unknown_day_type = 0

    for row in rows:
        segment_id, route_id, direction, day_of_week, time_period, travel_time = row

        day_type = DAY_TYPE_MAP.get(day_of_week)
        if day_type is None:
            skipped_unknown_day_type += 1
            continue

        key = (segment_id, route_id, direction, day_type, time_period)
        groups[key].append(travel_time)

    if skipped_unknown_day_type:
        print(f"WARNING: skipped {skipped_unknown_day_type} rows with unmapped day_of_week")

    return groups
    # --- KHALED EDIT END ---


def compute_cell_stats(travel_times):
    """avg / median / std / sample_count for one grouping cell."""
    # --- KHALED EDIT START ---
    sample_count = len(travel_times)
    avg_travel_time = statistics.mean(travel_times)
    median_travel_time = statistics.median(travel_times)
    std_travel_time = statistics.stdev(travel_times) if sample_count >= 2 else 0.0

    return {
        "avg_travel_time": avg_travel_time,
        "median_travel_time": median_travel_time,
        "std_travel_time": std_travel_time,
        "sample_count": sample_count,
    }
    # --- KHALED EDIT END ---


def upsert_cells(db, groups):
    """Upsert every computed cell into segment_statistics."""
    # --- KHALED EDIT START ---
    now = datetime.utcnow()
    cells = []

    for key, travel_times in groups.items():
        segment_id, route_id, direction, day_type, time_period = key
        stats = compute_cell_stats(travel_times)

        cells.append({
            "segment_id": segment_id,
            "route_id": route_id,
            "direction": direction,
            "day_type": day_type,
            "time_period": time_period,
            "avg_travel_time": stats["avg_travel_time"],
            "median_travel_time": stats["median_travel_time"],
            "std_travel_time": stats["std_travel_time"],
            "sample_count": stats["sample_count"],
            "last_updated": now,
        })

    if not cells:
        return cells

    stmt = pg_insert(SegmentStatistics).values(cells)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_segment_statistics",
        set_={
            "avg_travel_time": stmt.excluded.avg_travel_time,
            "median_travel_time": stmt.excluded.median_travel_time,
            "std_travel_time": stmt.excluded.std_travel_time,
            "sample_count": stmt.excluded.sample_count,
            "last_updated": stmt.excluded.last_updated,
        }
    )
    db.execute(stmt)
    db.commit()

    return cells
    # --- KHALED EDIT END ---


def print_below_threshold_warning(cells):
    """Print a table of cells under MIN_SAMPLES, if any."""
    # --- KHALED EDIT START ---
    below = [c for c in cells if c["sample_count"] < MIN_SAMPLES]

    if not below:
        return below

    print()
    print("=" * 90)
    print(f"WARNING: {len(below)} cell(s) below the {MIN_SAMPLES}-sample threshold")
    print("=" * 90)
    header = (
        f"{'route_id':<20}{'day_type':<12}{'time_period':<12}"
        f"{'segment_id':<20}{'sample_count':<14}{'samples_needed':<14}"
    )
    print(header)
    print("-" * len(header))

    for c in sorted(below, key=lambda c: c["sample_count"]):
        samples_needed = MIN_SAMPLES - c["sample_count"]
        print(
            f"{c['route_id']:<20}{c['day_type']:<12}{c['time_period']:<12}"
            f"{c['segment_id']:<20}{c['sample_count']:<14}{samples_needed:<14}"
        )

    return below
    # --- KHALED EDIT END ---


def print_summary(cells, below):
    """Final summary stats + Option C verdict."""
    # --- KHALED EDIT START ---
    total_cells = len(cells)
    sample_counts = [c["sample_count"] for c in cells]

    print()
    print("=" * 50)
    print("SEGMENT STATISTICS SUMMARY")
    print("=" * 50)
    print(f"Total cells created: {total_cells}")

    if sample_counts:
        print(f"Min sample_count: {min(sample_counts)}")
        print(f"Max sample_count: {max(sample_counts)}")
        print(f"Avg sample_count: {sum(sample_counts) / total_cells:.2f}")

    print(f"Cells below {MIN_SAMPLES}: {len(below)}")
    print(f"Cells above/at {MIN_SAMPLES}: {total_cells - len(below)}")

    print()
    print("=" * 50)
    if not below:
        print("OPTION C VIABLE — all cells >= 30 samples")
    else:
        print(
            f"OPTION C PARTIALLY BLOCKED — {len(below)} cells below "
            f"threshold (expected on 3-day subset)"
        )
    print("=" * 50)
    # --- KHALED EDIT END ---


def main():
    # --- KHALED EDIT START ---
    db = SessionLocal()
    try:
        rows = fetch_segment_completed_rows(db)
        print(f"Fetched {len(rows)} segment_completed rows (after travel_time filtering)")

        groups = build_groups(rows)
        print(f"Built {len(groups)} grouping cells")

        cells = upsert_cells(db, groups)
        print(f"Upserted {len(cells)} rows into segment_statistics")

        below = print_below_threshold_warning(cells)
        print_summary(cells, below)
    finally:
        db.close()
    # --- KHALED EDIT END ---


if __name__ == "__main__":
    main()
