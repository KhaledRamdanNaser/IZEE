# CLAUDE.md — IZEE Transit Management System
# Full Project Context for Claude Code

> This file is the single source of truth for all locked design decisions, data contracts,
> component boundaries, and academic context for the IZEE project.
> Read this fully before making any suggestion or code change.

---

## 1. Academic Context

| Field | Value |
|---|---|
| University | Arab Academy for Science, Technology, and Maritime Transport (AAST), Cairo |
| Supervisors | Dr. Ahmed Dahroug, Dr. Menna Kamel |
| Team | Khaled Mohamed Ramdan (221006703), Mohamed Ahmed Salah (221006412), Omar Ahmed Mohamed (221006709), Youssef Osama Mohamed (221006116), Sherif Ahmed Gomaa (221006812) |
| Project | IZEE – Unified Transit Management System (UTMS) |
| Scope | Proof-of-concept for Greater Cairo public transit under low-infrastructure conditions |
| Stack | Python / FastAPI / PostgreSQL (port 5433) / SQLAlchemy / Pydantic |

---

## 2. Project Purpose

IZEE addresses fragmented public transport and absence of AVL infrastructure in Greater Cairo.
It serves **4 user roles**: passengers, drivers, supervisors, and control center operators.
The system uses mobile-based GPS (crowdsensing + driver app), simulation, and predictive analytics
to estimate vehicle positions and arrival times **without dedicated hardware**.

**This is a graduation project proof-of-concept — not a production system.**
Prioritize correctness, academic soundness, and demonstrability over performance optimization.

---

## 3. Full System Architecture Pipeline (LOCKED)

```
Reference Management
        ↓
Simulation / Driver App / AVL (future)
        ↓
Transit Data Ingestion
        ↓
Vehicle State Engine
        ↓
Event Engine
        ↓
Data Manager  (stores everything)
        ↓
    ┌───┴───┐
ETA Engine  Alert Engine
    └───┬───┘
        ↓
Routing Engine
        ↓
API Layer (Passenger / Driver / Supervisor / Control Center)
```

---

## 4. Component Boundaries (STRICTLY LOCKED)

### 4.1 Transit Data Ingestion
- **Accepts:** TransitObservation from any source (driver app, simulation, crowdsensing, future AVL)
- **Output contract:** `TransitObservation` only
- **Must NOT:** produce VehicleState, TransitEvent, or ETA directly

### 4.2 Simulation Module
- **Purpose:** Generate synthetic GPS traces identical in format to real inputs
- **Output:** `TransitObservation` ONLY — never VehicleState, TransitEvent, or ETA
- **Critical rule:** If simulation produces final outputs → you are testing the simulation.
  If simulation produces raw inputs → you are testing the system. Always the latter.

### 4.3 Vehicle State Engine
- **Purpose:** Continuous description of vehicle reality within the transit network
- **Output:** `VehicleState` stream (continuous, every update)
- **Must NOT:** emit events, detect arrivals/departures
- **Inputs:** TransitObservation + route geometry from Reference Management

### 4.4 Event Engine
- **Purpose:** Convert state transitions into discrete, meaningful transit events
- **Output:** `TransitEvent` (discrete, only on state change)
- **Core logic:** `IF previous_state ≠ current_state → evaluate → possibly emit event`
- **Must NOT:** modify VehicleState, recompute movement, rely on raw GPS

### 4.5 Alert Engine
- **Purpose:** Convert raw operational events into user-facing alerts via rule-based logic
- **Output:** `Alert`
- **Rule:** `Event Engine → produces facts | Alert Engine → produces decisions`
- **Must NOT:** detect events, predict ETA, process GPS

### 4.6 Data Manager
- **Purpose:** System memory + knowledge base. Persists all runtime data.
- **Stores:** TransitObservations, VehicleStates, TransitEvents, ETAs, SegmentStatistics
- **Critical:** Offline batch job computes `SegmentStatistics` from TransitEvents
  → SegmentStatistics is what makes the system **predictive** (not just reactive)
- **Must NOT:** compute ETA, detect events, run ML models

### 4.7 Reference Management
- **Purpose:** Static authoritative knowledge of the transit network (from GTFS)
- **Contains:** stops, routes, trips, stop_times, shapes
- **Rule:** READ-ONLY at runtime. Loaded once, cached. Never part of real-time flow.

### 4.8 ETA Engine
- **Purpose:** Predict segment travel times and stop arrival times
- **Two output contracts (both locked):**
  - `SegmentEstimate` → Routing Engine only (edge weights)
  - `ServiceEstimate` → API/UI (human-readable ETA)
- **ETA types:**
  - Stop-ETA → produced by ETA Engine
  - Vehicle-ETA → produced by ETA Engine
  - Trip/Journey ETA → produced by **Routing Engine** (NOT ETA Engine)

### 4.9 Routing Engine
- **Purpose:** Compute optimal transit paths with ETA-enhanced costs
- **Algorithm:** CSA or RAPTOR (NOT Dijkstra — it ignores time-dependency)
- **Critical flow:** Query ETA Engine FIRST → update edge weights → THEN run routing
- **ETA is integrated BEFORE route selection, not after**

---

## 5. Locked Data Contracts

### TransitObservation
```json
{
  "observation_id": "uuid",
  "vehicle_id": "string",
  "timestamp": "ISO8601",
  "location": { "lat": "float", "lon": "float" },
  "speed": "float (optional)",
  "bearing": "float (optional)",
  "source": "enum: [driver_app, simulated, crowdsensed, avl]",
  "simulation_flag": "boolean",
  "trust_level": "enum: [high, medium, low]",
  "raw_payload": "object (optional)",
  "ingested_at": "timestamp"
}
```
Trust levels: AVL=high, driver_app=high, simulated=medium, crowdsensed=low

### VehicleState
```json
{
  "vehicle_id": "string",
  "route_id": "int",
  "trip_id": "string (nullable)",
  "timestamp": "ISO8601",
  "matched_position": { "lat": "float", "lon": "float" },
  "current_stop_id": "int (nullable)",
  "next_stop_id": "int",
  "stop_sequence": "int",
  "segment_id": "string",
  "segment_progress": "float (0→1)",
  "progress": "float (0→1 along route)",
  "distance_to_next_stop": "float",
  "speed": "float",
  "direction": "enum: [forward, backward, unknown]",
  "movement": "enum: [moving, stopped]",
  "movement_state": "enum: [between_stops, approaching_stop, at_stop, leaving_stop]",
  "current_delay": "float (seconds)",
  "confidence": "enum: [high, medium, low]",
  "source": "enum",
  "simulation_flag": "boolean"
}
```

### TransitEvent
```json
{
  "event_id": "uuid",
  "event_type": "enum: [stop_arrival, stop_departure, segment_travel, dwell_time, delay]",
  "vehicle_id": "string",
  "route_id": "int",
  "timestamp": "ISO8601",
  "stop_id": "int (optional)",
  "from_stop_id": "int (optional)",
  "to_stop_id": "int (optional)",
  "segment_id": "string (optional)",
  "stop_sequence": "int (optional)",
  "metrics": {
    "travel_time": "float (optional)",
    "dwell_time": "float (optional)",
    "delay": "float (optional)"
  },
  "confidence": "enum: [high, medium, low]",
  "source": "enum",
  "simulation_flag": "boolean"
}
```

### SegmentEstimate (ETA Engine → Routing Engine only)
```json
{
  "segment_id": "string",
  "predicted_travel_time": "float",
  "predicted_delay": "float",
  "confidence": "enum",
  "timestamp": "ISO8601"
}
```

### ServiceEstimate (ETA Engine → API/UI)
```json
{
  "vehicle_id": "string",
  "route_id": "int",
  "stop_id": "int",
  "stop_sequence": "int",
  "predicted_arrival_time": "ISO8601",
  "estimated_travel_time": "float",
  "delay": "float",
  "confidence": "enum",
  "model_version": "string",
  "timestamp": "ISO8601"
}
```

### SegmentStatistics (computed offline by Data Manager)
```json
{
  "segment_id": "string",
  "avg_travel_time": "float",
  "median_travel_time": "float",
  "variance": "float",
  "avg_dwell_time": "float",
  "sample_count": "int",
  "time_bucket": "enum: [peak, off_peak] (optional)",
  "last_updated": "ISO8601"
}
```

### Alert (Alert Engine output)
```json
{
  "alert_id": "uuid",
  "type": "enum: [delay, disruption, reroute, incident]",
  "severity": "enum: [low, medium, high]",
  "message": "string",
  "route_id": "int (optional)",
  "vehicle_id": "string (optional)",
  "location": { "lat": "float", "lon": "float" },
  "created_at": "ISO8601",
  "expires_at": "ISO8601 (optional)"
}
```

---

## 6. Movement State FSM (LOCKED THRESHOLDS)

| State | Condition |
|---|---|
| `at_stop` | distance ≤ 30m AND speed < 5 km/h |
| `leaving_stop` | transitioning FROM at_stop |
| `approaching_stop` | distance ≤ 150m (and not at_stop) |
| `between_stops` | everything else |

**Do not change these thresholds without explicit instruction.**

---

## 7. Event Detection Logic (LOCKED)

```python
IF previous.movement_state != at_stop AND current.movement_state == at_stop:
    → emit stop_arrival

IF previous.movement_state == at_stop AND current.movement_state != at_stop:
    → emit stop_departure

IF previous.segment_id != current.segment_id:
    → emit segment_travel

IF delay crosses level boundary:
    → emit delay event
```

Delay levels: none (<60s), minor (<180s), moderate (<300s), severe (≥300s)

---

## 8. Simulation Strategy (LOCKED)

**Primary method:** GTFS-based stochastic simulation

For each scheduled trip:
1. Use GTFS schedule as baseline timeline
2. Inject time-of-day congestion: peak +20–40%, off-peak +0–10%
3. Inject stop dwell times: uniform/normal 10–60s
4. Inject driver/traffic noise per segment
5. Inject rare large delays (low probability, high impact)
6. Output: TransitObservation ONLY with realistic delayed timestamps

**Output format:** `TransitObservation` only (simulation_flag=true, source="simulated")

**CRITICAL — Training Data Flow (LOCKED):**
Simulation NEVER produces ETA records, VehicleState, TransitEvents, or training labels directly.
The correct flow for generating ETA training data is:

```
Simulation → TransitObservation (with realistic delayed timestamps)
                    ↓
             Full pipeline processes observations
             (Ingestion → VehicleState → Event Engine)
                    ↓
             TransitEvents stored in DB
             (stop_arrival, stop_departure, dwell_time, segment_travel)
                    ↓
             Offline batch job reads TransitEvents
             → computes SegmentStatistics per segment
             (avg_travel_time, variance, avg_dwell_time)
                    ↓
             SegmentStatistics = ETA Engine training source
             (this is what makes the system predictive)
```

Rule 16.5 reinforces this: "Simulation data must flow through the pipeline —
never shortcut by injecting into later stages."

**Microbus simulation (LOCKED — different model):**
- Treat as frequency-based corridors, NOT scheduled trips
- Use TFC `shapes.txt` as ground truth corridor geometry
- Stochastic headways (normal dist, mean ~5min, std ~2min)
- Random dwell events every 300–600m (30% probability, 5–20s dwell)
- Speed noise: base_speed + traffic_noise + random_stop_events
- ETA output = range + LOW confidence
- **Never model microbuses as GTFS trips**

**SUMO:** Acknowledged as state-of-the-art but out of scope for this project.

---

## 9. ETA Model Strategy (LOCKED)

**Progressive approach (do NOT start with heavy DL):**
1. Baseline regression (MVP)
2. XGBoost / Random Forest (primary)
3. ARIMA for stable routes
4. LSTM only if sufficient historical data exists

**Features:**
- time_of_day, day_of_week, peak_flag
- route_id, stop_sequence_index, segment_length, stops_remaining
- current_delay, historical_avg_speed, historical_variance

**Training data:** 100% synthetic initially, calibrated against NYC/CTA distributions.

**Transfer learning (optional):** Pre-train on city-agnostic features from NYC/CTA data,
normalize for Cairo (feature transfer — NOT full fine-tuning).

---

## 10. Routing Model (LOCKED)

- **Graph:** Time-dependent transit graph (nodes = stops + transfers, edges = ride/walk/wait)
- **Algorithm:** CSA or RAPTOR — NOT Dijkstra
- **Cost function:** `travel_time + wait_time + walk_time + predicted_delay_penalty`
  - `delay_penalty = predicted_delay × (1 / confidence_weight)`
- **ETA integration:** Query ETA Engine BEFORE routing → update edge weights → run algorithm
- **Missing GTFS-RT:** Static GTFS baseline + driver app GPS overlay; fallback to static
- **Microbus legs:** `cost = avg_headway/2 + distance/avg_speed`, confidence = LOW

---

## 11. ABT Offline Model (LOCKED)

**3 core principles:**
1. Boarding must never be blocked due to connectivity loss
2. No fare must be silently lost or duplicated
3. Backend is always the source of truth

**Offline flow:**
- Validator checks local cache → creates provisional transaction (offline_flag=true) → queues for sync
- On reconnect: idempotent reconciliation via transaction IDs (no double-charge)
- Negative balance allowed (policy decision), offline limits apply, backend ledger always wins

**This is transit-grade ABT — not banking-grade.**

---

## 12. Crowdedness Estimation (LOCKED)

- **Signal 1:** Fare validations = HIGH confidence, lower bound on occupancy
- **Signal 2:** Passenger GPS telemetry = LOW confidence, proxy only
- **Filtering:** Device must be spatially co-located AND kinematically synchronized with bus
- **Output:** Low / Medium / High (qualitative only, always labeled "estimated")
- No individual tracking. No identity inference. Aggregation at vehicle/segment level only.

---

## 13. Datasets (7 total)

| ID | Name | Source | Notes |
|---|---|---|---|
| D1 | GTFS Static | Transport for Cairo (TFC), 2017–18 | Backbone. Routes, stops, trips, shapes, schedules |
| D2 | Fleet Inventory | System-managed (simulated) | vehicle_id, type, capacity, status, validators |
| D3 | ABT Accounts + Transactions | System-managed (simulated) | offline_sync_flag field required |
| D4 | Real-Time GPS (AVL) | Simulated from GTFS shapes; fallback NYC/CTA | trust_score + simulation_flag fields required |
| D5 | Incidents + Alerts | System-managed (simulated) | |
| D6 | ETA Records | System-derived (not external) | Treated as derived data, not source dataset |
| D7 | Users + Roles | System-managed (simulated) | 5 roles: passenger, driver, supervisor, control_center, admin |

---

## 14. API Layer Summary (LOCKED)

### Passenger API
- Network exploration (routes, stops, modes)
- Real-time vehicle tracking
- ETA: stop-level, vehicle-level, nearby
- Trip planning (GET /plan-trip)
- Trip tracking (GET /trip/{trip_id}/eta)
- ABT wallet (top-up, validate fare, balance, transactions)
- Alerts and notifications
- Incident reporting

### Driver API
- `POST /vehicle/location` — **system heartbeat**, uses TransitObservation contract
- `POST /trip/start` and `POST /trip/end`
- `GET /driver/{driver_id}/duties`
- `POST /driver/incidents`
- `GET /driver/{driver_id}/alerts` (receives instructions from control center)
- `POST /vehicle/status`

### Supervisor API
- Area performance monitoring
- Vehicle tracking (uses Events, NOT raw VehicleState — events are meaningful operational facts)
- Incident management and reporting
- Driver coordination and messaging

### Control Center API
- `GET /control/dashboard/overview` — system KPIs (active_vehicles, avg_delay, on_time_rate, system_status)
- Real-time fleet monitoring
- Service performance and analytics
- Incident management (get/update/resolve)
- Broadcast alerts and driver instructions
- Operational actions (reroute, adjust service frequency)
- Logs and report generation
- **Role:** Global authority — observe → decide → act loop

---

## 15. Known Technical Debt (Do Not Fix Without Being Asked)

These are tracked intentionally in `docs/future_improvements.md`:

1. In-memory dwell/segment trackers — should be Redis for persistence
2. Delay computation injected externally — should compare against GTFS schedule
3. Map matching — naive nearest-segment; HMM-based is deferred
4. Progress stabilization thresholds — heuristic, adaptive improvement deferred
5. Duplicate event filtering — currently in API layer, should move to Event Engine
6. Dwell event generation — partially in API, should be fully in Event Engine
7. Pydantic response schemas — currently manual dict responses
8. Structured logging — currently print() statements
9. GPS jitter handling — basic, Kalman filter deferred

**Do not proactively suggest fixing these unless the user asks.**

---

## 16. General Rules for Claude Code in This Project

1. **Never contradict locked decisions** listed in this file without explicit user confirmation.
2. **Never add unrequested features** — this is a graduation project with defined scope.
3. **Preserve existing logic** — suggest edits only with clear explanations of why.
4. **Academic tone matters** — code, comments, and documentation should reflect a serious academic project.
5. **Simulation data must flow through the pipeline** — never shortcut by injecting into later stages.
6. **All components respect data contracts** — never pass raw dicts where a typed contract is defined.
7. **Confidence levels must propagate** — every output that has uncertainty must carry a confidence field.
8. **simulation_flag must be preserved** — never strip or ignore this field in any processing step.

---

*Last updated: May 2026 — Generated from full project design documents.*
