# --- KHALED EDIT START ---
"""
bulk_replay.py

Replays observations through the SAME code path as the
/simulation/observation endpoint (api/routes/vehicle.py),
by calling services.observation_pipeline.process_observation_pipeline
directly — no HTTP layer.

Two modes:
- TEST MODE (default): replays a fast 3-day subset (day_1 Monday,
  day_5 Friday, day_6 Saturday) — full days, not truncated, so
  segments actually complete. Used for fast iterative testing.
- FULL MODE (--full flag): replays all 21 days, in order, with
  per-day state reset. This is the one-time overnight production
  run.

In both modes, TransitObservation rows are inserted via
db.bulk_insert_mappings() at the end of each batch (NOT db.add()
per row) for speed. VehicleLiveState stays a normal ORM object
(it's read back and mutated). TransitEvent stays db.add() (too
few rows per batch to matter).
"""
# --- KHALED EDIT END ---

import argparse
import json
import time
import builtins
import os
from datetime import datetime

from sqlalchemy import text

from database.connection import SessionLocal
from models.transit_event import TransitEvent
from models.transit_observation import TransitObservation
from services.observation_pipeline import process_observation_pipeline
from utils.validators import (
    normalize_timestamp,
    validate_location,
    validate_speed,
    validate_bearing
)
from enums.transit import SourceEnum, TrustLevelEnum

# --- KHALED EDIT START ---
import services.observation_pipeline as observation_pipeline_module
from event_engine.traversal_tracker import active_traversals
from event_engine.dwell_tracker import active_dwells
from vehicle_state.transition_tracker import (
    movement_transition_tracker,
    vehicle_operational_memory
)

CONVERTED_DIR = os.getenv("IZEE_CONVERTED_DIR", r"E:\Last Semster\IZEE_SUMO\converted")

# All 21 days, in calendar order — used by FULL mode (one-time
# overnight production run).
DAY_FILES = [
    "day_1_monday_observations.jsonl",
    "day_2_tuesday_observations.jsonl",
    "day_3_wednesday_observations.jsonl",
    "day_4_thursday_observations.jsonl",
    "day_5_friday_observations.jsonl",
    "day_6_saturday_observations.jsonl",
    "day_7_sunday_observations.jsonl",
    "day_8_friday_extra1_observations.jsonl",
    "day_9_saturday_extra1_observations.jsonl",
    "day_10_friday_extra2_observations.jsonl",
    "day_11_saturday_extra2_observations.jsonl",
    "day_12_friday_extra3_observations.jsonl",
    "day_13_saturday_extra3_observations.jsonl",
    "day_14_friday_extra4_observations.jsonl",
    "day_15_saturday_extra4_observations.jsonl",
    "day_16_friday_extra5_observations.jsonl",
    "day_17_saturday_extra5_observations.jsonl",
    "day_18_friday_extra6_observations.jsonl",
    "day_19_saturday_extra6_observations.jsonl",
    "day_20_friday_extra7_observations.jsonl",
    "day_21_saturday_extra7_observations.jsonl",
]

# Fast 3-day subset for iterative testing — full days (not
# truncated), covering all 3 binding day_types (weekday, Friday,
# Saturday) in ~30 minutes instead of overnight.
TEST_FILES = [
    "day_1_monday_observations.jsonl",
    "day_5_friday_observations.jsonl",
    "day_6_saturday_observations.jsonl",
]

CUSTOM_REPLAY_FILES = os.getenv("IZEE_REPLAY_FILES")
if CUSTOM_REPLAY_FILES:
    TEST_FILES = [
        file_name.strip()
        for file_name in CUSTOM_REPLAY_FILES.split(",")
        if file_name.strip()
    ]
# --- KHALED EDIT END ---

# --- KHALED EDIT START ---
# Removed: QUICK_TEST_LIMIT temporary quick-test cap (was 1000).
# Used only for the fast 1000-obs verification run; no longer needed
# now that 3-day test mode is ready to run for real.
# --- KHALED EDIT END ---

COMMIT_BATCH_SIZE = 5000

# Keep a real print available even after we silence the pipeline's print spam
_real_print = builtins.print


def _silence_prints():
    builtins.print = lambda *args, **kwargs: None


def _restore_prints():
    builtins.print = _real_print


def build_observation_and_db_row(raw_obs, persist_observation=True):
    """
    Mirrors api/routes/vehicle.py: receive_simulation_observation()
    so the replayed observation matches the simulation gateway exactly.

    # --- KHALED EDIT START ---
    When persist_observation is True (normal/default), returns
    (observation, db_observation) where db_observation is a
    TransitObservation ORM instance, exactly as before.

    When persist_observation is False (bulk_replay's mode), returns
    (observation, observation_mapping) where observation_mapping is
    a plain dict of column_name -> value, suitable for
    db.bulk_insert_mappings(TransitObservation, [...]). Python-side
    column defaults (observation_id, ingested_at, simulation_flag)
    are NOT guaranteed to be applied by bulk_insert_mappings, so they
    are set explicitly here.
    # --- KHALED EDIT END ---
    """
    if "location" not in raw_obs:
        raw_obs["location"] = {
            "lat": raw_obs["lat"],
            "lon": raw_obs["lon"]
        }

    raw_obs.setdefault("day_of_week", "Monday")
    raw_obs.setdefault("day_number", 1)
    raw_obs.setdefault("time_period", "peak")
    raw_obs.setdefault("simulation_seed", 1)

    raw_timestamp = datetime.fromisoformat(raw_obs["timestamp"])
    normalized_timestamp = normalize_timestamp(raw_timestamp)

    lat = raw_obs["location"]["lat"]
    lon = raw_obs["location"]["lon"]
    speed = raw_obs["speed"]  # already normalized from speed/speed_kmh
    bearing = raw_obs["bearing"]

    validate_location(lat, lon)
    validate_speed(speed)
    validate_bearing(bearing)

    observation = {
        "observation_id": raw_obs["observation_id"],

        "vehicle_id": raw_obs["vehicle_id"],
        "route_id": raw_obs["route_id"],
        "direction": raw_obs["direction"],

        "timestamp": normalized_timestamp.isoformat(),

        "location": {
            "lat": lat,
            "lon": lon
        },

        "speed": speed,
        "bearing": bearing,

        "day_of_week": raw_obs["day_of_week"],
        "day_number": raw_obs["day_number"],
        "time_period": raw_obs["time_period"],
        "simulation_seed": raw_obs["simulation_seed"],

        "source": SourceEnum.simulated.value,
        "simulation_flag": True,
        "trust_level": TrustLevelEnum.medium.value,

        "raw_payload": raw_obs,

        "ingested_at": datetime.utcnow().isoformat()
    }

    # --- KHALED EDIT START ---
    if not persist_observation:
        observation_mapping = {
            "observation_id": observation["observation_id"],

            "vehicle_id": observation["vehicle_id"],
            "route_id": observation["route_id"],

            "timestamp": normalized_timestamp,

            "lat": lat,
            "lon": lon,

            "speed": speed,
            "bearing": bearing,

            "direction": observation["direction"],

            "day_of_week": observation["day_of_week"],
            "day_number": observation["day_number"],
            "time_period": observation["time_period"],

            "simulation_seed": observation["simulation_seed"],

            "source": observation["source"],
            "simulation_flag": observation["simulation_flag"],
            "trust_level": observation["trust_level"],

            "raw_payload": observation["raw_payload"],

            "ingested_at": datetime.utcnow()
        }
        return observation, observation_mapping
    # --- KHALED EDIT END ---

    db_observation = TransitObservation(
        observation_id=observation["observation_id"],

        vehicle_id=observation["vehicle_id"],
        route_id=observation["route_id"],

        timestamp=normalized_timestamp,

        lat=lat,
        lon=lon,

        speed=speed,
        bearing=bearing,

        direction=observation["direction"],

        day_of_week=observation["day_of_week"],
        day_number=observation["day_number"],
        time_period=observation["time_period"],

        simulation_seed=observation["simulation_seed"],

        source=observation["source"],
        simulation_flag=observation["simulation_flag"],
        trust_level=observation["trust_level"],

        raw_payload=observation["raw_payload"]
    )

    return observation, db_observation


def get_event_counts():
    db = SessionLocal()
    total = db.query(TransitEvent).count()
    segment_completed = (
        db.query(TransitEvent)
        .filter(TransitEvent.event_type == "segment_completed")
        .count()
    )
    db.close()
    return total, segment_completed


# --- KHALED EDIT START ---
def reset_day_state(db, vehicle_state_cache):
    """
    Reset all per-day operational memory before starting the next
    day's file. Vehicle IDs repeat across days, so without this reset,
    day N's leftover in-memory/DB state would leak into day N+1 and
    corrupt the first observations of each vehicle (stale segment_id,
    stale traversal/dwell context, stale movement-state hysteresis).

    Clears:
    - active_traversals (event_engine.traversal_tracker)
    - active_dwells (event_engine.dwell_tracker)
    - movement_transition_tracker (vehicle_state.transition_tracker)
    - vehicle_operational_memory (vehicle_state.transition_tracker)
    - last_transition_per_vehicle (services.observation_pipeline)
    - vehicle_state_cache (bulk_replay's local cache)
    - vehicle_live_state table (TRUNCATE — DB-side live state)
    """
    active_traversals.clear()
    active_dwells.clear()
    movement_transition_tracker.clear()
    vehicle_operational_memory.clear()
    observation_pipeline_module.last_transition_per_vehicle.clear()
    vehicle_state_cache.clear()

    db.execute(text("TRUNCATE TABLE vehicle_live_state"))
    db.commit()

    _restore_prints()
    print("RESET: day-boundary state cleared (traversals, dwells, transition memory, vehicle_state_cache, vehicle_live_state truncated)")
    _silence_prints()
# --- KHALED EDIT END ---


# --- KHALED EDIT START ---
def replay_day_file(db, vehicle_state_cache, file_path, day_label):
    """
    Replay one full day file under the savepoint-per-batch scheme,
    bulk-inserting TransitObservation rows at the end of each batch.

    Returns (processed, errors, events_created, segment_completed_created,
    elapsed_seconds) for this single day.
    """
    day_start_time = time.time()
    processed = 0
    errors = 0

    events_before, seg_completed_before = get_event_counts()

    def process_batch(batch):
        nonlocal errors
        if not batch:
            return 0
        obs_mappings = []
        savepoint = db.begin_nested()
        try:
            for raw_obs in batch:
                observation, obs_mapping = build_observation_and_db_row(
                    raw_obs, persist_observation=False
                )
                obs_mappings.append(obs_mapping)
                process_observation_pipeline(
                    observation,
                    None,
                    db=db,
                    vehicle_state_cache=vehicle_state_cache,
                    persist_observation=False
                )
            db.bulk_insert_mappings(TransitObservation, obs_mappings)
            savepoint.commit()
            db.commit()
            return len(batch)
        except Exception as e:
            try:
                savepoint.rollback()
            except Exception:
                pass
            vehicle_state_cache.clear()
            errors += len(batch)
            _restore_prints()
            _real_print(f"ERROR: batch of {len(batch)} obs rolled back and skipped: {e}")
            _silence_prints()
            return 0

    batch = []
    _silence_prints()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue

                # Cheap json.loads guard — catches the only errors we
                # actually see (malformed lines), with NO DB work.
                try:
                    raw_obs = json.loads(line)
                    if "speed_kmh" in raw_obs:
                        raw_obs["speed"] = raw_obs.pop("speed_kmh")
                    elif "speed" not in raw_obs:
                        raise ValueError("Observation must include speed or speed_kmh")
                except Exception as e:
                    errors += 1
                    _restore_prints()
                    _real_print(f"ERROR parsing line (skipped): {e}")
                    _silence_prints()
                    continue

                batch.append(raw_obs)

                # --- KHALED EDIT START ---
                # Removed: QUICK_TEST_LIMIT break-early check
                # (if QUICK_TEST_LIMIT and processed + len(batch) >= QUICK_TEST_LIMIT: ...)
                # --- KHALED EDIT END ---

                if len(batch) >= COMMIT_BATCH_SIZE:
                    processed += process_batch(batch)
                    batch = []
                    _restore_prints()
                    print(f"PROGRESS [{day_label}]: {processed} observations processed")
                    _silence_prints()

        if batch:
            processed += process_batch(batch)
            batch = []
            _restore_prints()
            print(f"PROGRESS [{day_label}]: {processed} observations processed")
            _silence_prints()
    finally:
        _restore_prints()

    events_after, seg_completed_after = get_event_counts()
    elapsed = time.time() - day_start_time

    print("-" * 50)
    print(f"DAY SUMMARY [{day_label}]")
    print("-" * 50)
    print(f"Observations processed: {processed}")
    print(f"transit_events created: {events_after - events_before}")
    print(f"segment_completed events created: {seg_completed_after - seg_completed_before}")
    print(f"Errors: {errors}")
    print(f"Time taken: {elapsed:.2f} seconds")

    return processed, errors, events_after - events_before, seg_completed_after - seg_completed_before, elapsed


def run_test_mode(db, vehicle_state_cache):
    """Fast 3-day subset (day_1, day_5, day_6) — full days, no truncation."""
    # --- KHALED EDIT START ---
    # Removed: QUICK_TEST_LIMIT day_1-only restriction
    # (file_list = ["day_1_monday_observations.jsonl"] if QUICK_TEST_LIMIT else TEST_FILES)
    # --- KHALED EDIT END ---
    print("=" * 50)
    print("BULK REPLAY — TEST MODE (3-day subset)")
    print("=" * 50)
    return _run_files(db, vehicle_state_cache, TEST_FILES)


def run_full_mode(db, vehicle_state_cache):
    """All 21 days, in order — the one-time overnight production run."""
    print("=" * 50)
    print("BULK REPLAY — FULL MODE (21 days)")
    print("=" * 50)
    return _run_files(db, vehicle_state_cache, DAY_FILES)


def _run_files(db, vehicle_state_cache, file_list):
    total_processed = 0
    total_errors = 0
    total_events = 0
    total_seg_completed = 0

    for file_name in file_list:
        reset_day_state(db, vehicle_state_cache)

        file_path = f"{CONVERTED_DIR}\\{file_name}"
        processed, errors, events_created, seg_completed_created, elapsed = replay_day_file(
            db, vehicle_state_cache, file_path, file_name
        )

        total_processed += processed
        total_errors += errors
        total_events += events_created
        total_seg_completed += seg_completed_created

    return total_processed, total_errors, total_events, total_seg_completed
# --- KHALED EDIT END ---


def main():
    # --- KHALED EDIT START ---
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the full 21-day production replay (overnight). "
             "Without this flag, runs the fast 3-day test subset (~30 min)."
    )
    args = parser.parse_args()
    # --- KHALED EDIT END ---

    start_time = time.time()

    # --- KHALED EDIT START ---
    db = SessionLocal()
    db.autoflush = False
    vehicle_state_cache = {}

    try:
        if args.full:
            processed, errors, events_created, seg_completed_created = run_full_mode(
                db, vehicle_state_cache
            )
            mode_label = "FULL MODE (21 days)"
        else:
            processed, errors, events_created, seg_completed_created = run_test_mode(
                db, vehicle_state_cache
            )
            mode_label = "TEST MODE (3-day subset)"
    finally:
        db.close()
    # --- KHALED EDIT END ---

    elapsed = time.time() - start_time

    print("=" * 50)
    print(f"BULK REPLAY — {mode_label} — OVERALL SUMMARY")
    print("=" * 50)
    print(f"Total observations processed: {processed}")
    print(f"Total transit_events created: {events_created}")
    print(f"Total segment_completed events created: {seg_completed_created}")
    print(f"Total errors: {errors}")
    print(f"Time taken: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
