3. Movement State Thresholds and Hysteresis
Thresholds (movement.py:48-55):

at_stop: distance ≤ 40m AND speed ≤ 5 km/h
leaving_stop: previous was at_stop AND speed > 7 km/h AND segment_progress > 0.08
approaching_stop: distance ≤ 150m AND vehicle is converging (distance decreasing vs previous observation)
between_stops: all other cases
Hysteresis: PERSISTENCE_THRESHOLD = 2 — most transitions require the candidate state to be seen twice consecutively before confirming. Two explicit exceptions bypass this:

between_stops → approaching_stop is immediate (no persistence required, movement.py:197-201)
approaching_stop → at_stop is immediate (movement.py:183-187)
This means a single noisy GPS point within 150m of a stop can instantly snap the state to approaching_stop, and a second noisy point within 40m with low speed can snap to at_stop — producing false arrival events with no hysteresis protection on these two critical transitions.
ETA compatibility: The segment structure has segment_id, start.stop_id (= from_stop_id), end.stop_id (= to_stop_id), and end["sequence"] (= stop_sequence). All ETA-needed fields are derivable. However: there is no direction field in the reference. The loader picks the first trip for a route_id with no direction filter (see CHECK 4 below for the critical consequence).
CHECK 2 — EVENT ENGINE LOGIC
1. stop_arrival Detection
Exact condition (detectors.py:21):

if curr_state == "at_stop" and (prev_state != "at_stop"):
Stop_id used: current_state.get("next_stop_id") — correct, because at_stop means the bus reached the next stop.

GPS noise robustness: The movement state engine requires the candidate at_stop to be confirmed with speed ≤ 5 km/h and distance ≤ 40m. BUT approaching_stop → at_stop bypasses persistence (fires immediately). So one GPS outlier within 40m + speed ≤ 5 can produce a false arrival. In simulation data this is clean, but it's fragile for production.
2. segment_completed — Travel Time Formula
segment_completed is generated in two places — both attempt the same computation:

traversal_lifecycle.py:162-202
dwell_lifecycle.py:57-99
Formula: travel_time = arrival_timestamp - departure_timestamp in seconds, where departure is stored in active_traversals[vehicle_id]["departure_time"].

Execution order in engine.py:51-66:

process_traversal_lifecycle runs first — on stop_arrival, computes travel_time, appends segment_completed, calls clear_traversal(vehicle_id)
process_dwell_lifecycle runs second — on stop_arrival, calls get_active_traversal which now returns None (already cleared) — does NOT generate a second segment_completed
No duplication in practice. But this is fragile: the correctness depends entirely on execution order.

Departure time source: Stored by start_traversal on every stop_departure event. Both traversal_lifecycle and dwell_lifecycle call start_traversal on departure — the second call overwrites the first with identical values. Harmless redundancy.

6. State Leakage Between Vehicles
active_traversals, active_dwells, movement_transition_tracker, vehicle_operational_memory are all module-level dicts keyed by vehicle_id. Different vehicle_ids never interfere. Two buses on CTA_975 with distinct vehicle_ids have fully separate state. ✓

HOWEVER: These are in-process Python memory. In a multi-worker uvicorn deployment (e.g., --workers 4), each worker process has its own isolated copy of all trackers. Vehicle state from observations processed by worker 1 is invisible to worker 2. For sequential bulk replay (single process), this is fine. For a production deployment with multiple workers, this is a critical architectural gap

CHECK 3 — DATABASE AND PERSISTENCE LOGIC
1. Transit_events DB Write
metrics=event.get("metrics", {}) — SQLAlchemy JSON column stores Python dicts natively as JSON. For segment_completed: {"travel_time": 243.5} — stored as JSON number, not string. ✓

For dwell_time event: {"dwell_time": 47.2}. ✓

For segment_travel (from detect_segment_transition): metrics={} — empty JSON. The detect_segment_transition detector produces segment_travel events with no travel_time. These are NOT segment_completed events. They have no metrics.travel_time and are not useful for ETA training.

For ETA training, only segment_completed events have metrics.travel_time. segment_travel events (from the sequence detector) have empty metrics.

2. Error Handling on DB Writes
None. api/routes/vehicle.py contains zero try/except blocks around any DB operation. If db.add(db_observation) raises a UniqueConstraintViolation (same vehicle+timestamp sent twice), the entire request crashes with a 500, the DB session is left open (no db.close() in exception path), and neither vehicle_live_state nor transit_events get written.

There is no db.rollback() anywhere. Partial writes are possible: observation could be staged but state and events not committed.

3. Previous State Loading
Query: db.query(VehicleLiveState).filter(VehicleLiveState.vehicle_id == vehicle_id).first() — keyed by vehicle_id only, no route_id filter.

Subset stored: api/routes/vehicle.py:132-138 only preserves 5 fields into previous_state dict: progress, movement_state, next_stop_id, stop_sequence, current_delay. Fields like segment_id, segment_progress, distance_to_next_stop, speed are NOT passed forward. The current engine and event engine happen to only need the 5 that are present, but this is brittle.

First observation: db_state = None, previous_state = None. Engine runs cold. ✓

4. Deduplication
transit_observations has UniqueConstraint("vehicle_id", "timestamp") — prevents the same vehicle appearing twice at the same timestamp. observation_id (PK) is generated fresh each call (str(uuid.uuid4())). If the same JSONL row is replayed twice, it generates two different UUIDs — the PK constraint won't catch it. The vehicle_id + timestamp unique constraint WILL catch it and raise an IntegrityError — which crashes the request (no error handling).

5. PostgreSQL Not Running
create_engine(DATABASE_URL) is lazy. First actual operation (db.query(...)) raises sqlalchemy.exc.OperationalError: could not connect to server. No graceful handling — stack trace to caller. App crashes on first request

3. CRITICAL: Direction Bug in load_route_reference
load_route_reference queries: db.query(Trip).filter(Trip.route_id == route_id).first() — .first() returns one trip per route with no direction filter.

From GTFS trips.txt:

CTA_975: has CTA_975_O_Shape (dir 0) and CTA_975_R_Shape (dir 1) — two trips
CTA_914: both directions — two trips
CTA_80: both directions — two trips
CTA_1073: only direction 1 in GTFS — one trip
P_O_14_IG066: only direction 1 in GTFS — one trip
For CTA_975, the reference loader picks whichever trip the DB returns first (DB insertion order / undefined). A direction=0 vehicle from the JSONL (going one way) will be matched against the stops of a direction=1 trip (going the other way). GPS points along the outbound route will have maximum distance from all inbound segments — the segment matching will produce garbage: wrong segment_id, wrong stop_sequence, wrong movement_state, wrong events.

For CTA_1073, direction=0 vehicles exist in the JSONL but direction=0 trip is absent from GTFS. All CTA_1073 direction=0 observations will be matched against the direction=1 stop sequence — completely wrong.

This is the most severe correctness bug in the system. Bulk replay of all 7 days will produce ~50% of segment_completed events with wrong segment_ids and wrong travel times.

CHECK 5 — API AND INGESTION LOGIC
1. VehicleLocationRequest Schema Fields
Field	Type	Required?
vehicle_id	Optional[str]	No (can be None)
route_id	str	YES
timestamp	datetime	YES
location	Optional[Location]	No (either location OR lat+lon required)
lat	Optional[float]	No (either this pair OR location required)
lon	Optional[float]	No (either this pair OR location required)
speed	Optional[float]	No
bearing	Optional[float]	No
No speed_kmh, direction, day_of_week, time_period, simulation_seed, observation_id, trust_level, source, simulation_flag.

2. speed_kmh vs speed Mismatch
Exact line: schemas/transit.py:18: speed: Optional[float] = None

When JSONL sends {"speed_kmh": 45.2, ...}:

Pydantic v2 by default ignores extra fields (extra='ignore')
speed_kmh is silently dropped
payload.speed = None
Then api/routes/vehicle.py:78:

"speed": payload.speed   # → None
Then vehicle_state/engine.py:56:

movement_state = determine_movement_state(
    observation["vehicle_id"],
    distance,
    observation["speed"],   # ← None
    t,
    previous_state
)
In movement.py:74:

if distance <= STOP_RADIUS and speed <= STOP_SPEED:  # None <= 5 → TypeError
CRASH: TypeError: '<=' not supported between instances of 'NoneType' and 'int' on the first JSONL observation.

Also crashes at vehicle_state/engine.py:100:

"movement": "moving" if observation["speed"] > 0 else "stopped"  # None > 0 → TypeError
And at vehicle_state/validation.py:14:

if state["speed"] < 0:   # None < 0 → TypeError
3. Missing JSONL Fields
Pydantic ignores all unknown fields silently. day_of_week, time_period, direction, day_number, simulation_seed, observation_id are all dropped with no error. They are not saved anywhere.

4. Full Flow with Silent Failure Points
POST /vehicle/location (raw dict)
│
├─ VehicleLocationRequest(**raw_payload)
│    SILENT FAIL: speed_kmh → speed=None (Pydantic ignores unknown fields)
│    SILENT DROP: direction, day_of_week, time_period, day_number, simulation_seed
│
├─ normalize_timestamp(payload.timestamp)
│    NOTE: future/stale timestamp checks are COMMENTED OUT
│          Simulation timestamps from 2024 would fail if uncommented
│
├─ validate_speed(None) → passes silently (no-op for None)
│
├─ build observation dict
│    speed = None  ← silent corruption already in place
│
├─ load route_reference (from cache or DB)
│    CRASH RISK: if route_id not in DB → Exception (unhandled)
│    DIRECTION BUG: picks first trip regardless of direction
│
├─ db.query(VehicleLiveState) → previous_state
│    CRASH RISK: if vehicle_live_state table doesn't exist → ProgrammingError
│
├─ process_observation(observation, previous_state, route_reference)
│    CRASH: observation["speed"] = None → TypeError in movement.py:74
│
├─ process_event(current_state, previous_state, route_reference)
│    [never reached due to crash above]
│
├─ db.add(db_observation)
├─ db.add(db_event) for each event
├─ db upsert vehicle_live_state
├─ db.commit()
│    CRASH RISK: UniqueConstraint violation → IntegrityError (unhandled)
│    NO ROLLBACK on failure
│    db.close() in finally block? NO — session leaks on crash
│
└─ return state

CHECK 7 — WHAT IS NEEDED FOR ETA
1. SQL Query for Training Label
SELECT
    segment_id,
    (metrics->>'travel_time')::float  AS actual_travel_time,
    timestamp,
    vehicle_id,
    route_id,
    simulation_flag
FROM transit_events
WHERE event_type = 'segment_completed'
  AND metrics->>'travel_time' IS NOT NULL
  AND (metrics->>'travel_time')::float > 0
ORDER BY segment_id, timestamp;
Note: metrics is stored as PostgreSQL JSON, so ->>'travel_time' extracts it as text; cast to float for computation.

2. VehicleState Fields for ETA Features
Field	Stored in vehicle_live_state?	Correct?
segment_id	✓	Correct (but direction bug corrupts it)
segment_progress	✓	Correct (but unstabilized, oscillates)
speed	✓	Correct (but 0 when JSONL used with mismatch)
movement_state	✓	Correct
distance_to_next_stop	✓	Correct
current_delay	✓	Always 0 — broken
direction	✓	Correct (forward/backward/unknown)
stop_sequence	✓	Correct
day_of_week	NOT stored	MISSING — critical ETA feature
time_period	NOT stored	MISSING — critical ETA feature
3. stop_departure Events
YES, generated. detectors.py:29-34: fires when prev_state == "at_stop" and curr_state != "at_stop".

Timestamp issue: All events use build_event which assigns current_state["timestamp"] as the event timestamp (builder.py:16). For stop_departure, this is the timestamp of the observation AFTER the bus left — one observation interval after actual departure. For simulation data with 30-second intervals, departure time is off by ~30 seconds. This error propagates into travel_time calculations (travel_time will be ~30 seconds too short for every segment).

4. Bulk Replay Concerns for 2.3M Observations
No connection pooling config — SQLAlchemy default pool size is 5. Sequential single-threaded replay is fine.
Individual DB commit per observation — 2.3M individual transactions. At 5ms per commit (local PostgreSQL), this is ~3.2 hours of pure DB time.
Module-level in-memory trackers — with hundreds of vehicles active simultaneously across 5 routes × 2 directions × many concurrent trips, these dicts will hold thousands of entries. Memory is not a concern (dicts are small), but correctness of state recovery after a restart is zero — all in-memory state is lost on crash.
No batch insert — each db.add() + db.commit() is individual. No db.bulk_insert_mappings() or similar.
Timestamp validation is commented out — simulation data from 2024 would fail the ts < now - timedelta(hours=2) check if it were active. The commented-out check is accidentally saving replay. ✓ (if accidentally uncommented, ALL simulation observations would be rejected as stale)
No replay script for JSONL — tests/run_scenario.py reads hand-crafted scenario JSON files, not JSONL. A new script must be written.

FINAL LOGIC REPORT
LOGIC ISSUES — things that produce wrong results silently
#	Issue	File	Line
L1	Direction bug: load_route_reference picks first trip regardless of direction. Direction=0 vehicles matched to direction=1 stops → wrong segment_id, stop_sequence, events	reference/loader.py	11
L2	current_delay is always 0. All delay computation downstream is permanently broken	vehicle_state/engine.py	103
L3	stop_departure event timestamp = current observation time, not actual departure time. Underestimates travel_time by one observation interval (~30s for simulation)	event_engine/builder.py	16
L4	Cold-start bootstrap sets departure_time to current timestamp, not actual departure. First segment_completed per vehicle has underestimated travel_time	event_engine/traversal_lifecycle.py	125-126
L5	Euclidean lat/lon distance (not Haversine) in distance_point_to_segment. ~13% systematic error in E-W directions at Cairo latitude	vehicle_state/matcher.py	10-16
L6	project_point_on_segment uses same non-metric space — t is not geometrically accurate for E-W segments	vehicle_state/matcher.py	44-69
L7	segment_progress (raw t) is not stabilized, only route-level progress is. leaving_stop check at segment_progress > 0.08 uses unstabilized value	vehicle_state/utils.py + movement.py	utils.py:1-27, movement.py:89
L8	approaching_stop → at_stop and between_stops → approaching_stop bypass persistence threshold — single noisy GPS point can generate false arrival events	vehicle_state/movement.py	183-201
L9	segment_id stored in traversal at departure time is current_state["segment_id"] which may still be the PREVIOUS segment (GPS still matched to it)	event_engine/dwell_lifecycle.py	111
L10	detect_segment_transition generates segment_travel events with empty metrics={}. These look like segment completions but have no travel_time — silent dead data in DB	event_engine/detectors.py	109-115
L11	day_of_week, time_period, direction from JSONL are permanently dropped at ingestion — no path to preserve them for ETA features	api/routes/vehicle.py + schemas/transit.py	vehicle.py:48, transit.py:1-35
L12	stabilize_progress 0.5 smoothing factor lags reported progress behind reality — direction detection always reflects the previous step's movement, not current	vehicle_state/utils.py	25-26
L13	simulation/observation_generator.py hardcoded to CTA_M_112 — produces observations for a non-target route on import (line 41 executes at module level)	simulation/observation_generator.py	41
L14	start_traversal called twice per stop_departure event (once in traversal_lifecycle, once in dwell_lifecycle) — second call silently overwrites first	event_engine/traversal_lifecycle.py + dwell_lifecycle.py	traversal:141-147, dwell:107-112
CRASH RISKS — things that will cause exceptions
#	Risk	File	Line	Trigger
C1	speed=None TypeError when JSONL speed_kmh field is sent — None <= 5 crashes immediately	vehicle_state/movement.py	74	Every JSONL observation
C2	Same crash: None > 0 for movement field	vehicle_state/engine.py	100	Every JSONL observation
C3	Same crash: None < 0 in validation	vehicle_state/validation.py	14	Every JSONL observation
C4	load_route_reference raises Exception("No trip found for route X") — unhandled, crashes request	reference/loader.py	12-13	Any route not in DB
C5	init_db.py missing vehicle_live_state import — fresh DB lacks table, first DB query crashes with ProgrammingError	init_db.py	10-15	Fresh DB setup
C6	All GTFS model imports commented out in init_db.py — GTFS tables not created, load_gtfs.py fails with ProgrammingError	init_db.py	4-9	Fresh DB setup
C7	No try/except on db.commit() — UniqueConstraint violation (same vehicle+timestamp) crashes request, leaves session open (no db.close() in except path)	api/routes/vehicle.py	256	Duplicate observations
C8	observation_generator.py executes load_route_reference("CTA_M_112") at module level — importing this file crashes if DB is unavailable or CTA_M_112 not loaded	simulation/observation_generator.py	41	Any import of the module
C9	validate_vehicle_state comparison state["speed"] < 0 where speed=None — crashes before observation is stored	vehicle_state/validation.py	14	JSONL observations
C10	datetime.fromisoformat(stored["departure_time"]) in traversal — if departure_time stored as non-ISO string or None, silently swallowed by bare except Exception: pass — event silently lost

PHASE 0 — BLOCKERS (must fix before any replay)

  0.1  Fix speed_kmh → speed mismatch
       Option A: add speed_kmh field to VehicleLocationRequest with alias
       Option B: replay script remaps the field before POSTing
       Required to unblock every other step.

  0.2  Fix init_db.py: uncomment all model imports + add vehicle_live_state
       Without this, fresh DB has wrong tables and everything crashes.

  0.3  Fix direction in load_route_reference
       Add direction parameter and filter Trip query by direction_id.
       JSONL vehicle_id encodes direction (e.g., "route_CTA_1073_1_..." = dir 1)
       OR use the direction field from JSONL.
       Without this, 50%+ of segment_completed events have wrong segment_ids.

PHASE 1 — BULK REPLAY INFRASTRUCTURE

  1.1  Write bulk JSONL replay script
       - Read day_N_*_observations.jsonl line by line
       - Remap speed_kmh → speed
       - Remap direction → pass to pipeline (after schema fix)
       - Sort by timestamp within each vehicle_id to preserve order
       - POST to /vehicle/location OR call process_observation directly
       - Log failures per observation, continue on error
       - Report summary: N processed, M failed, K segment_completed generated

  1.2  Preserve day_of_week, time_period, direction at ingestion
       Two options:
       A. Add these fields to raw_payload (already stored as JSON) — extract later
       B. Add columns to transit_observations table
       These are required ETA features — option B is cleaner.

  1.3  Add error handling to api/routes/vehicle.py DB writes
       Wrap db.commit() in try/except, add db.rollback() on failure,
       guarantee db.close() in finally block.

PHASE 2 — SEGMENT STATISTICS AGGREGATION

  2.1  Create segment_statistics table
       SQLAlchemy model with: segment_id, route_id, direction,
       avg_travel_time, median_travel_time, variance, avg_dwell_time,
       sample_count, time_bucket (peak/off_peak — recommended extension),
       last_updated
       Add to init_db.py imports.

  2.2  Write segment_stats.py aggregation script
       Query transit_events WHERE event_type='segment_completed'
         AND metrics->>'travel_time' IS NOT NULL
         AND (metrics->>'travel_time')::float > 0
       Join with route/direction context from vehicle_id or raw_payload
       Filter outliers (travel_time > 3× median or < 30 seconds)
       Compute avg, median, variance per (segment_id, time_bucket)
       Write to segment_statistics table

PHASE 3 — CURRENT DELAY IMPLEMENTATION

  3.1  Implement current_delay computation
       On each observation, query transit_events for the latest
       stop_departure for this vehicle.
       Compute elapsed = current_timestamp - departure_timestamp
       Compute expected = avg_travel_time × segment_progress
       current_delay = elapsed - expected
       This requires segment_statistics to be populated first.

PHASE 4 — FEATURE ENGINEERING

  4.1  Write feature_engineering.py
       For each segment_completed event, build feature vector:
       - segment_id
       - route_id, direction
       - time_of_day (from timestamp, convert to Cairo local)
       - day_of_week (from raw_payload or transit_observations column)
       - time_period (peak/off_peak)
       - segment_progress at departure
       - speed at departure
       - current_delay at departure
       - avg_travel_time from segment_statistics (baseline)
       - variance from segment_statistics
       Target label: metrics.travel_time (actual)

PHASE 5 — ETA MODELS

  5.1  Write baseline_eta.py
       Predict = segment_statistics.avg_travel_time for (segment_id, time_bucket)
       Evaluate MAE/RMSE against held-out segment_completed events

  5.2  Write xgboost_eta.py
       Train XGBoost on feature vectors from feature_engineering.py
       Features: time_period, day_of_week, direction, speed, current_delay,
                 historical avg, historical variance
       Target: actual travel_time
       Output: trained model artifact

  5.3  Build eta_engine/ module
       Implements SegmentEstimate and ServiceEstimate contracts
       Loads trained model
       Accepts current VehicleState → returns predicted travel time per
       remaining segment → sums for predicted_arrival_time