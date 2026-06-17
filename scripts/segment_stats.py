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

# Route-aware segment merge map for spatial aggregation.
# Groups sparse low-frequency segments into merged super-segments so that
# each cell accumulates enough samples to exceed MIN_SAMPLES.
# Structured as {(route_id, direction): {original_segment_id: merged_segment_id}}.
# Covers CTA_1073, CTA_914, CTA_975, CTA_80, and P_O_14_IG066.
# --- KHALED EDIT START ---
SEGMENT_MERGE_MAP = {
    # CTA_1073 direction 1
    ("CTA_1073", 1): {
        # Zone 0: seq 1+2 (new)
        # --- KHALED EDIT START ---
        "833_95":    "833_1296",
        "95_1296":   "833_1296",
        # --- KHALED EDIT END ---
        # Zone 1: seq 3+4+5
        "1296_2780": "1296_2532",
        "2780_2124": "1296_2532",
        "2124_2532": "1296_2532",
        # Zone 1b: seq 6+7+8 (extended, target updated)
        # --- KHALED EDIT START ---
        "2532_1186": "2532_210",
        "1186_2121": "2532_210",
        "2121_210":  "2532_210",
        # --- KHALED EDIT END ---
        # Zone 1c: seq 9+10
        "210_1328":  "210_717",
        "1328_717":  "210_717",
        # Zone 1d: seq 12+13+14 (new)
        # --- KHALED EDIT START ---
        "717_2296":  "717_715",
        "2296_716":  "717_715",
        "716_715":   "717_715",
        # --- KHALED EDIT END ---
        # Zone 1e+2b: seq 15+16+17+18+19 (merged into 715_125)
        # --- KHALED EDIT START ---
        "715_1327":  "715_125",
        "1327_2299": "715_125",
        "2299_2301": "715_125",
        "2301_365":  "715_125",
        "365_125":   "715_125",
        # --- KHALED EDIT END ---
        # Zone 2: seq 19+20+21
        "125_366":   "125_796",
        "366_2099":  "125_796",
        "2099_796":  "125_796",
        # Zone 3a+3b: seq 23+24+25+26+27 (merged, target updated)
        # --- KHALED EDIT START ---
        "2072_680":  "2072_163",
        "680_165":   "2072_163",
        "165_1335":  "2072_163",
        "1335_1993": "2072_163",
        "1993_163":  "2072_163",
        # Zone 3c+3d: seq 28+29+30+31+32+33+34 (merged, target updated)
        "163_2756":  "163_1961",
        "2756_2085": "163_1961",
        "2085_788":  "163_1961",
        "788_2001":  "163_1961",
        "2001_810":  "163_1961",
        "810_1984":  "163_1961",
        "1984_1961": "163_1961",
        # --- KHALED EDIT END ---
        # Zone 3e: seq 35+36
        "1961_1967": "1961_1970",
        "1967_1970": "1961_1970",
    },
    # CTA_914 direction 0
    ("CTA_914", 0): {
        # D0-Z1: seq 1+2+3+4 (extended, target updated)
        # --- KHALED EDIT START ---
        "212_2128":  "212_2686",
        "2128_2297": "212_2686",
        "2297_2127": "212_2686",
        "2127_2686": "212_2686",
        # D0-Z2: seq 5+6+7
        "2686_30":   "2686_1295",
        "30_2122":   "2686_1295",
        "2122_1295": "2686_1295",
        # D0-Z3: seq 8+9+10+11
        "1295_1313": "1295_731",
        "1313_730":  "1295_731",
        "730_2321":  "1295_731",
        "2321_731":  "1295_731",
        # D0-Z4: seq 12+13+14
        "731_1738":  "731_2010",
        "1738_2011": "731_2010",
        "2011_2010": "731_2010",
        # D0-Z5: seq 15+16+17
        "2010_2008": "2010_2735",
        "2008_2006": "2010_2735",
        "2006_2735": "2010_2735",
        # --- KHALED EDIT END ---
        # D0-Z6: seq 18+19+20 (unchanged)
        "2735_2536": "2735_723",
        "2536_1746": "2735_723",
        "1746_723":  "2735_723",
        # D0-Z7: seq 21+22+23 (extended, target updated)
        # --- KHALED EDIT START ---
        "723_2798":  "723_127",
        "2798_179":  "723_127",
        "179_127":   "723_127",
        # --- KHALED EDIT END ---
        # D0-Z8: seq 24+25+26+27+28 (unchanged)
        "127_689":   "127_2503",
        "689_2754":  "127_2503",
        "2754_2136": "127_2503",
        "2136_2135": "127_2503",
        "2135_2503": "127_2503",
    },
    # CTA_914 direction 1
    ("CTA_914", 1): {
        # D1-Z1: seq 1+2+3+4 (unchanged)
        "2139_2135": "2139_180",
        "2135_2503": "2139_180",
        "2503_120":  "2139_180",
        "120_180":   "2139_180",
        # D1-Z2: seq 5+6+7+8 (extended, target updated)
        # --- KHALED EDIT START ---
        "180_2032":  "180_724",
        "2032_2029": "180_724",
        "2029_725":  "180_724",
        "725_724":   "180_724",
        # --- KHALED EDIT END ---
        # D1-Z3: seq 9+10 (unchanged)
        "724_2030":  "724_457",
        "2030_457":  "724_457",
        # D1-Z4: seq 11+12+13+14 (extended, target updated)
        # --- KHALED EDIT START ---
        "457_459":   "457_2012",
        "459_2007":  "457_2012",
        "2007_2009": "457_2012",
        "2009_2012": "457_2012",
        # --- KHALED EDIT END ---
        # D1-Z5: seq 15+16 (unchanged)
        "2012_2014": "2012_1740",
        "2014_1740": "2012_1740",
        # D1-Z6: seq 17+18 (unchanged)
        "1740_732":  "1740_2320",
        "732_2320":  "1740_2320",
        # D1-Z7: seq 22+23 (unchanged)
        "1314_1312": "1314_728",
        "1312_728":  "1314_728",
        # D1-Z8: seq 25+26 (unchanged)
        "2121_210":  "2121_1328",
        "210_1328":  "2121_1328",
        # D1-Z9: seq 27+28+29 (extended, target updated)
        # --- KHALED EDIT START ---
        "1328_717":  "1328_716",
        "717_2296":  "1328_716",
        "2296_716":  "1328_716",
        # --- KHALED EDIT END ---
    },
    # --- KHALED EDIT START ---
    # CTA_975 direction 0
    ("CTA_975", 0): {
        "1511_114":  "1511_1509",
        "114_1509":  "1511_1509",
        "2816_748":  "2816_749",
        "748_749":   "2816_749",
        "1215_1725": "1215_1219",
        "1725_1219": "1215_1219",
        "2034_2036": "2034_2038",
        "2036_2038": "2034_2038",
        "1841_2017": "1841_2022",
        "2017_2022": "1841_2022",
        "2117_2123": "2117_1297",
        "2123_1297": "2117_1297",
    },
    # CTA_975 direction 1
    ("CTA_975", 1): {
        "1296_2780": "1296_2532",
        "2780_2124": "1296_2532",
        "2124_2532": "1296_2532",
        "2532_1186": "2532_2121",
        "1186_2121": "2532_2121",
        "2121_2122": "2121_1295",
        "2122_1295": "2121_1295",
        "1295_1313": "1295_730",
        "1313_730":  "1295_730",
        "1726_1214": "1726_1720",
        "1214_1720": "1726_1720",
        "1390_2817": "1390_1693",
        "2817_1693": "1390_1693",
        "137_1512":  "137_138",
        "1512_138":  "137_138",
    },
    # P_O_14_IG066 direction 1
    ("P_O_14_IG066", 1): {
        "2484_2807": "2484_2118",
        "2807_2325": "2484_2118",
        "2325_2118": "2484_2118",
        "2118_2250": "2118_2248",
        "2250_2248": "2118_2248",
    },
    # CTA_80 direction 0
    ("CTA_80", 0): {
        "1430_301":  "1430_1121",
        "301_1121":  "1430_1121",
    },
    # CTA_80 direction 1
    ("CTA_80", 1): {
        "283_200":   "283_695",
        "200_695":   "283_695",
        "695_1765":  "695_693",
        "1765_694":  "695_693",
        "694_201":   "695_693",
        "201_693":   "695_693",
    },
    # --- KHALED EDIT END ---
}
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

        # --- KHALED EDIT START ---
        # Apply route-aware segment merge before grouping.
        # Only CTA_1073 and CTA_914 have merge entries; all other routes pass through unchanged.
        merge_key = (route_id, direction)
        if merge_key in SEGMENT_MERGE_MAP:
            segment_id = SEGMENT_MERGE_MAP[merge_key].get(segment_id, segment_id)
        # --- KHALED EDIT END ---

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
            f"threshold"
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
