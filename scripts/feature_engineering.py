"""
scripts/feature_engineering.py

IZEE ETA ENGINE — Feature Engineering Pipeline
===============================================
Produces:
    scripts/feature_data/train_features.csv
    scripts/feature_data/test_features.csv

Blueprint rules enforced:
  - One ML row = one vehicle_state_history snapshot
  - Label source will be transit_events.segment_completed later
  - TRAIN days: Monday, Tuesday, Wednesday, Thursday, Saturday
  - TEST  days: Friday, Sunday
  - LabelEncoder fitted on TRAIN only; unseen TEST values → -1
  - current_delay: temporarily set to 0.0 for migration step
  - SEGMENT_MERGE_MAP applied before every lookup
  - segment_length_m = haversine(from_stop, to_stop)
  - No event-based label logic in this step
"""

# --- KHALED EDIT START ---
import os
import sys
import math
import csv
import datetime

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
    "state_id",
    "timestamp",
    "route_id",
    "direction",
    "segment_id",
    "stop_sequence",
    "segment_progress",
    "speed",
    "hour",
    "day_of_week_encoded",
    "is_peak",
    "avg_segment_time",
    "std_travel_time",
    "segment_length_m",
    "current_delay",
    "segment_id_encoded",
    "route_id_encoded",
    "remaining_time",
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
def parse_timestamp(timestamp_str: str) -> datetime.datetime | None:
    """Parse ISO8601-like timestamp strings into a datetime object."""
    if timestamp_str is None:
        return None
    try:
        return datetime.datetime.fromisoformat(timestamp_str)
    except ValueError:
        try:
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def derive_time_period(dt: datetime.datetime) -> str:
    """Derive a time_period bucket from a datetime timestamp.
    TODO: Replace with schedule-aware buckets or source-aligned logic.
    """
    if dt is None:
        return "off_peak"
    hour = dt.hour
    # Approximate peak windows; preserve existing 'peak' vs other semantics.
    if 6 <= hour < 10 or 15 <= hour < 19:
        return "peak"
    return "off_peak"


def load_vehicle_state_history(db) -> list[dict]:
    """
    Fetch ALL vehicle history snapshots with a valid segment_id.
    Columns returned: state_id, vehicle_id, route_id, direction,
                      timestamp, segment_id, segment_progress,
                      speed, movement_state, stop_sequence,
                      day_of_week, time_period
    """
    result = db.execute(text("""
        SELECT
            state_id,
            vehicle_id,
            route_id,
            direction,
            timestamp,
            segment_id,
            segment_progress,
            speed,
            movement_state,
            stop_sequence
        FROM vehicle_state_history
        WHERE segment_id IS NOT NULL
        ORDER BY timestamp
    """))

    rows = []
    for r in result.fetchall():
        ts = r[4]
        dt = parse_timestamp(ts)
        if dt is None:
            continue
        day_of_week = dt.strftime("%A")
        time_period = derive_time_period(dt)
        rows.append({
            "state_id":         r[0],
            "vehicle_id":       r[1],
            "route_id":         r[2],
            "direction":        int(r[3]) if r[3] is not None else None,
            "timestamp":        ts,
            "segment_id":       r[5],
            "segment_progress": float(r[6]) if r[6] is not None else 0.0,
            "speed":            float(r[7]) if r[7] is not None else 0.0,
            "movement_state":   r[8],
            "stop_sequence":    int(r[9]) if r[9] is not None else None,
            "day_of_week":      day_of_week,
            "time_period":      time_period,
        })
    return rows
# --- SALAH EDIT START ---

def load_segment_completions(db):

    """
    Load completed segment events.

    These are NOT features.

    They are only used to resolve the ML label:
    remaining_segment_time.
    """

    result = db.execute(text("""
        SELECT
            vehicle_id,
            route_id,
            direction,
            segment_id,
            timestamp,
            metrics->>'travel_time'

        FROM transit_events

        WHERE event_type = 'segment_completed'
        AND segment_id IS NOT NULL
        AND metrics->>'travel_time' IS NOT NULL

        ORDER BY timestamp
    """))

    rows = []

    for r in result.fetchall():
        rows.append({
            "vehicle_id": r[0],
            "route_id": r[1],
            "direction": int(r[2]) if r[2] is not None else None,
            "segment_id": r[3],
            "completion_timestamp": r[4],
            "travel_time": r[5],
        })

    return rows
# --- SALAH EDIT END ---
# --- SALAH EDIT START ---

def build_completion_lookup(completions):

    """
    Index completions by vehicle and segment.

    Allows matching:
    snapshot -> future completion
    """

    lookup = {}

    for c in completions:

        merged_segment = apply_merge_map(
            c["segment_id"],
            c["route_id"],
            c["direction"]
        )

        key = (
            c["vehicle_id"],
            merged_segment
        )

        lookup.setdefault(
            key,
            []
        ).append(c)
    for key in lookup:
        lookup[key].sort(
            key=lambda x: parse_timestamp(
                x["completion_timestamp"]
            )
        )    

    return lookup


# --- SALAH EDIT END ---
# --- SALAH EDIT START ---

def resolve_remaining_time(
    state,
    completion_lookup
):

    """
    Find the segment completion after this snapshot.

    Label:
    completion_time - snapshot_time
    """

    key = (
        state["vehicle_id"],
        state["segment_id"]
    )


    candidates = completion_lookup.get(
        key,
        []
    )


    state_time = parse_timestamp(
        state["timestamp"]
    )

    for completion in candidates:

        completion_time = parse_timestamp(
            completion["completion_timestamp"]
        )

        remaining = (
            completion_time - state_time
        ).total_seconds()

        if 0 < remaining < 3600:
            return remaining


    return None

# --- SALAH EDIT END ---


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
    states: list[dict],
    stop_coords: dict,
    seg_stats: dict,
    completion_lookup: dict,
    split: str,                # "train" or "test"
) -> list[dict]:
    """
    Convert vehicle_state_history snapshots into ML feature rows.
    Blueprint rules strictly applied:
      - current_delay: temporarily set to 0.0 for migration
      - SEGMENT_MERGE_MAP applied before stats lookup
      - No event-based label or travel_time dependencies
    """
    rows = []

    for state in states:
        # --- SALAH EDIT START ---
        # Resolve ML label (y)
        # X comes from VehicleStateHistory
        # y comes from future segment_completed event



        # --- SALAH EDIT END ---        
        route_id        = state["route_id"]
        direction       = state["direction"]
        segment_id      = state["segment_id"]
        day_of_week     = state["day_of_week"]
        time_period     = state["time_period"]
        timestamp       = state["timestamp"]
        stop_seq        = state["stop_sequence"]
        segment_progress = state["segment_progress"]
        speed           = state["speed"]

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

        state_for_label = dict(state)

        state_for_label["segment_id"] = merged_segment_id

        remaining_time = resolve_remaining_time(
            state_for_label,
            completion_lookup
        )

        if remaining_time is None:
            continue        

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
        segment_length_m = compute_segment_length(merged_segment_id, stop_coords)

        # --- CURRENT DELAY ---
        current_delay = 0.0  # TODO: Replace with live delay calculation using segment_start_time, segment_progress, and avg_segment_time

        rows.append({
            "state_id":           state["state_id"],
            "timestamp":          timestamp,
            "route_id":           route_id,
            "direction":          direction,
            "segment_id":         merged_segment_id,
            "stop_sequence":      stop_seq,
            "segment_progress":   segment_progress,
            "speed":              speed,
            "hour":               hour,
            "day_of_week_encoded": day_of_week_encoded,
            "is_peak":            is_peak,
            "avg_segment_time":   avg_segment_time,
            "std_travel_time":    std_travel_time,
            "segment_length_m":   segment_length_m,
            "current_delay":      current_delay,
            "segment_id_raw":     merged_segment_id,
            "route_id_raw":       route_id,
            "remaining_time": remaining_time,
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
    expected_columns = [
        "state_id",
        "timestamp",
        "route_id",
        "direction",
        "segment_id",
        "stop_sequence",
        "segment_progress",
        "speed",
        "hour",
        "day_of_week_encoded",
        "is_peak",
        "avg_segment_time",
        "std_travel_time",
        "segment_length_m",
        "current_delay",
        "segment_id_encoded",
        "route_id_encoded",
        "remaining_time",
    ]
    if len(FEATURE_COLUMNS) != len(expected_columns):
        errors.append(f"FAIL: Feature count has changed to {len(FEATURE_COLUMNS)} (expected {len(expected_columns)})")
    if FEATURE_COLUMNS != expected_columns:
        errors.append("FAIL: Schema of FEATURE_COLUMNS has changed!")

    # FC-1: empty split
    if len(train_rows) == 0:
        errors.append("FAIL: TRAIN split is empty.")
    if len(test_rows) == 0:
        errors.append("FAIL: TEST split is empty.")

    # FC-2: >5% missing avg_segment_time in TRAIN
    if train_rows:
        missing_avg = sum(1 for r in train_rows if r["avg_segment_time"] is None)
        pct = missing_avg / len(train_rows)
        if pct > MAX_MISSING_AVG_SEGMENT_PCT:
            errors.append(
                f"FAIL: {pct:.1%} of TRAIN rows missing avg_segment_time "
                f"(threshold 5%). Missing={missing_avg}/{len(train_rows)}."
            )

    # FC-3: duplicate state_id in output
    train_ids = [r["state_id"] for r in train_rows]
    test_ids  = [r["state_id"] for r in test_rows]
    train_dups = len(train_ids) - len(set(train_ids))
    test_dups  = len(test_ids)  - len(set(test_ids))
    if train_dups > 0:
        errors.append(f"FAIL: {train_dups} duplicate state_id(s) in TRAIN output.")
    if test_dups > 0:
        errors.append(f"FAIL: {test_dups} duplicate state_id(s) in TEST output.")

    # FC-4: >5% missing avg_segment_time in TRAIN
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
    feature_fields = FEATURE_COLUMNS
    for col in feature_fields:
        missing = sum(1 for r in train_rows if r.get(col) is None)
        pct     = (missing / len(train_rows) * 100) if train_rows else 0
        print(f"   {col:<25} missing={missing:>6}  ({pct:.2f}%)")

    print(f"\n2b. MISSING VALUES PER FEATURE (TEST)")
    for col in feature_fields:
        missing = sum(1 for r in test_rows if r.get(col) is None)
        pct     = (missing / len(test_rows) * 100) if test_rows else 0
        print(f"   {col:<25} missing={missing:>6}  ({pct:.2f}%)")

    # 3. current_delay stats
    def delay_stats(rows):
        vals = [r["current_delay"] for r in rows]
        if not vals:
            return 0.0, 0.0, 0.0
        return min(vals), max(vals), sum(vals) / len(vals)

    print(f"\n3. CURRENT_DELAY STATS")
    t_min, t_max, t_mean = delay_stats(train_rows)
    print(f"   TRAIN — min={t_min:.2f}s  max={t_max:.2f}s  mean={t_mean:.2f}s")
    t_min, t_max, t_mean = delay_stats(test_rows)
    print(f"   TEST  — min={t_min:.2f}s  max={t_max:.2f}s  mean={t_mean:.2f}s")

    # 4. current_delay = 0.0 percentage
    def zero_delay_pct(rows):
        if not rows: return 0.0
        n = sum(1 for r in rows if r.get("current_delay", -999) == 0.0)
        return n / len(rows) * 100

    print(f"\n4. CURRENT_DELAY = 0.0 PERCENTAGE")
    print(f"   TRAIN : {zero_delay_pct(train_rows):.2f}%")
    print(f"   TEST  : {zero_delay_pct(test_rows):.2f}%  (should remain high during migration until live delay is added)")

    # 5. Unseen labels encoded as -1
    print(f"\n5. UNSEEN LABELS ENCODED AS -1")
    print(f"   Count (TEST segment_id + route_id unseen) : {test_unseen_count}")

    # 6. Duplicate state_id check
    train_dup = len([r["state_id"] for r in train_rows]) - len(
        set(r["state_id"] for r in train_rows))
    test_dup  = len([r["state_id"] for r in test_rows])  - len(
        set(r["state_id"] for r in test_rows))
    print(f"\n6. DUPLICATE state_id CHECK")
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
        print("\n[1/5] Loading vehicle_state_history snapshots from DB...")
        all_states = load_vehicle_state_history(db)
        print(f"  Total raw states fetched: {len(all_states):,}")
        completions = load_segment_completions(db)

        completion_lookup = build_completion_lookup(
            completions
        )
        print("\n[2/5] Loading GTFS stop coordinates...")
        stop_coords = load_stop_coords(db)
        print(f"  Stops with coordinates: {len(stop_coords):,}")

        print("\n[3/5] Loading segment_statistics...")
        seg_stats = load_segment_statistics(db)
        print(f"  Stat cells loaded: {len(seg_stats):,}")

    finally:
        db.close()

    # ------------------------------------------------------------------
    # SPLIT by day_of_week (deterministic, no random)
    # ------------------------------------------------------------------
    raw_train = [s for s in all_states if s["day_of_week"] in TRAIN_DAYS]
    raw_test  = [s for s in all_states if s["day_of_week"] in TEST_DAYS]
    print(f"\n  Day-based split -> TRAIN: {len(raw_train):,}  TEST: {len(raw_test):,}")

    # ------------------------------------------------------------------
    # Build feature rows
    # ------------------------------------------------------------------
    print("\n[4/5] Building feature rows...")
    train_rows = build_feature_rows(raw_train, stop_coords, seg_stats, completion_lookup,split="train")
    test_rows  = build_feature_rows(raw_test,  stop_coords, seg_stats,completion_lookup, split="test")
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