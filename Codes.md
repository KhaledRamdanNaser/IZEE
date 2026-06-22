1) Vehicle State Engine:{
   from vehicle_state.matcher import find_nearest_segment, project_point_on_segment
from vehicle_state.matcher import haversine_distance
from vehicle_state.movement import determine_movement_state
from vehicle_state.movement import determine_direction
from vehicle_state.utils import stabilize_progress
from vehicle_state.utils import determine_confidence
from vehicle_state.validation import validate_vehicle_state
from vehicle_state.transition_tracker import (
    update_operational_memory
)
def process_observation(observation, previous_state, route_reference):

    # 1️⃣ Extract GPS
    lat = observation["location"]["lat"]
    lon = observation["location"]["lon"]

    # 2️⃣ Find nearest segment
    segment = find_nearest_segment(lat, lon, route_reference["segments"])
    print("MATCHED SEGMENT:", segment)
    
    segments = route_reference["segments"]
    segment_index = segments.index(segment)
    total_segments = len(segments)
    

    # 3️⃣ Project onto segment
    start = segment["start"]
    end = segment["end"]

    proj_lat, proj_lon, t = project_point_on_segment(
        lat, lon,
        start["lat"], start["lon"],
        end["lat"], end["lon"]
    )
# AFTER projection
    raw_progress = (segment_index + t) / total_segments

    route_progress = stabilize_progress(
    raw_progress,
    previous_state
)
# 3.5️⃣ Determine next stop
    next_stop_id = end["stop_id"]
# Calculate Distance to next stop
    distance = haversine_distance(
    proj_lat, proj_lon,
    end["lat"], end["lon"]
)
    print("DISTANCE TO NEXT STOP:", distance)
    print("NEXT STOP:", next_stop_id)
#Movement State
    movement_state = determine_movement_state(
    observation["vehicle_id"],
    distance,
    observation["speed"],
    t,
    previous_state
)
    direction = determine_direction(
    route_progress,
    previous_state
)
    current_stop_id = None

    if movement_state == "at_stop":
        current_stop_id = next_stop_id

    confidence = determine_confidence(observation)
    # 🔥 continuously update operational continuity memory
    update_operational_memory(
        observation["vehicle_id"],
        distance,
        t
    )
# 4️⃣ Build vehicle state
    vehicle_state = {   
        "vehicle_id": observation["vehicle_id"],
        "route_id": route_reference["route_id"],
        "trip_id": None,
        "timestamp": observation["timestamp"],

        "matched_position": {
            "lat": proj_lat,
            "lon": proj_lon
        },

        "current_stop_id": current_stop_id,
        "next_stop_id": next_stop_id,
        "stop_sequence": end["sequence"],

        "segment_id": segment["segment_id"],
        "segment_progress": t,
        "progress": route_progress,

        "distance_to_next_stop": distance,

        "speed": observation["speed"],
        "direction": direction,

        "movement": "moving" if observation["speed"] > 0 else "stopped",
        "movement_state": movement_state,

        "current_delay": observation.get("current_delay", 0),
        "confidence": confidence,

        "source": observation["source"],
        "simulation_flag": observation["simulation_flag"]
    }

    vehicle_state = validate_vehicle_state(
    vehicle_state,
    previous_state
)

    return vehicle_state
}
vehicle_state/matcher.py:{
   import math


def distance_point_to_segment(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.hypot(px - closest_x, py - closest_y)


def find_nearest_segment(lat, lon, segments):
    min_distance = float("inf")
    best_segment = None

    for seg in segments:
        start = seg["start"]
        end = seg["end"]

        d = distance_point_to_segment(
            lat, lon,
            start["lat"], start["lon"],
            end["lat"], end["lon"]
        )

        if d < min_distance:
            min_distance = d
            best_segment = seg

    return best_segment





def project_point_on_segment(px, py, x1, y1, x2, y2):
    """
    Projects point (px, py) onto segment (x1,y1) → (x2,y2)

    Returns:
    - projected point (lat, lon)
    - t (progress along segment 0 → 1)
    """

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return (x1, y1, 0)

    # projection factor
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)

    # clamp between 0 and 1
    t = max(0, min(1, t))

    # projected point
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return (proj_x, proj_y, t)
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
}

2) Current Vehicle State persistence
models/vehicle_live_state.py:{
   from sqlalchemy import Column, String, Float, Integer, Boolean
from database.connection import Base

class VehicleLiveState(Base):
    __tablename__ = "vehicle_live_state"

    vehicle_id = Column(String, primary_key=True, index=True)
    route_id = Column(String)

    timestamp = Column(String)

    matched_lat = Column(Float)
    matched_lon = Column(Float)

    current_stop_id = Column(String, nullable=True)
    next_stop_id = Column(String)

    stop_sequence = Column(Integer, nullable=True)

    segment_id = Column(String)
    segment_progress = Column(Float)
    progress = Column(Float)

    distance_to_next_stop = Column(Float)

    speed = Column(Float)
    direction = Column(String)

    movement = Column(String)
    movement_state = Column(String)

    current_delay = Column(Float)
    confidence = Column(String)

    source = Column(String)
    simulation_flag = Column(Boolean)
}

3) Segment Statistics implementation
segment_stats.py:{
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
}
transit events.py:{
   from sqlalchemy import Column, String, Integer, Boolean, JSON
from database.connection import Base

class TransitEvent(Base):
    __tablename__ = "transit_events"

    event_id = Column(String, primary_key=True, index=True)

    event_type = Column(String, index=True)

    vehicle_id = Column(String, index=True)
    route_id = Column(String, index=True)  # keep String if your routes are strings like "CTA_M_112"

    timestamp = Column(String, index=True)  # ISO8601 OK for now

    # Optional IDs — keep as String if your stop_ids are strings
    stop_id = Column(String, nullable=True)
    from_stop_id = Column(String, nullable=True)
    to_stop_id = Column(String, nullable=True)
    segment_id = Column(String, nullable=True)

    # ⚠️ was Float before — should be Integer
    stop_sequence = Column(Integer, nullable=True)

    # Flexible metrics
    metrics = Column(JSON)

    confidence = Column(String)
    source = Column(String)
    simulation_flag = Column(Boolean)

    # --- KHALED EDIT START ---
    day_of_week = Column(String, nullable=True)
    time_period  = Column(String, nullable=True)
    direction    = Column(Integer, nullable=True)
    # --- KHALED EDIT END ---
}
4) Current ETA feature generation
feature_engineering.py:{
   """
scripts/feature_engineering.py

IZEE ETA ENGINE — Feature Engineering Pipeline
===============================================
Produces:
    scripts/feature_data/train_features.csv
    scripts/feature_data/test_features.csv

Blueprint rules enforced:
  - One ML row = one segment_completed event
  - Label     = metrics.travel_time (seconds)
  - TRAIN days: Monday, Tuesday, Wednesday, Thursday, Saturday
  - TEST  days: Friday, Sunday
  - LabelEncoder fitted on TRAIN only; unseen TEST values → -1
  - current_delay: actual_travel_time - avg_travel_time (TRAIN and TEST alike)
    No fallback to 0.0 — compute_current_delay.py covers all days.
  - SEGMENT_MERGE_MAP applied before every lookup
  - segment_length_m = haversine(from_stop, to_stop)
  - No vehicle_state / traversal / dwell / segment_transition logic
"""

# --- KHALED EDIT START ---
import os
import sys
import math
import csv

# Force UTF-8 output on Windows terminals to avoid cp1252 encode errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text

from database.connection import SessionLocal
from scripts.segment_stats import SEGMENT_MERGE_MAP, DAY_TYPE_MAP

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "feature_data")
TRAIN_CSV    = os.path.join(OUTPUT_DIR, "train_features.csv")
TEST_CSV     = os.path.join(OUTPUT_DIR, "test_features.csv")
DELAY_CSV    = os.path.join(OUTPUT_DIR, "current_delay.csv")

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
TRAIN_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Saturday"}
TEST_DAYS  = {"Friday", "Sunday"}

# Encoding: Monday=0 … Sunday=6  (ISO weekday order)
DAY_ENCODE = {
    "Monday":    0,
    "Tuesday":   1,
    "Wednesday": 2,
    "Thursday":  3,
    "Friday":    4,
    "Saturday":  5,
    "Sunday":    6,
}

# Final column order expected in output CSVs
FEATURE_COLUMNS = [
    "hour",
    "avg_segment_time",
    "current_delay",
    "day_of_week_encoded",
    "is_peak",
    "segment_id_encoded",
    "route_id_encoded",
    "std_travel_time",
    "stop_sequence",
    "segment_length_m",
    "travel_time",          # label — always last
]

UNSEEN_LABEL = -1

# ---------------------------------------------------------------------------
# FAIL CONDITIONS THRESHOLDS
# ---------------------------------------------------------------------------
MAX_MISSING_AVG_SEGMENT_PCT = 0.05   # 5 %


# ===========================================================================
# STEP 1 — HAVERSINE HELPER
# ===========================================================================
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two (lat, lon) points."""
    R = 6_371_000.0                          # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ===========================================================================
# STEP 2 — LABEL-ENCODER (fit on TRAIN, unseen → -1)
# ===========================================================================
class SafeLabelEncoder:
    """
    Lightweight label encoder.
    fit()     : build int mapping from a list of values
    transform(): return encoded int, or UNSEEN_LABEL for unknown values
    """
    def __init__(self):
        self._map: dict = {}
        self._fitted = False

    def fit(self, values):
        unique_sorted = sorted(set(str(v) for v in values))
        self._map = {v: i for i, v in enumerate(unique_sorted)}
        self._fitted = True

    def transform(self, value) -> int:
        return self._map.get(str(value), UNSEEN_LABEL)

    def unseen_count(self, values) -> int:
        return sum(1 for v in values if str(v) not in self._map)


# ===========================================================================
# STEP 3 — DATABASE LOADERS
# ===========================================================================
def load_segment_events(db) -> list[dict]:
    """
    Fetch ALL segment_completed events needed for both TRAIN and TEST.
    Columns returned: event_id, vehicle_id, route_id, direction,
                      segment_id, from_stop_id, to_stop_id,
                      stop_sequence, day_of_week, time_period,
                      timestamp, travel_time
    """
    result = db.execute(text("""
        SELECT
            event_id,
            vehicle_id,
            route_id,
            direction,
            segment_id,
            from_stop_id,
            to_stop_id,
            stop_sequence,
            day_of_week,
            time_period,
            timestamp,
            (metrics->>'travel_time')::float AS travel_time
        FROM transit_events
        WHERE event_type = 'segment_completed'
        AND (metrics->>'travel_time') IS NOT NULL
        AND day_of_week IN (
            'Monday','Tuesday','Wednesday','Thursday','Saturday',
            'Friday','Sunday'
        )
        ORDER BY timestamp
    """))

    rows = []
    for r in result.fetchall():
        rows.append({
            "event_id":      r[0],
            "vehicle_id":    r[1],
            "route_id":      r[2],
            "direction":     int(r[3]) if r[3] is not None else None,
            "segment_id":    r[4],
            "from_stop_id":  r[5],
            "to_stop_id":    r[6],
            "stop_sequence": int(r[7]) if r[7] is not None else None,
            "day_of_week":   r[8],
            "time_period":   r[9],
            "timestamp":     r[10],
            "travel_time":   float(r[11]),
        })
    return rows


def load_stop_coords(db) -> dict:
    """
    Returns dict[stop_id -> (lat, lon)] from the GTFS stop table.
    """
    result = db.execute(text("""
        SELECT stop_id, lat, lon
        FROM stop
        WHERE lat IS NOT NULL AND lon IS NOT NULL
    """))
    return {str(r[0]): (float(r[1]), float(r[2])) for r in result.fetchall()}


def load_segment_statistics(db) -> dict:
    """
    Returns dict keyed by (segment_id, route_id, direction, day_type, time_period)
    → {"avg_travel_time": float, "std_travel_time": float}
    """
    result = db.execute(text("""
        SELECT segment_id, route_id, direction,
               day_type, time_period,
               avg_travel_time, std_travel_time
        FROM segment_statistics
    """))
    stats = {}
    for r in result.fetchall():
        key = (str(r[0]), str(r[1]), int(r[2]), str(r[3]), str(r[4]))
        stats[key] = {
            "avg_travel_time": float(r[5]) if r[5] is not None else None,
            "std_travel_time": float(r[6]) if r[6] is not None else None,
        }
    return stats


# ===========================================================================
# STEP 4 — CURRENT DELAY LOADER
# ===========================================================================
def load_current_delay() -> dict:
    """
    Load current_delay.csv → dict[event_id -> float current_delay].
    Missing values are filled with 0.0 per blueprint rule.
    """
    delay_map = {}
    if not os.path.exists(DELAY_CSV):
        print(f"  WARNING: {DELAY_CSV} not found — all current_delay will be 0.0")
        return delay_map

    with open(DELAY_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get("event_id", "").strip()
            val = row.get("current_delay", "").strip()
            if eid:
                try:
                    delay_map[eid] = float(val)
                except (ValueError, TypeError):
                    delay_map[eid] = 0.0

    print(f"  current_delay entries loaded: {len(delay_map)}")
    return delay_map


# ===========================================================================
# STEP 5 — SEGMENT LENGTH via STOP COORDS
# ===========================================================================
# --- KHALED EDIT START ---
def compute_segment_length(segment_id: str, stop_coords: dict) -> float | None:
    """
    Haversine distance between from_stop and to_stop in metres, extracted from segment_id.
    Returns None if either stop is missing from GTFS.
    """
    if not segment_id or "_" not in segment_id:
        return None
    parts = segment_id.split("_")
    if len(parts) < 2:
        return None
    from_stop_id = parts[0]
    to_stop_id   = parts[1]
    from_coords = stop_coords.get(str(from_stop_id))
    to_coords   = stop_coords.get(str(to_stop_id))
    if from_coords is None or to_coords is None:
        return None
    return haversine_m(from_coords[0], from_coords[1],
                       to_coords[0],   to_coords[1])
# --- KHALED EDIT END ---


# ===========================================================================
# STEP 6 — SEGMENT MERGE MAP APPLICATOR
# ===========================================================================
def apply_merge_map(segment_id: str, route_id: str, direction: int) -> str:
    """
    Return merged segment_id if a mapping exists, else original.
    Applied BEFORE every lookup per blueprint §8.
    """
    sub = SEGMENT_MERGE_MAP.get((route_id, direction))
    if sub is None:
        return segment_id
    return sub.get(segment_id, segment_id)


# ===========================================================================
# STEP 7 — PARSE HOUR FROM TIMESTAMP
# ===========================================================================
def parse_hour(timestamp_str: str) -> int | None:
    """Extract hour (0–23) from ISO8601 timestamp string."""
    try:
        # Handles 'YYYY-MM-DDTHH:MM:SS' and 'YYYY-MM-DD HH:MM:SS'
        ts = timestamp_str.replace("T", " ")
        return int(ts.split(" ")[1].split(":")[0])
    except (IndexError, ValueError, AttributeError):
        return None


# ===========================================================================
# STEP 8 — BUILD FEATURE ROWS
# ===========================================================================
def build_feature_rows(
    events: list[dict],
    stop_coords: dict,
    seg_stats: dict,
    delay_map: dict,
    split: str,                # "train" or "test"
) -> list[dict]:
    """
    Convert raw events into feature dicts.
    Blueprint rules strictly applied:
      - current_delay: use computed value for TRAIN, 0.0 for TEST
      - SEGMENT_MERGE_MAP applied before stats lookup
      - Remove negative travel_time (cleaning rule)
      - Remove zero travel_time (cleaning rule §11)
    """
    rows = []

    for ev in events:
        travel_time  = ev["travel_time"]

        # CLEANING — skip negative or zero travel_time
        if travel_time is None or travel_time <= 0:
            continue

        route_id     = ev["route_id"]
        direction    = ev["direction"]
        segment_id   = ev["segment_id"]
        day_of_week  = ev["day_of_week"]
        time_period  = ev["time_period"]
        timestamp    = ev["timestamp"]
        from_stop    = ev["from_stop_id"]
        to_stop      = ev["to_stop_id"]
        stop_seq     = ev["stop_sequence"]

        # --- TEMPORAL FEATURES ---
        hour = parse_hour(str(timestamp))
        if hour is None:
            continue

        day_of_week_encoded = DAY_ENCODE.get(day_of_week)
        if day_of_week_encoded is None:
            continue

        is_peak = 1 if str(time_period).lower() == "peak" else 0

        # --- SEGMENT MERGE (must happen before any lookup) ---
        merged_segment_id = apply_merge_map(segment_id, route_id, direction)

        # --- STATS LOOKUP ---
        day_type  = DAY_TYPE_MAP.get(day_of_week)
        stats_key = (merged_segment_id, route_id, direction, day_type, time_period)
        seg_entry = seg_stats.get(stats_key)

        avg_segment_time = None
        std_travel_time  = None
        if seg_entry is not None:
            avg_segment_time = seg_entry.get("avg_travel_time")
            std_travel_time  = seg_entry.get("std_travel_time")

        # --- SEGMENT LENGTH ---
        # --- KHALED EDIT START ---
        segment_length_m = compute_segment_length(merged_segment_id, stop_coords)
        # --- KHALED EDIT END ---

        # --- CURRENT DELAY ---
        # --- KHALED EDIT START ---
        # current_delay is now computed identically for TRAIN and TEST.
        # compute_current_delay.py covers all days using the correct formula:
        #   current_delay = actual_travel_time - avg_travel_time
        # This is the offline instantiation of the design formula at segment_progress=1.0.
        # Fallback to 0.0 only when the event has no matching segment_statistics cell.
        current_delay = delay_map.get(ev["event_id"], 0.0)
        # --- KHALED EDIT END ---

        rows.append({
            "event_id":            ev["event_id"],   # kept internally for dedup check
            "hour":                hour,
            "avg_segment_time":    avg_segment_time,
            "current_delay":       current_delay,
            "day_of_week_encoded": day_of_week_encoded,
            "is_peak":             is_peak,
            "segment_id_raw":      merged_segment_id,   # raw value before encoding
            "route_id_raw":        route_id,            # raw value before encoding
            "std_travel_time":     std_travel_time,
            "stop_sequence":       stop_seq,
            "segment_length_m":    segment_length_m,
            "travel_time":         travel_time,
        })

    return rows


# ===========================================================================
# STEP 9 — LABEL ENCODING (fit on TRAIN, apply to TRAIN + TEST)
# ===========================================================================
def encode_ids(
    train_rows: list[dict],
    test_rows:  list[dict],
) -> tuple[list[dict], list[dict], dict]:
    """
    Fit SafeLabelEncoder on TRAIN segment_id and route_id.
    Apply to both splits; unseen TEST values → -1.
    Returns (train_rows_encoded, test_rows_encoded, encoders_dict).
    """
    seg_enc   = SafeLabelEncoder()
    route_enc = SafeLabelEncoder()

    seg_enc.fit([r["segment_id_raw"] for r in train_rows])
    route_enc.fit([r["route_id_raw"]  for r in train_rows])

    def apply_enc(rows, split_name):
        out = []
        unseen_seg   = 0
        unseen_route = 0
        for r in rows:
            seg_encoded   = seg_enc.transform(r["segment_id_raw"])
            route_encoded = route_enc.transform(r["route_id_raw"])
            if seg_encoded   == UNSEEN_LABEL: unseen_seg   += 1
            if route_encoded == UNSEEN_LABEL: unseen_route += 1
            new_r = dict(r)
            new_r["segment_id_encoded"] = seg_encoded
            new_r["route_id_encoded"]   = route_encoded
            out.append(new_r)
        print(f"  [{split_name}] unseen segment_id: {unseen_seg} | "
              f"unseen route_id: {unseen_route}")
        return out, unseen_seg + unseen_route

    train_enc, _  = apply_enc(train_rows, "TRAIN")
    test_enc, test_unseen = apply_enc(test_rows,  "TEST")

    return train_enc, test_enc, {
        "segment_encoder": seg_enc,
        "route_encoder":   route_enc,
        "test_unseen_count": test_unseen,
    }


# ===========================================================================
# STEP 10 — FAIL CONDITIONS
# ===========================================================================
# --- KHALED EDIT START ---
def fail_conditions_check(train_rows: list[dict], test_rows: list[dict]):
    """Halt script if any blueprint fail condition is triggered."""
    errors = []

    # FC-0: check schema and feature counts
    if len(FEATURE_COLUMNS) != 11:
        errors.append(f"FAIL: Feature count has changed to {len(FEATURE_COLUMNS)} (expected 11)")
    if FEATURE_COLUMNS != [
        "hour",
        "avg_segment_time",
        "current_delay",
        "day_of_week_encoded",
        "is_peak",
        "segment_id_encoded",
        "route_id_encoded",
        "std_travel_time",
        "stop_sequence",
        "segment_length_m",
        "travel_time"
    ]:
        errors.append("FAIL: Schema of FEATURE_COLUMNS has changed!")

    # FC-1: empty split
    if len(train_rows) == 0:
        errors.append("FAIL: TRAIN split is empty.")
    if len(test_rows) == 0:
        errors.append("FAIL: TEST split is empty.")

    # FC-2: negative travel_time (should already be filtered, double-check)
    neg_train = sum(1 for r in train_rows if r["travel_time"] < 0)
    neg_test  = sum(1 for r in test_rows  if r["travel_time"] < 0)
    if neg_train + neg_test > 0:
        errors.append(f"FAIL: Negative travel_time found — TRAIN:{neg_train}, TEST:{neg_test}.")

    # FC-3: >5% missing avg_segment_time in TRAIN
    if train_rows:
        missing_avg = sum(1 for r in train_rows if r["avg_segment_time"] is None)
        pct = missing_avg / len(train_rows)
        if pct > MAX_MISSING_AVG_SEGMENT_PCT:
            errors.append(
                f"FAIL: {pct:.1%} of TRAIN rows missing avg_segment_time "
                f"(threshold 5%). Missing={missing_avg}/{len(train_rows)}."
            )

    # FC-4: duplicate event_id in output
    train_eids = [r["event_id"] for r in train_rows]
    test_eids  = [r["event_id"] for r in test_rows]
    train_dups = len(train_eids) - len(set(train_eids))
    test_dups  = len(test_eids)  - len(set(test_eids))
    if train_dups > 0:
        errors.append(f"FAIL: {train_dups} duplicate event_id(s) in TRAIN output.")
    if test_dups > 0:
        errors.append(f"FAIL: {test_dups} duplicate event_id(s) in TEST output.")

    # FC-5: segment_length_m zeros > 5%
    zeros_train = sum(1 for r in train_rows if r.get("segment_length_m") == 0.0)
    zeros_test  = sum(1 for r in test_rows  if r.get("segment_length_m") == 0.0)
    pct_train = (zeros_train / len(train_rows)) if train_rows else 0.0
    pct_test  = (zeros_test / len(test_rows)) if test_rows else 0.0
    if pct_train > 0.05:
        errors.append(f"FAIL: TRAIN segment_length_m has {pct_train:.2%} zeros (exceeds 5% threshold).")
    if pct_test > 0.05:
        errors.append(f"FAIL: TEST segment_length_m has {pct_test:.2%} zeros (exceeds 5% threshold).")

    # FC-6: NaN values introduced
    for r in train_rows + test_rows:
        for col in FEATURE_COLUMNS:
            val = r.get(col)
            if val is None and col not in ["avg_segment_time", "std_travel_time"]:
                errors.append(f"FAIL: None value found in required feature '{col}'")
                break
            if isinstance(val, float) and math.isnan(val):
                errors.append(f"FAIL: NaN value found in feature '{col}'")
                break

    if errors:
# --- KHALED EDIT END ---
        print()
        print("=" * 60)
        print("PIPELINE HALTED — FAIL CONDITIONS TRIGGERED")
        print("=" * 60)
        for e in errors:
            print(f"  {e}")
        sys.exit(1)


# ===========================================================================
# STEP 11 — SAVE CSVs
# ===========================================================================
def save_csv(rows: list[dict], path: str):
    """Write feature rows to CSV using the canonical FEATURE_COLUMNS order."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ===========================================================================
# STEP 12 — VALIDATION REPORT
# ===========================================================================
def validation_report(
    train_rows: list[dict],
    test_rows:  list[dict],
    test_unseen_count: int,
):
    """Print the full validation report required by the blueprint."""
    print()
    print("=" * 65)
    print("FEATURE ENGINEERING VALIDATION REPORT")
    print("=" * 65)

    # 1. Row counts
    print(f"\n1. ROW COUNTS")
    print(f"   TRAIN rows : {len(train_rows):,}")
    print(f"   TEST  rows : {len(test_rows):,}")

    # 2. Missing values per feature (TRAIN)
    print(f"\n2. MISSING VALUES PER FEATURE (TRAIN)")
    feature_fields = FEATURE_COLUMNS[:-1]   # exclude label
    for col in feature_fields:
        missing = sum(1 for r in train_rows if r.get(col) is None)
        pct     = (missing / len(train_rows) * 100) if train_rows else 0
        print(f"   {col:<25} missing={missing:>6}  ({pct:.2f}%)")

    print(f"\n2b. MISSING VALUES PER FEATURE (TEST)")
    for col in feature_fields:
        missing = sum(1 for r in test_rows if r.get(col) is None)
        pct     = (missing / len(test_rows) * 100) if test_rows else 0
        print(f"   {col:<25} missing={missing:>6}  ({pct:.2f}%)")

    # 3. travel_time stats
    def tt_stats(rows):
        vals = [r["travel_time"] for r in rows]
        if not vals:
            return "N/A", "N/A", "N/A"
        return min(vals), max(vals), sum(vals) / len(vals)

    print(f"\n3. TRAVEL_TIME STATS")
    t_min, t_max, t_mean = tt_stats(train_rows)
    print(f"   TRAIN — min={t_min:.2f}s  max={t_max:.2f}s  mean={t_mean:.2f}s")
    t_min, t_max, t_mean = tt_stats(test_rows)
    print(f"   TEST  — min={t_min:.2f}s  max={t_max:.2f}s  mean={t_mean:.2f}s")

    # 4. current_delay = 0.0 percentage
    def zero_delay_pct(rows):
        if not rows: return 0.0
        n = sum(1 for r in rows if r.get("current_delay", -999) == 0.0)
        return n / len(rows) * 100

    print(f"\n4. CURRENT_DELAY = 0.0 PERCENTAGE")
    print(f"   TRAIN : {zero_delay_pct(train_rows):.2f}%")
    print(f"   TEST  : {zero_delay_pct(test_rows):.2f}%  (should be similar to TRAIN — same formula)")

    # 5. Unseen labels encoded as -1
    print(f"\n5. UNSEEN LABELS ENCODED AS -1")
    print(f"   Count (TEST segment_id + route_id unseen) : {test_unseen_count}")

    # 6. Duplicate event_id check
    train_dup = len([r["event_id"] for r in train_rows]) - len(
        set(r["event_id"] for r in train_rows))
    test_dup  = len([r["event_id"] for r in test_rows])  - len(
        set(r["event_id"] for r in test_rows))
    print(f"\n6. DUPLICATE event_id CHECK")
    print(f"   TRAIN duplicates : {train_dup}  {'[PASS]' if train_dup == 0 else '[FAIL]'}")
    print(f"   TEST  duplicates : {test_dup}   {'[PASS]' if test_dup  == 0 else '[FAIL]'}")

    # --- KHALED EDIT START ---
    # 7. Segment Length Stats
    def length_stats(rows):
        vals = [r["segment_length_m"] for r in rows if r.get("segment_length_m") is not None]
        if not vals:
            return 0.0, 0.0, 0.0, 0.0
        zeros = sum(1 for v in vals if v == 0.0)
        pct_zero = (zeros / len(vals)) * 100
        
        # calculate median
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        if n % 2 == 1:
            med = sorted_vals[n // 2]
        else:
            med = (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0
            
        return pct_zero, min(vals), med, max(vals)

    print(f"\n7. SEGMENT_LENGTH_M STATS")
    z_pct, l_min, l_med, l_max = length_stats(train_rows)
    print(f"   TRAIN — % == 0: {z_pct:.2f}%  min={l_min:.2f}m  median={l_med:.2f}m  max={l_max:.2f}m")
    z_pct, l_min, l_med, l_max = length_stats(test_rows)
    print(f"   TEST  — % == 0: {z_pct:.2f}%  min={l_min:.2f}m  median={l_med:.2f}m  max={l_max:.2f}m")

    # 8. Schema validation check
    print(f"\n8. SCHEMA AND NAN VERIFICATION")
    for name, path in [("TRAIN", TRAIN_CSV), ("TEST", TEST_CSV)]:
        if os.path.exists(path):
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                if header == FEATURE_COLUMNS:
                    print(f"   {name} CSV schema: columns match exactly. [PASS]")
                    print(f"   {name} CSV feature count: {len(header)} columns. [PASS]")
                else:
                    print(f"   {name} CSV schema mismatch! [FAIL] Expected: {FEATURE_COLUMNS}, Got: {header}")
        else:
            print(f"   {name} CSV not found. [FAIL]")

    for name, rows in [("TRAIN", train_rows), ("TEST", test_rows)]:
        nan_count = 0
        for r in rows:
            for col in FEATURE_COLUMNS:
                if col in ["avg_segment_time", "std_travel_time"]:
                    continue
                val = r.get(col)
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    nan_count += 1
        if nan_count == 0:
            print(f"   {name} features: No NaN/None values in required columns. [PASS]")
        else:
            print(f"   {name} features: Found {nan_count} NaN/None values in required columns! [FAIL]")

    print()
    print("=" * 65)
    print("PIPELINE COMPLETE")
    print(f"  TRAIN -> {TRAIN_CSV}")
    print(f"  TEST  -> {TEST_CSV}")
    print("=" * 65)
    # --- KHALED EDIT END ---


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 65)
    print("IZEE ETA ENGINE — Feature Engineering Pipeline")
    print("=" * 65)

    # ------------------------------------------------------------------
    # DB session
    # ------------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db = SessionLocal()
    try:
        print("\n[1/5] Loading segment_completed events from DB...")
        all_events = load_segment_events(db)
        print(f"  Total raw events fetched: {len(all_events):,}")

        print("\n[2/5] Loading GTFS stop coordinates...")
        stop_coords = load_stop_coords(db)
        print(f"  Stops with coordinates: {len(stop_coords):,}")

        print("\n[3/5] Loading segment_statistics...")
        seg_stats = load_segment_statistics(db)
        print(f"  Stat cells loaded: {len(seg_stats):,}")

    finally:
        db.close()

    print("\n[4/5] Loading current_delay.csv...")
    delay_map = load_current_delay()

    # ------------------------------------------------------------------
    # SPLIT by day_of_week (deterministic, no random)
    # ------------------------------------------------------------------
    raw_train = [e for e in all_events if e["day_of_week"] in TRAIN_DAYS]
    raw_test  = [e for e in all_events if e["day_of_week"] in TEST_DAYS]
    print(f"\n  Day-based split -> TRAIN: {len(raw_train):,}  TEST: {len(raw_test):,}")

    # ------------------------------------------------------------------
    # Build feature rows
    # ------------------------------------------------------------------
    print("\n[5/5] Building feature rows...")
    train_rows = build_feature_rows(raw_train, stop_coords, seg_stats, delay_map, split="train")
    test_rows  = build_feature_rows(raw_test,  stop_coords, seg_stats, delay_map, split="test")
    print(f"  Feature rows built -> TRAIN: {len(train_rows):,}  TEST: {len(test_rows):,}")

    # ------------------------------------------------------------------
    # Label encoding (fit ONLY on TRAIN)
    # ------------------------------------------------------------------
    print("\n  Encoding segment_id and route_id (fit on TRAIN only)...")
    train_rows, test_rows, enc_info = encode_ids(train_rows, test_rows)

    # ------------------------------------------------------------------
    # Fail conditions
    # ------------------------------------------------------------------
    print("\n  Checking fail conditions...")
    fail_conditions_check(train_rows, test_rows)
    print("  All fail conditions passed [OK]")

    # ------------------------------------------------------------------
    # Save CSVs
    # ------------------------------------------------------------------
    save_csv(train_rows, TRAIN_CSV)
    save_csv(test_rows,  TEST_CSV)
    print(f"\n  Saved: {TRAIN_CSV}")
    print(f"  Saved: {TEST_CSV}")

    # ------------------------------------------------------------------
    # Validation report
    # ------------------------------------------------------------------
    validation_report(train_rows, test_rows, enc_info["test_unseen_count"])


if __name__ == "__main__":
    main()
# --- KHALED EDIT END ---
}

5) Current traversal lifecycle
event_engine/traversal_lifecycle.py:{
   # event_engine/traversal_lifecycle.py

from datetime import datetime

from event_engine.traversal_tracker import (
    start_traversal,
    get_active_traversal,
    clear_traversal
)

from event_engine.builder import build_event


def process_traversal_lifecycle(
    events,
    current_state,
    previous_state,
    route_reference
):
    """
    Process traversal lifecycle timing.

    Responsibilities:
    - traversal start tracking
    - traversal completion tracking
    - segment_completed generation
    """

    generated_events = []

    vehicle_id = current_state.get("vehicle_id")
        # -----------------------------------
    # SEGMENT TRANSITION COMPLETION
    # -----------------------------------

    active_traversal = get_active_traversal(
        vehicle_id
    )

    if (
        active_traversal
        and previous_state
    ):

        stored_segment = active_traversal.get(
            "segment_id"
        )

        current_segment = current_state.get(
            "segment_id"
        )

        if (
            stored_segment
            and current_segment
            and stored_segment != current_segment
        ):

            try:

                t1 = datetime.fromisoformat(
                    active_traversal["departure_time"]
                )

                t2 = datetime.fromisoformat(
                    current_state["timestamp"]
                )

                travel_time = (
                    t2 - t1
                ).total_seconds()
                if travel_time <= 0:

                    clear_traversal(
                        vehicle_id
                    )

                    return generated_events
                                


                raw_segment_completed = {
                    "event_type": "segment_completed",

                    "from_stop_id":
                        active_traversal["from_stop_id"],

                    "to_stop_id":
                        stored_segment.split("_")[1],

                    "segment_id":
                        stored_segment,

                    "metrics": {
                        "travel_time": travel_time,
                        "completion_method":
                            "segment_transition"
                    }
                }


                generated_events.append(
                    build_event(
                        raw_segment_completed,
                        current_state
                    )
                )

            except Exception as e:

                print(
                    "Segment transition completion failed:",
                    e
                )


            clear_traversal(
                vehicle_id
            )


            start_traversal(
                vehicle_id,
                current_segment.split("_")[0],
                current_state.get("timestamp"),
                current_segment
            )
    # -----------------------------------
    # OPERATIONAL TRAVERSAL BOOTSTRAP
    # -----------------------------------

    active_traversal = get_active_traversal(vehicle_id)

    prev_progress = None
    curr_progress = current_state.get("progress")

    if previous_state:
        prev_progress = previous_state.get("progress")

    previous_movement_state = None

    if previous_state:
        previous_movement_state = previous_state.get(
            "movement_state"
        )

    distance_to_stop = current_state.get(
        "distance_to_next_stop",
        999999
    )

    movement_state = current_state.get(
        "movement_state"
    )

    speed = current_state.get("speed", 0)

    # traversal continuity evidence
    has_forward_progress = False

    if (
        prev_progress is not None
        and curr_progress is not None
    ):
        has_forward_progress = (
            curr_progress > prev_progress
        )

    # bootstrap traversal lifecycle
    if (
        not active_traversal
        and previous_state
        and movement_state == "between_stops"
        and previous_movement_state == "between_stops"
        and speed > 5
        and has_forward_progress
        and distance_to_stop > 150
    ):

        print("BOOTSTRAP: traversal lifecycle initialized")

        # -----------------------------------
        # RECONSTRUCT ORIGIN OWNERSHIP
        # -----------------------------------

        current_sequence = current_state.get(
            "stop_sequence"
        )

        origin_stop_id = None

        if current_sequence is not None:

            origin_sequence = current_sequence - 1

            stops_map = route_reference.get(
                "stops_by_sequence",
                {}
            )

            origin_stop = stops_map.get(
                origin_sequence
            )

            if origin_stop:

                origin_stop_id = origin_stop.get(
                    "stop_id"
                )

        # fallback protection
        if not origin_stop_id:

            segment_id = current_state.get(
                "segment_id"
            )

            if segment_id:
                origin_stop_id = segment_id.split("_")[0]

        if origin_stop_id and current_state.get("segment_id"):

            start_traversal(
                vehicle_id,
                origin_stop_id,
                current_state.get("timestamp"),
                current_state.get("segment_id")
            )

    for event in events:

        event_type = event.get("event_type")

        stop_id = event.get("stop_id")

        timestamp = event.get("timestamp")

        # -----------------------------------
        # STOP DEPARTURE
        # -----------------------------------

        if event_type == "stop_departure":

            departure_segment = current_state.get(
                "segment_id"
            )

            if (
                departure_segment
                and not departure_segment.startswith(
                    f"{stop_id}_"
                )
            ):

                departure_segment = None


            if not departure_segment:

                current_sequence = current_state.get(
                    "stop_sequence"
                )

                segments = route_reference.get(
                    "segments",
                    []
                )

                for segment in segments:

                    from_stop_id = (
                        segment.get("from_stop_id")
                        or segment.get("start", {}).get("stop_id")
                    )

                    if from_stop_id == stop_id:

                        departure_segment = segment.get(
                            "segment_id"
                        )

                        break

            if departure_segment:

                start_traversal(
                    vehicle_id,
                    stop_id,
                    timestamp,
                    departure_segment
                )
        # -----------------------------------
        # STOP ARRIVAL
        # -----------------------------------

        elif event_type == "stop_arrival":

            stored = get_active_traversal(
                vehicle_id
            )

            if not stored:
                continue


            if stored["segment_id"] != current_state["segment_id"]:
                clear_traversal(
                    vehicle_id
                )
                continue

            try:

                t1 = datetime.fromisoformat(
                    stored["departure_time"]
                )

                t2 = datetime.fromisoformat(
                    timestamp
                )

                travel_time = (
                    t2 - t1
                ).total_seconds()
                if travel_time <= 0:
                    clear_traversal(vehicle_id)
                    continue

                raw_segment_completed = {
                    "event_type": "segment_completed",

                    "from_stop_id": stored["from_stop_id"],
                    "to_stop_id": stop_id,

                    "segment_id": stored["segment_id"],

                    "metrics": {
                        "travel_time": travel_time,
                        "completion_method": "stop_arrival"
                    }
                }

                full_segment_completed = build_event(
                    raw_segment_completed,
                    current_state
                )

                generated_events.append(
                    full_segment_completed
                )

            except Exception as e:
                print(
                    "Stop arrival completion failed:",
                    e
                )

            clear_traversal(vehicle_id)


    return generated_events
}