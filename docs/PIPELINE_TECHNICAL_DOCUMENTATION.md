# Transit Pipeline — Technical Documentation
### Components: Transit Data Ingestion → Vehicle State Engine → Event Engine

This document is a complete, code-level reference for the three pipeline
stages as they exist on branch `eta-engine-development`. It is meant to be
the foundation for building the ETA engine on top of this code.

---

# COMPONENT 1 — Transit Data Ingestion

Files: [api/routes/vehicle.py](../api/routes/vehicle.py),
[services/observation_pipeline.py](../services/observation_pipeline.py),
[schemas/transit.py](../schemas/transit.py),
[schemas/simulation_observation.py](../schemas/simulation_observation.py),
[utils/validators.py](../utils/validators.py)

## 1.1 API Endpoints

### `POST /vehicle/location`
- **Request schema**: `VehicleLocationRequest` (raw dict parsed into it manually inside the handler — no FastAPI `response_model`/body typing is declared on the route signature itself; the body arrives as `raw_payload: dict` and is validated by hand).
- **Fields**:
  - `vehicle_id: Optional[str]`
  - `route_id: str` (required)
  - `direction: int` (required)
  - `timestamp: datetime` (required)
  - `location: Optional[Location]` *or* `lat`/`lon: Optional[float]` — a `model_validator(mode="after")` (`normalize_location`) reconciles the two input shapes: if `location` is given it copies into `lat`/`lon`; if `lat`/`lon` are given it builds `location`; if neither is given it raises `ValueError("Provide either location or lat/lon")`.
  - `speed`, `bearing: Optional[float]`
- **What it does**: this is the production/live ingestion endpoint for vehicle GPS pings. Flow:
  1. Parse `raw_payload` into `VehicleLocationRequest(**raw_payload)`.
  2. `normalize_timestamp()` — converts to Cairo-local-aware-then-UTC-naive datetime (see §1.5 below).
  3. `validate_location`, `validate_speed`, `validate_bearing`.
  4. Build a plain-dict `observation` with a fresh UUID, hardcoded **temporary defaults**: `source="simulated"`, `simulation_flag=True`, `trust_level="medium"` (there's a `TODO (Production)` comment above the route stating these need to become `driver_app` / `False` / `high` once real driver ingestion exists).
  5. Build a `TransitObservation` ORM object (`db_observation`) from the same data (not yet committed).
  6. Call `process_observation_pipeline(observation, db_observation)` and return its result directly as the HTTP response.

### `GET /vehicles/live`
- Query params: `vehicle_id: Optional[str]`, `route_id: Optional[str]`.
- Opens its own `SessionLocal()`, queries `VehicleLiveState`, applies optional filters, builds and returns a list of plain dicts (one per matching vehicle) exposing: `vehicle_id`, `route_id`, `timestamp`, `matched_position {lat,lon}`, `current_stop_id`, `next_stop_id`, `stop_sequence`, `segment_id`, `segment_progress`, `progress`, `distance_to_next_stop`, `speed`, `direction`, `movement`, `movement_state`, `current_delay`, `confidence`, `source`, `simulation_flag`.
- Closes the session before returning. No pagination.

### `GET /events`
- Query params: `vehicle_id: Optional[str]`, `route_id: Optional[str]`.
- Queries `TransitEvent`, optional filters by vehicle/route, ordered by `timestamp DESC` (newest first), returns full ORM rows (FastAPI will serialize them — relies on default attribute serialization, no explicit Pydantic response model).

### `POST /simulation/observation`
- **Request schema**: `SimulationObservationRequest` — stricter/required-field version used by the simulator/bulk replay tooling:
  - `vehicle_id: str`, `route_id: str`, `direction: int`, `timestamp: datetime`
  - `location: dict` (plain dict, **not** validated as lat/lon types beyond runtime indexing)
  - `speed_kmh: float`, `bearing: float`
  - `day_of_week: str`, `day_number: int`, `time_period: str`
  - `simulation_seed: int`
- Same validation calls as `/vehicle/location` (`normalize_timestamp`, `validate_location`, `validate_speed` — note it validates `speed_kmh` through the generic `validate_speed`, which assumes km/h semantics — `validate_bearing`).
- Builds the same kind of `observation` dict/`TransitObservation`, but additionally carries `day_of_week`, `day_number`, `time_period`, `simulation_seed`, and `direction` onto the ORM object (these columns exist on `TransitObservation` for simulation use but are **not** populated by `/vehicle/location`).
- Delegates to the same `process_observation_pipeline(observation, db_observation)`.

This is the endpoint used by `scripts/bulk_replay*.py` style tooling and by the simulator producing CTA-style synthetic GPS traces.

## 1.2 `process_observation_pipeline()` — step by step

Defined in [services/observation_pipeline.py](../services/observation_pipeline.py). Signature:

```python
def process_observation_pipeline(
    observation, db_observation,
    db=None, vehicle_state_cache=None, persist_observation=True
):
```

`db`, `vehicle_state_cache`, `persist_observation` are **KHALED EDIT** additions (see §1.8) that make the function reusable for bulk replay without changing the default API behavior.

Step-by-step:

1. **Extract `vehicle_id`** from `observation["vehicle_id"]`.
2. **Session ownership**: `owns_session = db is None`. If no `db` was passed (the normal API path), open `SessionLocal()` and the function owns commit/close. If a `db` is passed in (bulk replay), the caller owns the transaction lifecycle.
3. **Try block** wraps everything:
   1. Read `route_id` and `direction_id` from the observation.
   2. **Route cache lookup**: `cache_key = (route_id, direction_id)`. If not in module-level `route_cache` dict, call `load_route_reference(route_id, direction_id)` and store it. Otherwise reuse the cached `route_reference`. (See §1.3.)
   3. Debug print of `route_reference["route_id"]`.
   4. If `persist_observation` is `True` (default / API path), `db.add(db_observation)` — stages the raw observation row for insert.
   5. **Load previous state** — either from the in-memory `vehicle_state_cache` dict (bulk-replay fast path) if supplied, or via a DB query: `db.query(VehicleLiveState).filter(vehicle_id==...).first()`.
   6. Build `previous_state` dict (or `None` if no prior row exists) containing exactly: `progress`, `movement_state`, `next_stop_id`, `stop_sequence`, `current_delay`. **This is a narrow projection** — many other `VehicleLiveState` fields (e.g. `segment_id`, `distance_to_next_stop`, `matched_lat/lon`, `confidence`) are *not* carried into `previous_state` and are therefore unavailable to the vehicle-state/event engines on the next tick except via separately-maintained module-level memories (`transition_tracker`, `traversal_tracker`, `dwell_tracker`).
   7. **Process observation**: `state = process_observation(observation, previous_state, route_reference)` → produces the new `VehicleState` dict (Component 2).
   8. **Process events**: `events = process_event(current_state=state, previous_state=previous_state, route_reference=route_reference)` → Component 3.
   9. Debug prints of prev/curr `stop_sequence`.
   10. Compute `current_transition = (prev_seq, curr_seq)`.
   11. **Duplicate-transition filter**: iterate `events`; for any event with `event_type == "segment_travel"`, if `last_transition_per_vehicle[vehicle_id] == current_transition`, skip it (printing `"IGNORED: duplicate transition"`); all other event types pass through untouched. This guards against the event engine re-emitting `segment_travel` for the same (prev_seq, curr_seq) pair across repeated observations that don't change stop sequence (e.g. if called twice for the same tick, or a vehicle hovering near a sequence boundary).
   12. If any surviving event is `segment_travel`, update `last_transition_per_vehicle[vehicle_id] = current_transition`.
   13. `final_events = filtered_events` (a no-op merge step — there used to be more here, the variable name preserves the intent of a "merge" stage).
   14. **Persist events**: for each event in `final_events`, construct a `TransitEvent` ORM row pulling `event_id`, `event_type`, `vehicle_id`, `route_id`, `timestamp`, `stop_id`, `from_stop_id`, `to_stop_id`, `segment_id`, `stop_sequence`, `metrics`, `confidence`, `source`, `simulation_flag` from the event dict, plus `day_of_week`, `time_period`, `direction` pulled from the **observation** (not the event) via `observation.get(...)`. `db.add(db_event)`.
   15. **Update or insert `VehicleLiveState`**: if `db_state` already existed (loaded in step v), mutate every field on it in place from `state`. Otherwise construct a brand-new `VehicleLiveState` and `db.add()` it.
   16. If a `vehicle_state_cache` was supplied, write `vehicle_state_cache[vehicle_id] = db_state` so the next call for this vehicle (in the same bulk-replay loop) sees the updated state without a DB round trip.
   17. Debug print of `len(db.new)`.
   18. If `owns_session`, `db.commit()`.
4. **Exception handling**:
   - `IntegrityError` → `db.rollback()`, print `"DUPLICATE OBSERVATION SKIPPED"`, **return `None`** (swallows the error — caller must handle a `None` return).
   - Any other `Exception` → `db.rollback()`, print `"PIPELINE ERROR"`, **re-raise**.
5. **Finally**: if `owns_session`, `db.close()`.
6. **Return `state`** (the new vehicle state dict) on success.

## 1.3 How `route_cache` works

- A **module-level dict** in `services/observation_pipeline.py`: `route_cache = {}` (there's also a separate, unused duplicate `route_cache = {}` in `api/routes/vehicle.py` — dead/vestigial, since the route module never reads or writes it; only the pipeline module's cache is actually used).
- Key: `(route_id, direction_id)` tuple.
- Value: the full `route_reference` dict returned by `load_route_reference()` (route_id, direction_id, stops, segments, stops_by_sequence — see §2.9).
- On miss, calls `load_route_reference(route_id, direction_id)` (which opens its own short-lived DB session) and stores the result.
- On hit, reuses the cached object directly — **no TTL, no invalidation**. If GTFS stop/trip data changes in the DB while the process is running, the cache will not reflect it until process restart.
- This is process-local, in-memory — not shared across multiple worker processes/replicas.

## 1.4 How `TransitObservation` is built and saved

- Built as a plain dict first (the `observation` variable) inside the route handler, then mirrored into the ORM model `TransitObservation` (`db_observation`).
- Fields always populated: `observation_id` (new UUID4), `vehicle_id`, `route_id`, `timestamp` (normalized), `lat`, `lon`, `speed`, `bearing`, `source`, `simulation_flag`, `trust_level`, `raw_payload` (the entire original incoming dict, stored verbatim — full audit trail).
- For `/simulation/observation` only: additionally `direction`, `day_of_week`, `day_number`, `time_period`, `simulation_seed`.
- For `/vehicle/location`: `direction` is present in the `observation` dict but is **not passed into the `TransitObservation` constructor** — so the `direction` column is left `NULL` for live-ingestion observations (only simulation observations get it persisted on the observation row). Note `observation["ingested_at"]` is also computed but never passed to the ORM model — it's dead data on the observation dict (not persisted anywhere).
- Saving: the ORM object is constructed in the route handler but **not added to a session** there — `db.add(db_observation)` happens inside `process_observation_pipeline()`, gated by `persist_observation` (default `True`). Commit happens at the end of the pipeline call (if the pipeline owns the session).
- If a duplicate primary key / unique constraint is hit (e.g. inserting the same `observation_id` twice — unlikely given UUID4, but other constraints could apply), the whole pipeline call is rolled back and returns `None`.

## 1.5 `normalize_timestamp` details

From [utils/validators.py](../utils/validators.py):
```python
def normalize_timestamp(ts: datetime):
    cairo_tz = pytz.timezone("Africa/Cairo")
    if ts.tzinfo is None:
        ts = cairo_tz.localize(ts)
    ts = ts.astimezone(pytz.UTC)
    return ts.replace(tzinfo=None)
```
- If the incoming timestamp has no tzinfo, it's assumed to be Cairo local time and localized as such.
- Always converted to UTC, then stripped of tzinfo (naive UTC) before storage — this is the convention the rest of the system assumes timestamps are in (naive UTC strings/datetimes).
- The "future timestamp"/"stale timestamp" sanity checks (originally `ts > now+5min` / `ts < now-2h`) are **commented out** — currently no freshness validation is enforced at all.

## 1.6 How `TransitEvent` is built and saved

Construction happens entirely inside `process_observation_pipeline()` (not in the route layer). For each event dict produced by `process_event()` (which itself was already normalized by `build_event()` — see §3.8):
- `event_id`, `event_type`, `vehicle_id`, `route_id`, `timestamp` — always present (set by `build_event`).
- `stop_id`, `from_stop_id`, `to_stop_id`, `segment_id` — optional, `None` unless the specific event type set them.
- `stop_sequence` — taken from `current_state["stop_sequence"]` at build time, so it reflects the vehicle's stop sequence *at the moment the event was generated*, not necessarily semantically tied to `from_stop_id`/`to_stop_id` (see known inconsistency in §3.6).
- `metrics` — dict, defaults to `{}` if not set (e.g. `dwell_time`, `travel_time`, `delay`/`level`).
- `confidence` — usually `current_state["confidence"]`, but can be overridden per-event via `confidence_override` (only used by the reverse-movement branch of `detect_segment_transition`, forcing `"low"`).
- `source`, `simulation_flag` — copied from `current_state`.
- `day_of_week`, `time_period`, `direction` — pulled from the **observation** dict (not the event or state) at persistence time in the pipeline.
- Added via `db.add(db_event)`; committed together with the `VehicleLiveState` update and the observation insert in one transaction (if the pipeline owns the session).

## 1.7 Fields populated vs left null

| Area | Populated | Left null / not persisted |
|---|---|---|
| `TransitObservation` (live `/vehicle/location`) | observation_id, vehicle_id, route_id, timestamp, lat, lon, speed, bearing, source, simulation_flag, trust_level, raw_payload | direction, day_of_week, day_number, time_period, simulation_seed, ingested_at (never sent to ORM) |
| `TransitObservation` (`/simulation/observation`) | all of the above **plus** direction, day_of_week, day_number, time_period, simulation_seed | ingested_at (still computed but discarded) |
| `TransitEvent` | event_id, event_type, vehicle_id, route_id, timestamp, metrics, confidence, source, simulation_flag, day_of_week, time_period, direction (from observation) | stop_id/from_stop_id/to_stop_id/segment_id (only set per event type — many are `None` for a given event), `trip_id` is never on the event at all |
| `VehicleState` (Component 2 output) | trip_id is explicitly set to `None` always — never populated anywhere in the current pipeline | — |

## 1.8 Error handling logic

- **Pydantic validation** (`VehicleLocationRequest(**raw_payload)` / `SimulationObservationRequest(**raw_payload)`): raises a standard FastAPI 422 if the payload doesn't match the schema (handled by FastAPI automatically, not custom code).
- **Field-level validators** (`utils/validators.py`) raise `HTTPException(400, ...)` for: invalid latitude/longitude, negative speed, unrealistic speed (≥130), invalid bearing (outside 0–360). These propagate straight out of the route handler as HTTP 400s — they execute *before* any DB writes happen, so no partial state is persisted on validation failure.
- **`IntegrityError`** inside `process_observation_pipeline`: rollback, log, return `None`. **Caller-side risk**: the route handlers (`receive_vehicle_location`, `receive_simulation_observation`) directly `return process_observation_pipeline(...)` — if it returns `None`, FastAPI will serialize `None` as a `null` JSON body with HTTP 200, not an error status. There is no special-casing for this in the route layer.
- **Any other exception**: rollback, log, **re-raise** — FastAPI's default exception handling turns this into a 500.
- `finally`: session is closed only if the pipeline itself opened it (`owns_session`).

## 1.9 KHALED EDIT changes and why they exist

All marked with `# --- KHALED EDIT START/END ---` comments in [services/observation_pipeline.py](../services/observation_pipeline.py) and [event_engine/traversal_lifecycle.py](../event_engine/traversal_lifecycle.py):

1. **Optional `db`, `vehicle_state_cache`, `persist_observation` parameters** — added to let `scripts/bulk_replay.py`-style tooling drive the pipeline at high throughput: pass an externally-managed session for batched commits, an in-memory `vehicle_id -> VehicleLiveState` cache to avoid a DB read per observation, and skip the per-call `db.add(db_observation)` because bulk replay uses `db.bulk_insert_mappings()` instead. Default values preserve the exact original behavior for the live API path.
2. **`owns_session` logic** — lets the function be either a self-contained transaction (API path) or a participant in a caller-managed transaction (bulk replay path), without duplicating the function.
3. **`vehicle_state_cache` sync after update** — keeps the in-memory cache consistent across repeated calls within one bulk replay batch, avoiding stale reads.
4. **Removed quadratic `event_count` computation** — a comment notes a prior implementation scanned `db.new` on every observation just to feed a silenced print statement, an O(batch²) cost with zero functional value; removed for performance.
5. **`event_engine/detectors.py` — `# --- KHALED EDIT START/END ---` block** inside `process_traversal_lifecycle` (stop_departure handling): adds a fallback search over `route_reference["segments"]` to find the departure segment by matching `segment["start"]["stop_id"] == stop_id` when the vehicle's current `segment_id` doesn't already start with `{stop_id}_` (e.g. because the vehicle has already advanced past the stop's segment by the time the departure event is processed). Without this fallback, `start_traversal` could be skipped or called with the wrong segment.

---

# COMPONENT 2 — Vehicle State Engine

Files: [vehicle_state/engine.py](../vehicle_state/engine.py),
[vehicle_state/matcher.py](../vehicle_state/matcher.py),
[vehicle_state/movement.py](../vehicle_state/movement.py),
[vehicle_state/validation.py](../vehicle_state/validation.py),
[vehicle_state/transition_tracker.py](../vehicle_state/transition_tracker.py),
[vehicle_state/utils.py](../vehicle_state/utils.py),
[reference/loader.py](../reference/loader.py)

## 2.1 `process_observation()` — complete flow

```python
def process_observation(observation, previous_state, route_reference):
```

1. **Extract GPS**: `lat, lon = observation["location"]["lat"/"lon"]`.
2. **Find nearest segment**: `segment = find_nearest_segment(lat, lon, route_reference["segments"])` (§2.2).
3. Compute `segment_index = segments.index(segment)` and `total_segments = len(segments)`. (Note: `list.index()` is an O(n) linear scan that re-finds the segment by equality — slightly wasteful since `find_nearest_segment` already iterated the same list, but functionally fine for route sizes seen here.)
4. **Project the point onto the matched segment**: `proj_lat, proj_lon, t = project_point_on_segment(lat, lon, start.lat, start.lon, end.lat, end.lon)` — `t` is the 0–1 fractional progress *along this one segment*.
5. **Raw route progress**: `raw_progress = (segment_index + t) / total_segments` — a 0–1 value representing overall route completion.
6. **Stabilize progress**: `route_progress = stabilize_progress(raw_progress, previous_state)` (§2.3) — smooths/clamps against the previous tick's progress.
7. **Next stop**: `next_stop_id = end["stop_id"]` (the stop_id at the far end of the matched segment).
8. **Distance to next stop**: `distance = haversine_distance(proj_lat, proj_lon, end.lat, end.lon)` — great-circle distance in meters from the *projected* point to the segment's end stop.
9. **Movement state**: `movement_state = determine_movement_state(vehicle_id, distance, observation["speed"], t, previous_state)` (§2.4).
10. **Direction**: `direction = determine_direction(route_progress, previous_state)` — `"forward"` if progress increased, `"backward"` if decreased, `"unknown"` if no previous data or unchanged.
11. **Current stop**: `current_stop_id = next_stop_id if movement_state == "at_stop" else None`.
12. **Confidence**: `confidence = determine_confidence(observation)` — based on `source` (§2.utils).
13. **Update operational memory**: `update_operational_memory(vehicle_id, distance, t)` — unconditionally called every tick, regardless of movement state, to keep `vehicle_operational_memory[vehicle_id]` current (`previous_distance`, `previous_progress`) for the *next* tick's convergence checks in `determine_movement_state`.
14. **Build the `vehicle_state` dict** (full field list in §2.7).
15. **Validate**: `vehicle_state = validate_vehicle_state(vehicle_state, previous_state)` (§2.validation) — clamps progress to [0,1], clamps speed to ≥0, falls back `movement_state` to `"between_stops"` if it's somehow not one of the four valid values, and guards against timestamp regression (keeps previous timestamp if the new one is earlier).
16. **Return** the validated state dict.

`trip_id` is always set to `None` — there is currently no trip-matching logic anywhere in this engine.

## 2.2 `find_nearest_segment` — exact algorithm

[vehicle_state/matcher.py](../vehicle_state/matcher.py):

```python
def distance_point_to_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    closest_x, closest_y = x1 + t*dx, y1 + t*dy
    return math.hypot(px - closest_x, py - closest_y)
```

- **This is planar (Euclidean) geometry on raw lat/lon values**, not a geodesic/haversine calculation — `distance_point_to_segment` treats latitude and longitude as if they were Cartesian x/y. This is an approximation that's reasonably accurate for short segments at city scale but technically distorts east-west distances by `cos(latitude)` and ignores Earth curvature entirely. (Contrast with `haversine_distance`, which **is** geodesically correct and used elsewhere, e.g. for `distance_to_next_stop`.)
- `find_nearest_segment` loops over **every** segment in the route, computes `distance_point_to_segment` for each (point-to-segment perpendicular/clamped distance), and keeps the segment with the smallest distance (`min_distance` starts at `inf`, strict `<` comparison — first segment with the minimum wins on ties).
- No spatial index — O(n) per observation where n = number of segments in the route. Fine for typical route sizes (tens of segments), would not scale to very large route networks without an index.
- **No outlier rejection** — even a GPS fix wildly off-route still matches to *some* segment (whichever is geometrically closest), there is no max-distance cutoff that could mark the vehicle as "unmatched".

## 2.3 Segment progress (0.0–1.0)

Two distinct progress values exist:
- **Segment-local `t`** (`segment_progress` field): from `project_point_on_segment`, purely the 0–1 fraction along the *currently matched* segment (clamped). Computed once per tick directly from the projection — **not stabilized/smoothed**.
- **Route-level `progress`**: `raw_progress = (segment_index + t) / total_segments`, then passed through `stabilize_progress()`:

```python
def stabilize_progress(current_progress, previous_state):
    if not previous_state: return current_progress
    prev_progress = previous_state.get("progress")
    if prev_progress is None: return current_progress
    delta = current_progress - prev_progress
    if delta < -0.05: return prev_progress      # reject big backward jump
    if delta > 0.2:  return prev_progress        # reject big forward jump
    return prev_progress + (delta * 0.5)         # 50% smoothing otherwise
```
  - Backward jump > 0.05 of total route → rejected, previous progress is kept.
  - Forward jump > 0.2 of total route → rejected (treated as noise/mismatch), previous progress is kept.
  - Otherwise, the new progress is **half-stepped** toward the raw value (exponential-smoothing-like, factor 0.5) rather than snapping directly to it.
  - This means `progress` always lags slightly behind the raw geometric computation, and can get "stuck" at the previous value if a real jump (e.g. due to a route's segment skip) exceeds 0.2 — a known source of incorrect progress under fast movement or sparse pings.

## 2.4 `movement_state` — exact conditions

[vehicle_state/movement.py](../vehicle_state/movement.py), function `determine_movement_state(vehicle_id, distance, speed, segment_progress, previous_state)`.

Constants: `STOP_RADIUS=40m`, `APPROACH_RADIUS=150m`, `STOP_SPEED=5`, `DEPARTURE_SPEED=7`, `PERSISTENCE_THRESHOLD=2`.

**Candidate inference** (before applying hysteresis against the previous confirmed state):
1. **`at_stop` candidate**: `distance <= 40` AND `speed <= 5`.
2. **`leaving_stop` candidate**: only considered if `previous_confirmed_state == "at_stop"`. Requires BOTH `speed > 7` (departure speed) AND `segment_progress > 0.08` ("origin divergence" — far enough along the new segment). If only one holds, candidate falls back to `"at_stop"` (stays parked).
3. **`approaching_stop` candidate**: only when `distance <= 150` (and not already captured by 1/2 above). Looks up `vehicle_operational_memory[vehicle_id]["previous_distance"]`; if the current distance is strictly less than the remembered previous distance, `is_converging = True` → candidate is `"approaching_stop"`; otherwise candidate is `"between_stops"` (i.e. close to a stop but not getting closer = not "approaching" by this logic — possibly an inflection point or it just left a stop in the other direction).
4. **Default**: `"between_stops"`.

**Hysteresis / persistence layer** applied after candidate inference:
- If there's **no previous confirmed state** → return candidate directly (no smoothing on the very first tick for a vehicle).
- If **candidate == previous confirmed state** → call `reset_transition_memory(vehicle_id)` (clear any pending-transition evidence) and return the previous state (stable).
- **Special-cased transitions that bypass persistence**:
  - `approaching_stop → at_stop`: returned immediately, no persistence required ("terminal servicing semantics" — once close+slow enough, commit to the stop right away).
  - `between_stops → approaching_stop`: returned immediately ("approach ownership" is a soft transition, doesn't need confirmation).
- **All other transitions** require evidence accumulation: `update_transition_memory(vehicle_id, candidate_state, distance)` increments a counter if the candidate matches the last pending candidate, else resets it to 1. If `count < PERSISTENCE_THRESHOLD (2)`, the **previous confirmed state is returned** (transition not yet confirmed). Once `count >= 2`, `reset_transition_memory` is called and the **new candidate state is returned** (confirmed transition).

So in practice: `at_stop`↔`leaving_stop`/`between_stops` and `between_stops`↔`approaching_stop`(reverse direction)/`at_stop` directly require **two consecutive ticks** agreeing before the state officially changes, except for the two special-cased fast paths above.

`direction` is computed separately (`determine_direction`) purely from progress delta: `forward` if `current_progress > prev_progress`, `backward` if less, `unknown` if no previous data or equal.

## 2.5 `previous_state` — contents and use

Constructed in `process_observation_pipeline()` (Component 1, §1.2 step iii) from the **previous tick's `VehicleLiveState` DB row** (or in-memory cache entry), projected down to exactly:
```python
{
  "progress": ...,
  "movement_state": ...,
  "next_stop_id": ...,
  "stop_sequence": ...,
  "current_delay": ...
}
```
It does **not** include `timestamp` from the DB row directly as a top-level read in this snapshot... but note `validate_vehicle_state` reads `previous_state.get("timestamp")` — which will always be `None` from this construction since `timestamp` isn't one of the five extracted keys. This means the "keep previous timestamp if invalid" guard in validation **never actually triggers via this path** — it's effectively dead protection given how `previous_state` is built today (a latent inconsistency, not a crash, just inert code).

Used by: `stabilize_progress` (progress smoothing), `determine_movement_state` (hysteresis baseline), `determine_direction` (progress delta), `validate_vehicle_state` (timestamp regression guard — currently inert per above), and in Component 3's detectors for stop-arrival/departure and segment-transition detection.

## 2.6 `distance_to_next_stop` computation

`haversine_distance(proj_lat, proj_lon, end["lat"], end["lon"])` — true geodesic distance in meters between the **projected (matched) position** on the segment and the stop coordinate at the segment's end. Uses the standard haversine formula with `R = 6371000` meters. This is distinct from the planar distance used for segment matching (§2.2) — distance-to-stop is geodesically accurate, segment matching is not.

## 2.7 `VehicleLiveState` — fields and meaning

(ORM model `models/vehicle_live_state.py` is mirrored exactly by the `vehicle_state` dict built in `engine.py`.)

| Field | Meaning |
|---|---|
| `vehicle_id` | identifier from observation |
| `route_id` | from `route_reference["route_id"]` (i.e. the route that was matched, echoing the input route_id) |
| `trip_id` | always `None` — no trip-level matching implemented |
| `timestamp` | observation timestamp (validated/possibly held back if regressed — see §2.5 caveat) |
| `matched_position.lat/lon` | the GPS fix snapped onto the nearest route segment (`proj_lat`, `proj_lon`) |
| `current_stop_id` | set only when `movement_state == "at_stop"`, else `None` |
| `next_stop_id` | stop_id at the far end of the matched segment, always set |
| `stop_sequence` | GTFS `sequence` of the **next** stop (the segment's `end`) |
| `segment_id` | `f"{start_stop_id}_{end_stop_id}"` of the matched segment |
| `segment_progress` | raw `t` (0–1) along the current segment, unsmoothed |
| `progress` | stabilized 0–1 route-wide progress |
| `distance_to_next_stop` | haversine meters from matched position to next stop |
| `speed` | from observation, clamped ≥0 by validation |
| `direction` | `"forward"/"backward"/"unknown"` based on progress delta |
| `movement` | simple boolean-ish: `"moving"` if `speed > 0` else `"stopped"` — independent from/coarser than `movement_state` |
| `movement_state` | `"at_stop"/"leaving_stop"/"approaching_stop"/"between_stops"` per §2.4 |
| `current_delay` | `observation.get("current_delay", 0)` — **no delay computation exists anywhere in this codebase**; this is always `0` unless a caller manually injects it into the observation dict, which none of the current ingestion paths do. The delay-event detector (Component 3) consumes this field but will never actually fire since it's always `0`/never changes level. |
| `confidence` | `"high"/"medium"/"low"` mapped from `observation["source"]` |
| `source`, `simulation_flag` | passed through from observation |

## 2.8 `transition_tracker` — what it tracks and why

[vehicle_state/transition_tracker.py](../vehicle_state/transition_tracker.py) — two **module-level global dicts**:

1. **`movement_transition_tracker`** (`vehicle_id -> {"candidate_state", "count"}`): short-lived hysteresis evidence. Reset to empty whenever a transition is confirmed or the candidate matches the already-confirmed state. Used purely to require N consecutive agreeing observations before flipping `movement_state` (persistence threshold = 2). `get_transition_memory` is defined but **never called anywhere** (dead accessor — only `update_transition_memory` and `reset_transition_memory` are used directly inside `movement.py`).
2. **`vehicle_operational_memory`** (`vehicle_id -> {"previous_distance", "previous_progress"}`): **continuous** memory, updated unconditionally every tick via `update_operational_memory()` (called once per `process_observation` regardless of movement state). Used by the `approaching_stop` convergence check (is current distance less than last tick's distance?). Unlike the transition tracker, this is never reset — it just keeps overwriting.

**Why two separate trackers**: the transition tracker is deliberately ephemeral (reset on confirmation) to implement debounce/hysteresis; the operational memory is deliberately persistent/continuous because convergence detection needs last-tick's raw distance regardless of whether a state transition is pending.

## 2.9 `route_reference` — exact structure

From [reference/loader.py](../reference/loader.py) `load_route_reference(route_id, direction_id)`:

```python
{
    "route_id": route_id,
    "direction_id": direction_id,
    "stops": [ {"stop_id", "lat", "lon", "sequence"}, ... ],   # ordered by stop_sequence
    "segments": [
        {
            "segment_id": f"{stops[i]['stop_id']}_{stops[i+1]['stop_id']}",
            "start": {"stop_id", "lat", "lon", "sequence"},
            "end":   {"stop_id", "lat", "lon", "sequence"}
        },
        ...
    ],
    "stops_by_sequence": {
        sequence_int: {"stop_id", "lat", "lon"},   # NOTE: no "sequence" key inside the value itself
        ...
    }
}
```
- Built from **one** `Trip` row matching `(route_id, direction_id)` — `.first()` — i.e. it assumes all trips on a given route+direction share the same stop pattern; if a route has multiple trip variants (branches/short-turns) with different stop sequences, only the first trip found is used as the canonical reference for the whole route+direction.
- `stops` list comes from that one trip's `StopTime` rows ordered by `stop_sequence`, each joined individually to `Stop` (N+1 query pattern — one query per stop, not batched — a performance consideration for very long routes, though loader runs once per cache miss so it's not hot-path).
- Raises a bare `Exception` (not `HTTPException`) if no trip is found for the route/direction — this propagates up through `process_observation_pipeline`'s generic `except Exception` handler and becomes an HTTP 500 with the rollback/re-raise behavior in §1.8.

## 2.10 `stops_by_sequence` — built and used

- Built once inside `load_route_reference`, as `{sequence: {"stop_id","lat","lon"}}` for every stop on the route.
- Used in **Component 3** (`event_engine/detectors.py::detect_segment_transition`) to walk every intermediate sequence between `prev_seq` and `curr_seq` when a vehicle has advanced multiple stops in one tick ("skipped stop" handling) — `stops_map.get(seq)` / `stops_map.get(seq+1)` to synthesize one `segment_travel` event per hop.
- Also used in `traversal_lifecycle.py`'s "OPERATIONAL TRAVERSAL BOOTSTRAP" block to reconstruct the **origin** stop_id of the segment the vehicle is currently traversing, by looking up `current_sequence - 1`.
- Not used anywhere in Component 2 itself — it's loaded for Component 3's benefit, despite living in the `route_reference` object built for Component 2.

## Component 2 — Known bugs / global state / performance

**Known bugs / inconsistencies:**
- `previous_state["timestamp"]` is always `None` given how `previous_state` is constructed in the pipeline (§2.5) → the timestamp-regression guard in `validate_vehicle_state` is dead code in practice.
- `current_delay` is always `0` — no delay computation exists, so delay-level events (Component 3) can never fire under the current pipeline.
- Segment matching (`find_nearest_segment`) uses **planar** distance, not geodesic — a known approximation, acceptable at city scale but not exact, and inconsistent with the geodesically-correct `haversine_distance` used for stop distance.
- No max-distance cutoff on segment matching — a vehicle GPS fix arbitrarily far from any route segment still gets matched to the nearest one with no "off-route"/low-confidence flag.
- `segments.index(segment)` does a second O(n) scan immediately after `find_nearest_segment` already iterated the list — redundant but not currently a real bottleneck.
- `route_reference` building does one Stop query per stop (N+1) rather than a single batched join/IN query — runs only on cache miss so it's a one-time cost per (route,direction) pair, not per-observation.

**Module-level global state that must be reset between days / replay runs:**
- `vehicle_state.transition_tracker.movement_transition_tracker` (`vehicle_id -> evidence`)
- `vehicle_state.transition_tracker.vehicle_operational_memory` (`vehicle_id -> previous_distance/progress`)

These are pure in-process Python dicts with **no expiry and no persistence**. They survive across observations for the life of the process but are **not** scoped per simulated "day" — if a bulk replay script feeds multiple simulated days through the same process without resetting these dicts, residual hysteresis/convergence state from the end of day N will bleed into the start of day N+1 for the same vehicle_id. Anyone driving multi-day batch replay must explicitly clear these dicts (and the Component 3 equivalents, §3 below) between days, or restart the process per day.

**Performance considerations:**
- `route_cache` (Component 1) avoids re-loading route geometry every observation — good.
- Per-tick cost in Component 2 is O(segments) for matching + O(1) dict lookups for trackers — fine for normal route sizes.
- The two global tracker dicts grow unboundedly with the number of distinct `vehicle_id`s ever seen in the process lifetime — no eviction. For a long-running production process with high vehicle churn this is an unbounded memory growth concern (not yet hit in practice within the current simulation scale).

---

# COMPONENT 3 — Event Engine

Files: [event_engine/engine.py](../event_engine/engine.py),
[event_engine/detectors.py](../event_engine/detectors.py),
[event_engine/traversal_lifecycle.py](../event_engine/traversal_lifecycle.py),
[event_engine/dwell_lifecycle.py](../event_engine/dwell_lifecycle.py),
[event_engine/builder.py](../event_engine/builder.py),
[event_engine/traversal_tracker.py](../event_engine/traversal_tracker.py),
[event_engine/dwell_tracker.py](../event_engine/dwell_tracker.py)

## 3.1 `process_event()` — complete flow

```python
def process_event(current_state, previous_state, route_reference):
```
1. `stop_events = detect_stop_events(current_state, previous_state)` — always runs, even with no `previous_state` (first observation for a vehicle).
2. `segment_events = detect_segment_transition(...)` — **only if `previous_state` exists**.
3. `delay_events = detect_delay_event(...)` — **only if `previous_state` exists**.
4. `all_raw_events = stop_events + segment_events + delay_events`.
5. For each raw event, call `build_event(event, current_state)` to produce the fully standardized event dict (§3.8); collect into `events`.
6. `traversal_events = process_traversal_lifecycle(events, current_state, previous_state, route_reference)` — examines the just-built `events` list (specifically looking for `stop_departure`/`stop_arrival`) plus standalone segment-transition bootstrap logic, and may emit additional `segment_completed` events. `events.extend(traversal_events)`.
7. `dwell_events = process_dwell_lifecycle(events, current_state)` — examines the (now extended) `events` list for `stop_arrival`/`stop_departure` and may emit `dwell_time` and/or another `segment_completed`. `events.extend(dwell_events)`.
8. Return `events` (a flat list, possibly containing duplicate-ish `segment_completed` events from both lifecycle passes — see known bug below).

## 3.2 `stop_arrival` detection — exact conditions

[event_engine/detectors.py](../event_engine/detectors.py) `detect_stop_events`:
```python
if curr_state == "at_stop" and prev_state != "at_stop":
    events.append({"event_type": "stop_arrival", "stop_id": current_state.get("next_stop_id")})
```
- Fires whenever the **current tick's `movement_state`** (already hysteresis-confirmed by Component 2) is `"at_stop"` and the previous tick's was anything else (including `None` on the very first observation for a vehicle — i.e. a vehicle that starts the simulation already parked at a stop will fire an immediate `stop_arrival`).
- `stop_id` = `current_state["next_stop_id"]` (the stop the vehicle has arrived at, per Component 2's convention that `next_stop_id` becomes the arrived-at stop once `at_stop`).
- No distance threshold or speed check is re-applied here — entirely delegates to Component 2's `movement_state` machine.

## 3.3 `stop_departure` detection — exact conditions

Same function:
```python
if prev_state == "at_stop" and curr_state != "at_stop":
    events.append({"event_type": "stop_departure", "stop_id": previous_state.get("next_stop_id")})
```
- Mirror image of arrival: previous tick was `"at_stop"`, current tick is anything else (including `"leaving_stop"`, `"approaching_stop"`, or `"between_stops"`).
- `stop_id` = `previous_state["next_stop_id"]` — the stop being departed from.
- Both arrival and departure can theoretically fire in the **same** call only if `prev_state` transitioned through `at_stop` *and* current is also `at_stop`-adjacent in a weird way — in practice these two `if`s are mutually exclusive given the values involved (can't have `curr_state == "at_stop"` and `curr_state != "at_stop"` simultaneously), so at most one of the two fires per tick.

## 3.4 `dwell_time` computation

Handled in [event_engine/dwell_lifecycle.py](../event_engine/dwell_lifecycle.py) `process_dwell_lifecycle`, triggered off the **already-built events list** (not off raw current/previous state directly):
- On a `stop_arrival` event: `start_dwell(vehicle_id, stop_id, timestamp)` records `{"stop_id", "arrival_time"}` in the module-level `active_dwells` dict. (It also independently checks for an active traversal and may emit a `segment_completed` here too — see §3.7 overlap.)
- On a `stop_departure` event: looks up `get_active_dwell(vehicle_id)`; if found **and** `stored_dwell["stop_id"] == stop_id` (the departure stop matches the stop the dwell was started at), computes `dwell_time = (departure_timestamp - arrival_timestamp).total_seconds()` via `datetime.fromisoformat` on both timestamps, builds a `dwell_time` event with `metrics={"dwell_time": ...}`, then unconditionally `clear_dwell(vehicle_id)` regardless of whether the stop_id matched.
- Wrapped in `try/except: pass` — any parsing failure silently drops the dwell event (no log).

## 3.5 `segment_travel` detection

[event_engine/detectors.py](../event_engine/detectors.py) `detect_segment_transition(current_state, previous_state, route_reference)` — only called when `previous_state` exists:
1. Reads `prev_seq`/`curr_seq` (`stop_sequence` field of each state). If either is `None`, returns no events.
2. **Same sequence** → no event.
3. **Reverse** (`curr_seq < prev_seq`):
   - If the reverse is exactly one sequence step (`prev_seq - curr_seq == 1`) → treated as GPS jitter/oscillation, **ignored** (no event).
   - Otherwise (reverse by 2+) → emits **one single** `segment_travel` event spanning `from_stop_id = previous_state["next_stop_id"]` → `to_stop_id = current_state["next_stop_id"]`, with `confidence_override: "low"` (does not walk intermediate stops on a multi-step reverse — only one synthetic event for the whole jump).
4. **Forward** (`curr_seq > prev_seq`): loops `for seq in range(prev_seq, curr_seq)`, looking up `stops_by_sequence[seq]` and `[seq+1]`, emitting one `segment_travel` event per consecutive pair (so a multi-stop forward skip generates multiple discrete `segment_travel` events, one per hop, each with `metrics={}` and no confidence override). If a sequence is missing from the map, that hop is silently skipped (`continue`).
- These `segment_travel` events carry no timing/metrics themselves (`metrics: {}`) — they're a simple "transition happened" marker; actual timing (`travel_time`) is computed separately by the traversal lifecycle (§3.6), not here.
- A commented-out block shows a previously considered (and disabled) "tiny forward movement" oscillation filter based on progress delta — not currently active.
- Component 1's pipeline applies an additional duplicate-transition filter on top of these (§1.2.xi) keyed on `(prev_seq, curr_seq)` per vehicle.

## 3.6 Traversal lifecycle — full detail

[event_engine/traversal_lifecycle.py](../event_engine/traversal_lifecycle.py) `process_traversal_lifecycle(events, current_state, previous_state, route_reference)`.

### Starting a traversal — `start_traversal()`
[event_engine/traversal_tracker.py](../event_engine/traversal_tracker.py):
```python
def start_traversal(vehicle_id, from_stop_id, departure_time, segment_id):
    active_traversals[vehicle_id] = {
        "from_stop_id": from_stop_id,
        "departure_time": departure_time,
        "segment_id": segment_id
    }
```
Three separate call sites can start a traversal:
1. **Operational bootstrap** (below) — when the vehicle is mid-route with no tracked traversal but clear forward movement evidence.
2. **`stop_departure` event handling** inside `process_traversal_lifecycle`'s event loop — the "real" start, anchored to an actual departure.
3. **`stop_departure` event handling** inside `process_dwell_lifecycle` (§3.7) — a *second*, independent call to `start_traversal` for the same departure (re-starts/overwrites the traversal entry that step 2 may have just set, since dict assignment is idempotent overwrite — not a crash, but a redundant duplicate call path).

### `active_traversals` dict structure
`vehicle_id -> {"from_stop_id": str, "departure_time": isoformat str, "segment_id": str}`. Single active traversal per vehicle at a time (no stacking/queueing).

### SEGMENT TRANSITION COMPLETION block — exact condition and what it fires
At the top of `process_traversal_lifecycle`, before anything else:
```python
active_traversal = get_active_traversal(vehicle_id)
if active_traversal and previous_state:
    stored_segment = active_traversal.get("segment_id")
    current_segment = current_state.get("segment_id")
    if stored_segment and current_segment and stored_segment != current_segment:
        ...
```
- Fires when there **is** an active traversal, there **was** a previous state, and the vehicle's **current matched `segment_id` differs from the segment the traversal was recorded against** — i.e. Component 2 has matched the vehicle onto a new segment since the traversal started, independent of whether a `stop_arrival`/`stop_departure` event fired this tick.
- Computes `travel_time = current_state.timestamp - active_traversal.departure_time` (via `datetime.fromisoformat` on both — **note**: `active_traversal["departure_time"]` was stored from whatever was passed as `timestamp` at start-time, which in the engine call sites is a `datetime` object or ISO string depending on caller — `fromisoformat` requires a string, so this only works correctly if `current_state["timestamp"]` and the stored departure_time are string-formatted; if a raw `datetime` object was stored instead, `datetime.fromisoformat` would throw and the whole block is wrapped in `try/except Exception` which just prints `"Segment transition completion failed:"` and continues).
- If `travel_time <= 0`, the traversal is simply cleared and the function returns early **without** starting a new traversal for the new segment (a vehicle whose clock seems to have gone backward loses traversal tracking for that hop).
- Otherwise, builds and appends a `segment_completed` event with:
  - `from_stop_id = active_traversal["from_stop_id"]`
  - `to_stop_id = stored_segment.split("_")[1]` (parsed from the **old/stored** segment_id string, not from current_state)
  - `segment_id = stored_segment` (the segment being completed, i.e. the *old* one)
  - `metrics = {"travel_time": ..., "completion_method": "segment_transition"}`
- Then **always** `clear_traversal(vehicle_id)` and **immediately `start_traversal()` again** for the *new* current segment: `start_traversal(vehicle_id, current_segment.split("_")[0], current_state["timestamp"], current_segment)` — so traversal tracking is continuous/self-perpetuating as long as the vehicle keeps moving onto new segments, independent of explicit stop events.

### OPERATIONAL TRAVERSAL BOOTSTRAP block — exact conditions
```python
if (
    not active_traversal
    and previous_state
    and movement_state == "between_stops"
    and previous_movement_state == "between_stops"
    and speed > 5
    and has_forward_progress
    and distance_to_stop > 150
):
```
- Only runs if there is currently **no** active traversal for the vehicle.
- Requires both current and previous `movement_state == "between_stops"` (stable mid-route state, two ticks running).
- `speed > 5`.
- `has_forward_progress` — current `progress` strictly greater than previous `progress`.
- `distance_to_next_stop > 150` (i.e. not near a stop — avoids double-bootstrapping right as a vehicle approaches/leaves).
- When triggered: reconstructs the **origin** stop_id by taking `current_sequence - 1` and looking it up in `stops_by_sequence`; if that lookup fails, falls back to parsing the origin out of the current `segment_id` string (`segment_id.split("_")[0]`). Then calls `start_traversal(vehicle_id, origin_stop_id, current_state["timestamp"], current_state["segment_id"])`.
- Purpose: recovers traversal tracking for a vehicle that's mid-segment when the engine first starts observing it (e.g. simulation start mid-route, or after a traversal was cleared by an anomaly) — without this, such a vehicle would never get a `segment_completed`/`travel_time` for its first segment because no `stop_departure` event would ever have been seen for it.

### How `stop_arrival` closes a traversal
In the per-event loop at the bottom of `process_traversal_lifecycle`:
```python
elif event_type == "stop_arrival":
    stored = get_active_traversal(vehicle_id)
    if not stored: continue
    if stored["segment_id"] != current_state["segment_id"]:
        clear_traversal(vehicle_id); continue
    ... compute travel_time, build segment_completed (completion_method: "stop_arrival") ...
    clear_traversal(vehicle_id)
```
- If the traversal's recorded `segment_id` doesn't match the vehicle's current segment at arrival time, the traversal is discarded **without** producing a `segment_completed` (treated as stale/mismatched tracking — protects against firing a `segment_completed` for the wrong segment).
- Otherwise computes `travel_time = arrival_timestamp - stored.departure_time`min; if `<= 0`, clears and skips (no event); else builds `segment_completed` with `completion_method: "stop_arrival"`, `from_stop_id = stored["from_stop_id"]`, `to_stop_id = stop_id` (the arrival event's stop), `segment_id = stored["segment_id"]`. Always clears the traversal afterward.

### `travel_time` computation
Always `(t2 - t1).total_seconds()` where `t1`/`t2` come from `datetime.fromisoformat()` on the stored departure time and the relevant current timestamp — used identically in all three completion paths (segment-transition completion, stop-arrival completion, and the dwell-lifecycle's own arrival-triggered completion in §3.7). Non-positive results are discarded (no event fired) in every path except the dwell-lifecycle one, which doesn't check positivity at all (see known bug below).

### `from_stop_id` / `to_stop_id` / `segment_id` relationship — known inconsistency
- `segment_id` follows the convention `f"{from_stop_id}_{to_stop_id}"` when built fresh from GTFS data in `reference/loader.py`.
- But the **segment-transition-completion** path derives `to_stop_id` by string-splitting the **stored** `segment_id` (`stored_segment.split("_")[1]`) rather than reading it off `current_state` — this is correct only as long as `segment_id` truly always follows that naming convention; if any stop_id itself ever contained an underscore, this split would silently produce a wrong stop_id (some GTFS stop_ids, e.g. `"CTA_M_112"`-style ids seen in this project's test fixtures, **do** contain underscores — this is a real, latent parsing hazard, not just theoretical, given the route id format observed in the codebase/commit history).
- The **stop-arrival-completion** and **dwell-lifecycle** paths instead use the event's own `stop_id` for `to_stop_id`, which is more robust but means the three completion paths derive `to_stop_id` from two different sources of truth depending on which path fires, a documented inconsistency in the lifecycle design.

## 3.7 Dwell lifecycle — full detail

[event_engine/dwell_lifecycle.py](../event_engine/dwell_lifecycle.py) `process_dwell_lifecycle(events, current_state)`.

- **Dwell start detection**: on a `stop_arrival` event, `start_dwell(vehicle_id, stop_id, timestamp)`.
- **`dwell_time` computation**: on the matching `stop_departure` event (same stop_id check), `dwell_time = departure_timestamp - arrival_timestamp` — see §3.4.
- **When dwell fires `segment_completed`**: Notably, this module **also** independently fires `segment_completed` on the **arrival** side (not just `traversal_lifecycle.py`'s arrival handling) — inside the `stop_arrival` branch:
```python
if event_type == "stop_arrival":
    start_dwell(...)
    stored = get_active_traversal(vehicle_id)
    if stored:
        travel_time = arrival_ts - stored.departure_time   # NOTE: no <=0 check here
        ... build "segment_completed" with no "completion_method" key in metrics ...
        clear_traversal(vehicle_id)
```
- **This duplicates** the `stop_arrival` handling already done in `process_traversal_lifecycle` (§3.6) — both modules check `get_active_traversal`, both compute `travel_time` from the same stored departure_time, and both call `clear_traversal`. Since `process_event()` (§3.1) calls `process_traversal_lifecycle` *first* (which would have already cleared the traversal on `stop_arrival` if conditions matched), by the time `process_dwell_lifecycle` runs, `get_active_traversal(vehicle_id)` is **usually already `None`** — so in the common case this duplicate branch is a no-op. But it is **not always** a no-op: if `process_traversal_lifecycle`'s `stop_arrival` branch hit its `stored["segment_id"] != current_state["segment_id"]` mismatch path (which clears without firing an event) or any other early-`continue`, the traversal could still be present, OR if the traversal was started by some other path *between* the two function calls — though within one `process_event()` call there's no intervening state change, so the realistic overlap window is narrow. The exception-swallowing (`except Exception: pass`) here is broader than the traversal module's own try/except (which logs), so a failure here is **silently** dropped with no print at all.

## 3.8 `builder.py` — `build_event()`

```python
def build_event(raw_event, current_state):
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": raw_event.get("event_type"),
        "vehicle_id": current_state.get("vehicle_id"),
        "route_id": current_state.get("route_id"),
        "timestamp": current_state.get("timestamp"),
        "stop_id": raw_event.get("stop_id"),
        "from_stop_id": raw_event.get("from_stop_id"),
        "to_stop_id": raw_event.get("to_stop_id"),
        "segment_id": raw_event.get("segment_id"),
        "stop_sequence": current_state.get("stop_sequence"),
        "metrics": raw_event.get("metrics", {}),
        "confidence": raw_event.get("confidence_override", current_state.get("confidence", "medium")),
        "source": current_state.get("source"),
        "simulation_flag": current_state.get("simulation_flag")
    }
```
- Generates the event's own UUID4 `event_id`.
- **Every** event gets the **current** vehicle's `vehicle_id`/`route_id`/`timestamp`/`stop_sequence`/`source`/`simulation_flag` stamped on, regardless of what the raw event actually semantically refers to — e.g. a `segment_completed` event fired from the traversal-completion path gets `timestamp = current_state["timestamp"]` (the time the *completion was detected*, i.e. arrival/transition time) and `stop_sequence = current_state["stop_sequence"]` (the vehicle's *current* sequence at detection time) even though the event describes something that happened over the *preceding* segment — this is intentional (events are stamped at detection time) but means `stop_sequence` on a `segment_completed`/`segment_travel` event doesn't necessarily correspond to either endpoint of `from_stop_id`/`to_stop_id` cleanly; consumers needing the originating sequence must derive it from `from_stop_id`/`to_stop_id` via the route reference rather than trusting the event's own `stop_sequence` field.
- `confidence` defaults to the current state's confidence but can be force-overridden per-raw-event via `confidence_override` (only the reverse-segment-travel detector uses this, forcing `"low"`).
- This function is the **single point** where the raw, ad-hoc dicts produced by detectors/lifecycle modules get normalized into the full `TransitEvent`-shaped contract that Component 1 persists.

## 3.9 `active_traversals` dict — exact structure

(repeated from §3.6 for completeness) `vehicle_id -> {"from_stop_id": str, "departure_time": <isoformat str>, "segment_id": str}`. One entry per vehicle, overwritten on each `start_traversal` call, deleted on `clear_traversal`.

## 3.10 `active_dwells` dict — exact structure

[event_engine/dwell_tracker.py](../event_engine/dwell_tracker.py): `vehicle_id -> {"stop_id": str, "arrival_time": <isoformat str>}`. One entry per vehicle, overwritten on each `start_dwell`, deleted on `clear_dwell`.

## Component 3 — Known bugs / global state / performance

**Known bugs / inconsistencies (status: present in code, not yet fixed):**
- **Duplicate `segment_completed` emission risk** between `traversal_lifecycle.py`'s `stop_arrival` handling and `dwell_lifecycle.py`'s `stop_arrival` handling — both compute and can emit `segment_completed` from the same `active_traversals` entry. Usually mitigated because `traversal_lifecycle` runs first and clears the traversal, but not airtight under the mismatch/early-continue paths described in §3.7. Not deduplicated downstream (Component 1's duplicate filter only dedups `segment_travel` by `(prev_seq, curr_seq)`, not `segment_completed`).
- **`to_stop_id` derived by string-splitting `segment_id`** in the segment-transition-completion path (§3.6) — breaks if any stop_id contains an underscore, which this project's own fixture data (`CTA_M_112`-style ids) suggests is a real possibility.
- **`travel_time <= 0` not checked** in the dwell lifecycle's own arrival-side `segment_completed` computation (§3.7), unlike the two other completion paths which do check and discard non-positive travel times.
- **`datetime.fromisoformat` dependency** on `departure_time`/`arrival_time`/`timestamp` always being ISO-format **strings** — if any call site passes a raw `datetime` object instead (worth auditing call sites in `vehicle_state/engine.py` and the API layer for exactly what type `timestamp` is at each point), parsing throws and is silently/loudly swallowed depending on which module catches it.
- **`current_delay` always 0` (Component 2 issue) means `detect_delay_event` can never actually fire** under the current pipeline — present but operationally inert.
- Reverse-segment-travel (jump back by 2+ sequences) emits only one `segment_travel` spanning the whole jump rather than per-hop events like the forward case — asymmetric handling.

**Module-level global state that must be reset between days / replay runs:**
- `event_engine.traversal_tracker.active_traversals` (`vehicle_id -> traversal`)
- `event_engine.dwell_tracker.active_dwells` (`vehicle_id -> dwell`)
- (Plus the Component 1 `last_transition_per_vehicle` dict in `services/observation_pipeline.py`, and the **duplicate, unused** copy of the same name in `api/routes/vehicle.py`.)
- (Plus Component 2's two trackers, §2 above.)

None of these are persisted or keyed by simulated day — a long-running process or a multi-day bulk replay must explicitly clear all of: `route_cache` (safe to keep — static reference data), `last_transition_per_vehicle`, `movement_transition_tracker`, `vehicle_operational_memory`, `active_traversals`, `active_dwells` between simulated days, or restart the process per day, to avoid leaking state across day boundaries (e.g. a traversal still "active" from 23:59 on day N silently completing against a day N+1 observation with a huge bogus `travel_time`, since timestamps are not validated for plausibility (§1.5 — the staleness check is disabled) and the `travel_time <= 0` guard only catches *negative* time deltas, not unreasonably large positive ones spanning a day boundary).

**Performance considerations:**
- Both lifecycle passes (`traversal_lifecycle.py`, `dwell_lifecycle.py`) iterate the already-built `events` list (small, typically 0–2 items) per observation — negligible cost.
- All trackers are O(1) dict lookups — no scalability concern per-observation; the only growth concern is the same unbounded-dict-size issue noted for Component 2.
- The segment-transition-completion block runs unconditionally near the top of `process_traversal_lifecycle` for **every** observation that has an active traversal, even when no events fired in the current tick — meaning `segment_completed` events can be generated **without** any corresponding `stop_arrival`/`stop_departure`/`segment_travel` event existing for that same tick, purely from Component 2's segment-matching changing between ticks. This is by design (continuous traversal tracking) but means downstream consumers must not assume `segment_completed` only co-occurs with other event types.

---

# Cross-Component Summary (relevant for ETA engine design)

- **Six independent in-process global dicts** carry state between observations: `route_cache`, `last_transition_per_vehicle` (Component 1); `movement_transition_tracker`, `vehicle_operational_memory` (Component 2); `active_traversals`, `active_dwells` (Component 3). None have TTL/eviction; all must be considered when designing day-boundary resets or multi-process/multi-replica deployment (none of this state is shared across processes — an ETA engine reading from the DB only, not from these in-memory structures, is the safe integration point).
- **The only durable, cross-process state** is what's written to `TransitObservation`, `TransitEvent`, and `VehicleLiveState` tables. An ETA engine should consume `TransitEvent` rows (especially `segment_completed.metrics.travel_time` and `dwell_time.metrics.dwell_time`) plus `VehicleLiveState` current position/progress — not the in-memory trackers.
- **`current_delay`/delay events are inert** (always 0) — an ETA engine cannot rely on existing delay computation; it would need to compute delay itself from scheduled vs. actual times.
- **`segment_completed` can be duplicated or have a parsing-fragile `to_stop_id`** — an ETA engine aggregating historical segment travel times should be defensive: prefer `from_stop_id`/`to_stop_id` from the event row directly (already persisted, post-split) but be aware some rows may have come from the underscore-split path and could be wrong if any stop_id contains `_`.
- **`stop_sequence` on events is "current sequence at detection time," not necessarily the sequence of either endpoint** — don't join naively on it; join on `from_stop_id`/`to_stop_id`/`segment_id` instead.
