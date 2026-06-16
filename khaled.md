# IZEE Project — Complete Codebase Reference (eta-development branch)

> This document is the authoritative codebase map for the IZEE real-time Cairo transit ETA system.
> Generated from a full file-by-file read of the eta-development branch.
> Use this to orient any new Claude Code session without re-reading source files.

---

## SYSTEM OVERVIEW

IZEE is a real-time bus ETA pipeline for Cairo, Egypt. It ingests GPS observations
from a SUMO simulation (5 routes, 2.3M observations across 7 days), runs each
observation through a Vehicle State Engine and Event Engine, persists results to
PostgreSQL, and exposes a FastAPI REST API. The ETA engine does not yet exist.

**Database:** PostgreSQL at `localhost:5433/izee_db` (user: postgres, pass: 1234)
**Framework:** FastAPI + SQLAlchemy (sync)
**GTFS data:** 5 routes — CTA_1073, CTA_975, CTA_914, P_O_14_IG066, CTA_80
**Simulation data:** `E:\Last Semster\IZEE_SUMO\converted\day_N_*_observations.jsonl`

---

## FILE: main.py
**Status:** WORKING
**Purpose:** FastAPI app entry point — registers the vehicle router.
```
app = FastAPI()
app.include_router(vehicle_router)   # from api/routes/vehicle.py
```
No middleware. No startup events. No lifespan hooks.

---

## FILE: init_db.py
**Status:** PARTIAL — only creates 2 of 8 needed tables
**Purpose:** Creates database tables via SQLAlchemy `Base.metadata.create_all`.

Active imports (tables that WILL be created):
- `models.transit_event`       → `transit_events`
- `models.transit_observation` → `transit_observations`

Commented-out imports (tables that will NOT be created):
- `#import models.agency`         → `agency`
- `#import models.route`          → `route`
- `#import models.trip`           → `trip`
- `#import models.stop`           → `stop`
- `#import models.stop_time`      → `stop_time`
- `#import models.shape`          → `shape`
- `#import models.vehicle_live_state` → `vehicle_live_state`

**Known issue:** Running `init_db.py` on a fresh DB creates only 2 tables.
GTFS tables and `vehicle_live_state` are absent — all pipeline operations will
crash on first request. All commented imports must be uncommented before use.
No `if __name__ == "__main__"` guard — importing this file side-effects immediately.

---

## FILE: database/connection.py
**Status:** WORKING
**Purpose:** SQLAlchemy engine, session factory, and declarative base.

```python
DATABASE_URL = "postgresql://postgres:1234@localhost:5433/izee_db"
engine = create_engine(DATABASE_URL)           # lazy — no connection until first use
SessionLocal = sessionmaker(bind=engine)       # no pool config — default pool size 5
Base = declarative_base()
```

No connection pooling configuration. No pool_pre_ping. Default pool_size=5,
max_overflow=10. App crashes on first DB operation if PostgreSQL is not running.

---

## FILE: database/__init__.py
**Status:** EMPTY
**Purpose:** Package marker only. No exports.

---

## FILE: enums/transit.py
**Status:** WORKING
**Purpose:** String enums for source and trust level fields used in models and ingestion.

```python
class SourceEnum(str, Enum):
    driver_app = "driver_app"
    simulated  = "simulated"
    crowdsensed = "crowdsensed"
    avl        = "avl"

class TrustLevelEnum(str, Enum):
    high   = "high"
    medium = "medium"
    low    = "low"
```

---

## FILE: schemas/transit.py
**Status:** PARTIAL — missing speed_kmh alias, missing direction/day_of_week/time_period
**Purpose:** Pydantic request schema for the POST /vehicle/location endpoint.

```python
class Location(BaseModel):
    lat: float     # required
    lon: float     # required

class VehicleLocationRequest(BaseModel):
    vehicle_id: Optional[str] = None   # optional
    route_id:   str                    # REQUIRED
    timestamp:  datetime               # REQUIRED
    location:   Optional[Location] = None
    lat:        Optional[float] = None
    lon:        Optional[float] = None
    speed:      Optional[float] = None  # ← field is "speed" not "speed_kmh"
    bearing:    Optional[float] = None

    @model_validator(mode="after")
    def normalize_location(self): ...  # requires location OR (lat+lon), raises ValueError otherwise
```

**Known issues:**
- JSONL simulation data sends `speed_kmh` — this field is silently dropped by Pydantic
  → `speed=None` → pipeline crashes with TypeError in movement.py
- `direction`, `day_of_week`, `time_period`, `simulation_seed`, `observation_id`
  from JSONL are all silently dropped — never persisted anywhere

---

## FILE: api/routes/vehicle.py
**Status:** PARTIAL — works for manual testing; crashes on JSONL bulk replay
**Purpose:** Three FastAPI endpoints — ingestion, live state query, events query.
Contains full pipeline orchestration inline (no separate service layer).

**Module-level state (persists for process lifetime):**
```python
last_transition_per_vehicle: dict  # vehicle_id → (prev_seq, curr_seq)
route_cache: dict                  # route_id → route_reference dict
```

### Endpoint 1: POST /vehicle/location
**Input:** `raw_payload: dict` (accepts anything, validates via VehicleLocationRequest)
**Output:** VehicleState dict (raw Python dict, not a Pydantic model)
**Flow:**
1. `VehicleLocationRequest(**raw_payload)` — validates, normalizes location
2. `normalize_timestamp(payload.timestamp)` — converts Cairo tz → UTC naive
3. `validate_location / validate_speed / validate_bearing` — HTTP 400 on failure
4. Build `observation` dict (hardcodes source="simulated", simulation_flag=True, trust_level="medium")
5. Build `TransitObservation` ORM object (NOT yet added to session)
6. Open `SessionLocal()`
7. Cache miss → `load_route_reference(route_id)` — raises Exception if route not in DB
8. `db.add(db_observation)` — stages observation
9. `db.query(VehicleLiveState).filter_by(vehicle_id).first()` — load previous state
10. Previous state dict has only 5 fields: `progress, movement_state, next_stop_id, stop_sequence, current_delay`
11. `process_observation(observation, previous_state, route_reference)` → VehicleState dict
12. `process_event(current_state, previous_state, route_reference)` → list of event dicts
13. Duplicate `segment_travel` filter using `last_transition_per_vehicle`
14. DB upsert: `VehicleLiveState` (UPDATE if exists, INSERT if new)
15. `TransitEvent` INSERT for each event
16. `db.commit()` — **no try/except, no rollback, db.close() not in finally**
17. Return `state` dict

**Known issues:**
- No error handling on any DB operation — IntegrityError propagates as 500
- `db.close()` not called on exception path — session leaks on crash
- `speed=None` from JSONL mismatch causes TypeError crash in step 11
- `source` and `simulation_flag` are hardcoded — JSONL values ignored
- `direction`, `day_of_week`, `time_period` never captured

### Endpoint 2: GET /vehicles/live
**Input:** Optional query params `vehicle_id: str`, `route_id: str`
**Output:** List of VehicleState dicts from `vehicle_live_state` table
**Status:** WORKING for manual queries

### Endpoint 3: GET /events
**Input:** Optional query params `vehicle_id: str`, `route_id: str`
**Output:** List of TransitEvent ORM objects, ordered by timestamp DESC
**Status:** WORKING for manual queries

---

## FILE: models/__init__.py
**Status:** EMPTY
**Purpose:** Package marker only.

---

## FILE: models/agency.py
**Status:** WORKING (commented out of init_db.py)
**Purpose:** SQLAlchemy ORM model for `agency` table.

```
Table: agency
  agency_id  String  PK
  name       String
```

---

## FILE: models/route.py
**Status:** WORKING (commented out of init_db.py)
**Purpose:** SQLAlchemy ORM model for `route` table.

```
Table: route
  route_id   String  PK
  route_name String
  agency_id  String  FK→agency.agency_id
```

---

## FILE: models/shape.py
**Status:** WORKING (commented out of init_db.py — and never used by pipeline)
**Purpose:** SQLAlchemy ORM model for `shape` table. Not used by load_gtfs.py.

```
Table: shape
  shape_id  String   PK (composite with lat, lon)
  lat       Float    PK
  lon       Float    PK
  sequence  Integer
```

---

## FILE: models/stop.py
**Status:** WORKING (commented out of init_db.py)
**Purpose:** SQLAlchemy ORM model for `stop` table.

```
Table: stop
  stop_id  String  PK
  name     String
  lat      Float
  lon      Float
```

---

## FILE: models/stop_time.py
**Status:** WORKING (commented out of init_db.py)
**Purpose:** SQLAlchemy ORM model for `stop_time` table.

```
Table: stop_time
  trip_id       String   PK, FK→trip.trip_id
  stop_id       String   PK, FK→stop.stop_id
  stop_sequence Integer
```

Note: composite PK on (trip_id, stop_id). No arrival_time or departure_time stored.

---

## FILE: models/trip.py
**Status:** WORKING (commented out of init_db.py)
**Purpose:** SQLAlchemy ORM model for `trip` table.

```
Table: trip
  trip_id   String  PK
  route_id  String  FK→route.route_id
```

Note: No `direction_id` column stored — critical gap for multi-direction support.

---

## FILE: models/transit_observation.py
**Status:** PARTIAL — missing day_of_week, time_period, direction columns
**Purpose:** SQLAlchemy ORM model for `transit_observations` table.

```
Table: transit_observations
  observation_id  String    PK  (uuid, auto-generated)
  vehicle_id      String    nullable
  route_id        String    NOT NULL
  timestamp       DateTime  NOT NULL
  lat             Float     NOT NULL
  lon             Float     NOT NULL
  speed           Float     nullable           ← stored as "speed", JSONL sends "speed_kmh"
  bearing         Float     nullable
  source          Enum(SourceEnum)  NOT NULL   ← "source_enum" PG type
  simulation_flag Boolean   default=False
  trust_level     Enum(TrustLevelEnum)  NOT NULL  ← "trust_level_enum" PG type
  raw_payload     JSON      nullable
  ingested_at     DateTime  default=utcnow

Constraints:
  UniqueConstraint("vehicle_id", "timestamp", name="uq_vehicle_timestamp")
```

**Known issues:**
- `day_of_week`, `time_period`, `direction` from JSONL not stored as columns
- `speed` column name mismatches JSONL `speed_kmh` field

---

## FILE: models/vehicle_live_state.py
**Status:** WORKING (commented out of init_db.py — table won't exist on fresh DB)
**Purpose:** SQLAlchemy ORM model for `vehicle_live_state` table — one row per vehicle.

```
Table: vehicle_live_state
  vehicle_id           String   PK, indexed
  route_id             String
  timestamp            String                 ← stored as string, not DateTime
  matched_lat          Float
  matched_lon          Float
  current_stop_id      String   nullable
  next_stop_id         String
  stop_sequence        Integer  nullable
  segment_id           String
  segment_progress     Float
  progress             Float
  distance_to_next_stop Float
  speed                Float
  direction            String
  movement             String
  movement_state       String
  current_delay        Float
  confidence           String
  source               String
  simulation_flag      Boolean
```

Note: Keyed by `vehicle_id` only — no route_id in PK. A single vehicle_id can
only have one live state row regardless of which route it is on.

---

## FILE: models/transit_event.py
**Status:** WORKING
**Purpose:** SQLAlchemy ORM model for `transit_events` table.

```
Table: transit_events
  event_id        String   PK, indexed
  event_type      String   indexed
  vehicle_id      String   indexed
  route_id        String   indexed
  timestamp       String   indexed            ← ISO8601 string, not DateTime
  stop_id         String   nullable
  from_stop_id    String   nullable
  to_stop_id      String   nullable
  segment_id      String   nullable
  stop_sequence   Integer  nullable
  metrics         JSON                        ← stores {travel_time, dwell_time, delay}
  confidence      String
  source          String
  simulation_flag Boolean
```

Note: `segment_completed` events store `metrics = {"travel_time": float}` as JSON.
ETA training label query: `SELECT (metrics->>'travel_time')::float FROM transit_events WHERE event_type='segment_completed'`

---

## FILE: reference/loader.py
**Status:** PARTIAL — does not filter by direction
**Purpose:** Builds route reference dict from DB (GTFS tables) for use by VSE and Event Engine.

```python
def load_route_reference(route_id: str) -> dict
```

**Critical bug:** uses `.first()` to select a trip — picks arbitrarily from multiple
direction trips. Direction=0 vehicles will be matched against direction=1 stop sequence.

**Return structure:**
```python
{
    "route_id": str,                       # e.g. "CTA_975"
    "stops": [
        {
            "stop_id": str,                # e.g. "95"
            "lat": float,
            "lon": float,
            "sequence": int                # stop_sequence from GTFS
        },
        ...                                # ordered by stop_sequence ASC
    ],
    "segments": [
        {
            "segment_id": str,             # format: "{from_stop_id}_{to_stop_id}"
            "start": { stop_id, lat, lon, sequence },
            "end":   { stop_id, lat, lon, sequence }
        },
        ...                                # N-1 segments for N stops
    ],
    "stops_by_sequence": {
        int: { "stop_id": str, "lat": float, "lon": float }
        ...                                # key = stop_sequence integer
    }
}
```

N+1 query problem: queries DB once per stop for stop coordinates (O(N) queries).

---

## FILE: loaders/load_gtfs.py
**Status:** WORKING — but requires GTFS tables to exist first
**Purpose:** Loads GTFS CSV files from `gtfs/` (relative path) into DB.

**Functions:**
```python
def load_agencies() → None    # reads gtfs/agency.txt   → inserts into agency
def load_stops()    → None    # reads gtfs/stops.txt    → inserts into stop
def load_routes()   → None    # reads gtfs/routes.txt   → inserts into route
def load_trips()    → None    # reads gtfs/trips.txt    → inserts into trip
def load_stop_times() → None  # reads gtfs/stop_times.txt → inserts into stop_time
```

**Run order:** agencies → stops → routes → trips → stop_times (FK dependency order)
**GTFS path:** hardcoded relative `"gtfs/"` — must be run from `E:\Last Semster\IZEE\`
**Not loaded:** shapes.txt (no load_shapes function), frequencies.txt (not needed)
**Does not filter routes** — loads entire GTFS (2997 stops, all trips)

---

## FILE: vehicle_state/engine.py
**Status:** PARTIAL — crashes if speed is None (JSONL mismatch)
**Purpose:** Main Vehicle State Engine — converts a GPS observation into a VehicleState dict.

```python
def process_observation(observation: dict, previous_state: dict | None, route_reference: dict) → dict
```

**Internal flow:**
1. Extract `lat, lon` from `observation["location"]`
2. `find_nearest_segment(lat, lon, segments)` — O(N) linear scan, Euclidean distance
3. `project_point_on_segment(lat, lon, start, end)` → `(proj_lat, proj_lon, t)`
4. `raw_progress = (segment_index + t) / total_segments`
5. `stabilize_progress(raw_progress, previous_state)` → smoothed route_progress
6. `next_stop_id = segment["end"]["stop_id"]`
7. `haversine_distance(proj_lat, proj_lon, end_lat, end_lon)` → distance_to_next_stop (meters)
8. `determine_movement_state(vehicle_id, distance, observation["speed"], t, previous_state)`
9. `determine_direction(route_progress, previous_state)`
10. `update_operational_memory(vehicle_id, distance, t)` — stores distance for next tick
11. Returns VehicleState dict

**Returns:**
```python
{
    "vehicle_id": str,
    "route_id": str,
    "trip_id": None,           # always None
    "timestamp": str,          # ISO8601
    "matched_position": {"lat": float, "lon": float},
    "current_stop_id": str | None,   # set only when movement_state == "at_stop"
    "next_stop_id": str,
    "stop_sequence": int,      # from segment["end"]["sequence"]
    "segment_id": str,         # format: "{from_stop_id}_{to_stop_id}"
    "segment_progress": float, # raw t [0,1], NOT stabilized
    "progress": float,         # stabilized route-level progress [0,1]
    "distance_to_next_stop": float,  # meters, haversine
    "speed": float,            # directly from observation["speed"]
    "direction": str,          # "forward" | "backward" | "unknown"
    "movement": str,           # "moving" | "stopped"
    "movement_state": str,     # "between_stops"|"approaching_stop"|"at_stop"|"leaving_stop"
    "current_delay": float,    # ALWAYS 0 — observation.get("current_delay", 0)
    "confidence": str,         # "high"|"medium"|"low" based on source
    "source": str,
    "simulation_flag": bool
}
```

**Known issues:**
- `observation["speed"]` crashes with TypeError if speed is None (JSONL mismatch)
- `current_delay` is always 0
- `segment_progress` (raw t) is not stabilized — only route-level `progress` is

---

## FILE: vehicle_state/matcher.py
**Status:** PARTIAL — segment matching uses Euclidean degrees, distance uses Haversine
**Purpose:** GPS-to-segment matching and distance calculations.

```python
def distance_point_to_segment(px, py, x1, y1, x2, y2) → float
    # Perpendicular distance from point to line segment
    # Uses Euclidean in lat/lon DEGREE space — ~13% E-W bias at lat=30°N
    # Used ONLY by find_nearest_segment

def find_nearest_segment(lat, lon, segments) → dict
    # Linear O(N) scan — returns segment dict with min Euclidean distance
    # No history constraint — GPS spike can jump to any segment

def project_point_on_segment(px, py, x1, y1, x2, y2) → (float, float, float)
    # Returns (proj_lat, proj_lon, t) where t ∈ [0,1]
    # t computed in degree space — geometrically inexact for E-W segments
    # Clamped to [0, 1]

def haversine_distance(lat1, lon1, lat2, lon2) → float
    # Correct spherical distance in meters
    # Used for distance_to_next_stop (the value compared against STOP_RADIUS)
```

---

## FILE: vehicle_state/movement.py
**Status:** WORKING (old version string-commented out at top — ignore it)
**Purpose:** Movement state machine with hysteresis, convergence, and persistence.

**Thresholds (all defined inside function):**
```
STOP_RADIUS        = 40m
APPROACH_RADIUS    = 150m
STOP_SPEED         = 5 km/h
DEPARTURE_SPEED    = 7 km/h
PERSISTENCE_THRESHOLD = 2 observations
```

```python
def determine_movement_state(vehicle_id, distance, speed, segment_progress, previous_state) → str
```

**State machine logic:**
- `at_stop` candidate: `distance ≤ 40 AND speed ≤ 5`
- `leaving_stop` candidate: prev=`at_stop` AND `speed > 7 AND segment_progress > 0.08`
- `approaching_stop` candidate: `distance ≤ 150 AND is_converging` (requires prior observation)
- `between_stops`: default

**Bypass rules (no persistence required):**
- `between_stops → approaching_stop`: immediate (convergence alone sufficient)
- `approaching_stop → at_stop`: immediate
- All other transitions: require count ≥ 2 via `update_transition_memory`

```python
def determine_direction(current_progress, previous_state) → str
    # Returns "forward" | "backward" | "unknown"
    # Based on delta of route-level progress vs previous_state["progress"]
```

---

## FILE: vehicle_state/transition_tracker.py
**Status:** WORKING
**Purpose:** In-process module-level dicts for movement state persistence memory.

**Module-level state:**
```python
movement_transition_tracker: dict  # vehicle_id → {candidate_state, count}
vehicle_operational_memory: dict   # vehicle_id → {previous_distance, previous_progress}
```

```python
def get_transition_memory(vehicle_id) → dict | None
def reset_transition_memory(vehicle_id) → None
def update_transition_memory(vehicle_id, candidate_state, current_distance) → dict
    # Increments count if same candidate, resets to 1 if different
    # NOTE: distance tracking inside update_transition_memory is COMMENTED OUT

def get_operational_memory(vehicle_id) → dict | None
def update_operational_memory(vehicle_id, current_distance, current_progress) → dict
    # Called AFTER determine_movement_state in engine.py
    # Stores current tick's distance as "previous_distance" for next tick
    # This is what powers the convergence check in movement.py
```

**Multi-worker caveat:** all state is in-process memory. Multiple uvicorn workers
have independent copies — vehicle state is inconsistent across workers.

---

## FILE: vehicle_state/utils.py
**Status:** WORKING
**Purpose:** Progress stabilization and confidence scoring.

```python
def stabilize_progress(current_progress, previous_state) → float
    # Rules:
    # - No previous_state → return current_progress as-is
    # - delta < -0.05 (backward > 5% of route) → freeze at prev_progress
    # - delta > 0.20 (forward jump > 20% of route) → freeze at prev_progress
    # - Otherwise → smoothed = prev_progress + (delta * 0.5)
    # NOTE: applies only to route-level progress, NOT to segment_progress (t)

def determine_confidence(observation) → str
    # "high"   if source == "driver_app"
    # "medium" if source == "simulated"
    # "low"    if source == "crowdsensed"
    # "medium" fallback
```

---

## FILE: vehicle_state/validation.py
**Status:** PARTIAL — crashes if speed is None
**Purpose:** Post-process validation and clamping of VehicleState dict.

```python
def validate_vehicle_state(state, previous_state) → dict
    # 1. Clamp progress to [0, 1]
    # 2. state["speed"] < 0 → set to 0  ← CRASHES if speed is None (TypeError)
    # 3. Invalid movement_state → fallback to "between_stops"
    # 4. Timestamp regression → keep previous timestamp
```

---

## FILE: vehicle_state/kalman.py
**Status:** EMPTY
**Purpose:** Intended for Kalman filter GPS smoothing. Contains no code.
Not imported anywhere. Placeholder only.

---

## FILE: event_engine/engine.py
**Status:** WORKING
**Purpose:** Main event orchestrator — calls all detectors and lifecycle processors.

```python
def process_event(current_state, previous_state, route_reference) → list[dict]
```

**Execution order:**
1. `detect_stop_events(current_state, previous_state)` → stop_arrival / stop_departure
2. `detect_segment_transition(current_state, previous_state, route_reference)` → segment_travel
3. `detect_delay_event(current_state, previous_state)` → delay (never fires — current_delay always 0)
4. `build_event()` for each raw event → adds vehicle_id, route_id, timestamp, event_id
5. `process_traversal_lifecycle(events, ...)` → may append segment_completed
6. `process_dwell_lifecycle(extended_events, ...)` → may append dwell_time and/or segment_completed

Note: `detect_stop_events` is imported twice (duplicate import at top of file — harmless).

---

## FILE: event_engine/detectors.py
**Status:** WORKING (delay detector permanently dormant)
**Purpose:** Three detector functions for raw event generation.

```python
def detect_stop_events(current_state, previous_state) → list[dict]
    # stop_arrival:   curr == "at_stop"  AND prev != "at_stop"
    #   stop_id = current_state["next_stop_id"]
    # stop_departure: prev == "at_stop"  AND curr != "at_stop"
    #   stop_id = previous_state["next_stop_id"]
    # Returns raw event dicts (not yet built with build_event)
    # Contains verbose print debug statements

def detect_segment_transition(current_state, previous_state, route_reference) → list[dict]
    # Compares stop_sequence (integer) between states
    # Same seq: no event
    # Reverse (seq decrease by 1): ignored as GPS jitter
    # Reverse (seq decrease > 1): segment_travel with confidence_override="low"
    # Forward: one segment_travel per step in range(prev_seq, curr_seq)
    # All segment_travel events have metrics={} — NO travel_time
    # Note: segment_travel ≠ segment_completed — only segment_completed has travel_time

def get_delay_level(delay) → str | None
    # None if < 60s, "minor" 60-180s, "moderate" 180-300s, "severe" >300s

def detect_delay_event(current_state, previous_state) → list[dict]
    # Emits "delay" event only when delay level changes
    # NEVER fires in practice — current_delay is always 0
```

---

## FILE: event_engine/builder.py
**Status:** WORKING
**Purpose:** Standardizes a raw event dict into full TransitEvent contract shape.

```python
def build_event(raw_event, current_state) → dict
    # Adds: event_id (new uuid4), vehicle_id, route_id, timestamp, stop_sequence
    # Passes through: event_type, stop_id, from_stop_id, to_stop_id, segment_id, metrics
    # confidence: uses raw_event["confidence_override"] if present, else current_state["confidence"]
    # timestamp is always current_state["timestamp"] — NOT the event's actual time
    # This means stop_departure timestamp = time of first post-departure observation
```

---

## FILE: event_engine/traversal_lifecycle.py
**Status:** WORKING (with known 20-second departure lag)
**Purpose:** Manages segment traversal timing and generates segment_completed events.

```python
def process_traversal_lifecycle(events, current_state, previous_state, route_reference) → list[dict]
```

**Bootstrap logic:** If no active traversal exists AND bus is between_stops AND
has forward progress AND speed > 5 AND distance > 150:
- Reconstructs origin_stop_id as `stops_by_sequence[current_sequence - 1]`
- Calls `start_traversal` with current timestamp as departure_time
- First segment_completed from bootstrap has underestimated travel_time

**On stop_departure event:** calls `start_traversal(vehicle_id, stop_id, timestamp, segment_id)`

**On stop_arrival event:**
- Gets active traversal
- Computes `travel_time = arrival_timestamp - departure_timestamp` (seconds)
- Emits `segment_completed` with `metrics={"travel_time": float}`
- Calls `clear_traversal`

**Note:** `start_traversal` is also called by `dwell_lifecycle` on departure — second
call overwrites first with same values (harmless redundancy).

---

## FILE: event_engine/traversal_tracker.py
**Status:** WORKING
**Purpose:** In-process module-level dict tracking active traversals per vehicle.

**Module-level state:**
```python
active_traversals: dict  # vehicle_id → {from_stop_id, departure_time, segment_id}
```

```python
def start_traversal(vehicle_id, from_stop_id, departure_time, segment_id) → None
def get_active_traversal(vehicle_id) → dict | None
def clear_traversal(vehicle_id) → None
```

---

## FILE: event_engine/dwell_lifecycle.py
**Status:** WORKING
**Purpose:** Manages dwell timing and generates dwell_time events; also generates
segment_completed (but traversal_lifecycle clears the traversal first — no duplication).

```python
def process_dwell_lifecycle(events, current_state) → list[dict]
```

**On stop_arrival:** calls `start_dwell(vehicle_id, stop_id, timestamp)`, then checks
`get_active_traversal` — if traversal was already cleared by traversal_lifecycle, no
segment_completed is generated here (correct — no duplication).

**On stop_departure:**
- Calls `start_traversal` (redundant — already called by traversal_lifecycle)
- If matching dwell exists: computes `dwell_time = departure - arrival` (seconds)
- Emits `dwell_time` event with `metrics={"dwell_time": float}`
- Calls `clear_dwell`

---

## FILE: event_engine/dwell_tracker.py
**Status:** WORKING
**Purpose:** In-process module-level dict tracking active dwells per vehicle.

**Module-level state:**
```python
active_dwells: dict  # vehicle_id → {stop_id, arrival_time}
```

```python
def start_dwell(vehicle_id, stop_id, arrival_time) → None
def get_active_dwell(vehicle_id) → dict | None
def clear_dwell(vehicle_id) → None
```

---

## FILE: utils/validators.py
**Status:** PARTIAL — timestamp staleness check is commented out
**Purpose:** Input validation functions used by the ingestion endpoint.

```python
def normalize_timestamp(ts: datetime) → datetime
    # Localizes naive timestamps as Cairo time (Africa/Cairo = UTC+2, no DST)
    # Converts to UTC
    # Returns UTC naive (tzinfo stripped) for DB storage
    # Future/stale timestamp checks ARE COMMENTED OUT — required for simulation replay

def validate_location(lat, lon) → None
    # Raises HTTP 400 if lat not in [-90,90] or lon not in [-180,180]

def validate_speed(speed: float | None) → None
    # Raises HTTP 400 if speed < 0 or speed >= 130
    # Does nothing if speed is None — does NOT catch None (JSONL mismatch)

def validate_bearing(bearing: float | None) → None
    # Raises HTTP 400 if bearing not in [0, 360]
    # Does nothing if bearing is None
```

**Known issues:**
- Timestamp staleness check is commented out — simulation 2024 data would be rejected
  if uncommented. Must stay commented for bulk replay.
- `validate_speed(None)` passes silently — does not prevent None from reaching engine

---

## FILE: simulation/observation_generator.py
**Status:** DO NOT USE
**Purpose:** Dev/test synthetic observation generator for route CTA_M_112.

**Critical problem:** `load_route_reference("CTA_M_112")` executes at MODULE LEVEL
(line 41) — importing this file immediately queries the DB. CTA_M_112 is not one
of the 5 target routes and may not exist in the DB. Import crashes if DB unavailable.

Functions (for reference only):
```python
def create_observation(vehicle_id, lat, lon, speed=0, source, simulation_flag, trust_level) → dict
def interpolate(p1, p2, steps=5) → list[tuple]
def generate_observations() → list[dict]
def stream_observations() → generator   # yields with time.sleep(2) between obs
```

---

## FILE: tests/run_scenario.py
**Status:** PARTIAL — works for hand-crafted JSON scenarios, not JSONL bulk replay
**Purpose:** HTTP-based scenario runner that POSTs observations from a JSON file.

```python
# Usage: python tests/run_scenario.py tests/scenarios/happy_path.json
# Reads: JSON file with {"scenario_name": str, "observations": list}
# POSTs each observation to http://127.0.0.1:8000/vehicle/location
# Sleeps 1 second between observations
# Prints movement_state and events from response
```

**Known issues:**
- Reads JSON scenario files, NOT JSONL simulation files
- No field remapping — `speed_kmh` from JSONL would break this too
- No error recovery — continues loop even on failed response
- Not useful for bulk replay of 2.3M observations

---

## FILE: tests/scenarios/happy_path.json
**Status:** WORKING test scenario
**Purpose:** 6-observation scenario testing full stop arrival → departure → arrival cycle.
Expected: at_stop, stop_departure, between_stops, approaching_stop, at_stop, stop_arrival, segment_completed.
Uses vehicle_id "BusEE_HappyPath_Final12", route CTA_M_112 area coords.

---

## FILE: tests/scenarios/Dwell.json
**Status:** WORKING test scenario
**Purpose:** 6-observation scenario validating dwell lifecycle.
Expected: stop_arrival once, stable at_stop for multiple ticks, stop_departure once, dwell_time once, traversal bootstrap.

---

## FILE: tests/scenarios/congestion.json
**Status:** WORKING test scenario
**Purpose:** 9-observation scenario testing that speed=0 mid-segment does not produce false at_stop.
Expected: between_stops stable during congestion, exactly one segment_completed at end.

---

## FILE: tests/scenarios/Rollback.json
**Status:** WORKING test scenario
**Purpose:** 9-observation scenario with reverse movement and re-approach.
Expected: no false stop_arrival during rollback, correct arrival on final approach.

---

## FILE: test_engine.py
**Status:** BROKEN — depends on CTA_M_112 via observation_generator
**Purpose:** Manual test that streams synthetic observations through the VSE.
Calls `stream_observations()` from observation_generator (which requires CTA_M_112 in DB).
Has no assertions — output is print-only.

---

## FILE: test_event_engine.py
**Status:** BROKEN — calls process_event() with only 2 arguments (missing route_reference)
**Purpose:** Manual test for event engine with hardcoded state dicts.
`process_event(current_state, previous_state)` — missing required `route_reference` arg.
Will raise TypeError on execution.

---

## FILE: test_reference.py
**Status:** BROKEN — depends on CTA_M_112 in DB
**Purpose:** Manual test that loads and prints route reference for CTA_M_112.
Will fail with Exception if CTA_M_112 not in trips table.

---

## CURRENT STATE SUMMARY

**Lines of code total:** ~900 (Python source, excluding comments and blank lines)
**Files total:** 39 Python files (32 source + 3 test files at root + 4 scenario JSON)

---

### Components fully working:
- `event_engine/engine.py` — orchestration correct
- `event_engine/builder.py` — event standardization correct
- `event_engine/detectors.py` — stop and segment detection correct (delay detector dormant)
- `event_engine/traversal_lifecycle.py` — segment_completed generation correct
- `event_engine/dwell_lifecycle.py` — dwell_time generation correct
- `event_engine/traversal_tracker.py` — traversal state correct
- `event_engine/dwell_tracker.py` — dwell state correct
- `vehicle_state/movement.py` — state machine with hysteresis correct
- `vehicle_state/transition_tracker.py` — persistence memory correct
- `vehicle_state/utils.py` — stabilization and confidence correct
- `vehicle_state/matcher.py` — haversine distance correct (segment matching has degree-space bias)
- `enums/transit.py` — enum definitions correct
- `database/connection.py` — connection string correct
- `loaders/load_gtfs.py` — GTFS loading correct (needs tables to exist first)
- `api/routes/vehicle.py` GET endpoints — live vehicles and events queries correct
- `models/transit_event.py` — schema correct
- `models/vehicle_live_state.py` — schema correct
- `models/agency.py`, `route.py`, `stop.py`, `trip.py`, `stop_time.py` — schemas correct

---

### Components partially working (with specific gaps):

- **`api/routes/vehicle.py` POST /vehicle/location**
  - BROKEN for JSONL replay: `speed_kmh` → `speed` mismatch causes TypeError crash
  - BROKEN: no DB error handling, no rollback, session leak on exception
  - MISSING: does not capture direction, day_of_week, time_period

- **`schemas/transit.py`**
  - MISSING: `speed_kmh` field alias
  - MISSING: `direction`, `day_of_week`, `time_period` fields

- **`init_db.py`**
  - MISSING: all GTFS model imports commented out
  - MISSING: `vehicle_live_state` import commented out
  - Only creates `transit_observations` and `transit_events` on fresh run

- **`models/transit_observation.py`**
  - MISSING: `day_of_week`, `time_period`, `direction` columns

- **`reference/loader.py`**
  - BROKEN: no direction filter — `.first()` returns arbitrary trip direction
  - Direction=0 vehicles matched against direction=1 stops

- **`vehicle_state/engine.py`**
  - BROKEN with JSONL: crashes on `None` speed from mismatch
  - `current_delay` always 0

- **`vehicle_state/validation.py`**
  - BROKEN with JSONL: `state["speed"] < 0` crashes if speed is None

- **`tests/run_scenario.py`**
  - PARTIAL: works only for hand-crafted JSON scenarios
  - No JSONL replay capability

---

### Files that must NOT be used:
- `simulation/observation_generator.py` — executes DB query at import time, wrong route
- `test_engine.py` — depends on broken observation_generator
- `test_reference.py` — hardcoded CTA_M_112 (not a target route)
- `test_event_engine.py` — calls process_event() with wrong argument count

---

### Files that need to be created (ETA build order):

1. **Bulk JSONL replay script** (e.g., `scripts/replay_jsonl.py`)
   - Reads day_N_*_observations.jsonl
   - Remaps `speed_kmh → speed`, passes `direction` to pipeline
   - Handles multi-route, sequential per vehicle, logs failures

2. **`segment_statistics` model** (`models/segment_statistics.py`)
   - Columns: segment_id, route_id, direction, avg_travel_time, median_travel_time,
     variance, avg_dwell_time, sample_count, time_bucket, last_updated

3. **`segment_stats.py`** aggregation script
   - Queries transit_events WHERE event_type='segment_completed'
   - Computes statistics per (segment_id, time_bucket, direction)
   - Writes to segment_statistics table

4. **`feature_engineering.py`**
   - Builds training feature vectors from segment_completed events + segment_statistics
   - Features: segment_id, direction, time_period, day_of_week, speed, current_delay,
     historical avg, variance

5. **`baseline_eta.py`**
   - Historical mean predictor using segment_statistics

6. **`xgboost_eta.py`**
   - XGBoost model training and evaluation

7. **`eta_engine/` module**
   - Implements SegmentEstimate and ServiceEstimate output contracts

---

### Known bugs requiring fixes before bulk replay (in priority order):

1. **[CRASH]** `speed_kmh` → `speed` mismatch — fix in `schemas/transit.py` or replay script
2. **[CRASH]** `init_db.py` missing imports — uncomment all 7 model imports
3. **[WRONG DATA]** Direction bug in `reference/loader.py` — add direction parameter and filter
4. **[CRASH]** No DB error handling in `api/routes/vehicle.py` — add try/except/rollback
5. **[MISSING FEATURES]** `day_of_week`, `time_period`, `direction` dropped at ingestion —
   add to `VehicleLocationRequest` and `transit_observations` table