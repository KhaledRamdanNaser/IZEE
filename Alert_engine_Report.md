IZEE Technical Implementation Report
Event Engine, Service Observation Pipeline, and Alert Engine Integration Handoff
Generated: 2026-06-18 15:45
Scope: This document is based on the current D:\GradProject\IZEE repository contents, implemented scripts, database observations, and the latest GTFS-based CMD pipeline test. Git commit references were unavailable because Git reported a Windows dubious-ownership safety block in this sandbox, so references are given by file path.
 
Table of Contents

Right-click the table of contents in Word and choose Update Field to refresh page numbers.
 
1. Executive Summary
IZEE is a transit management pipeline that ingests simulated or vehicle-location observations, matches them to GTFS route geometry, derives vehicle state, detects operational events, aggregates segment statistics, and generates passenger/control-center alert decisions.
Current result: The GTFS-based CMD test runs through generated observations, Vehicle State Engine, Event Engine, segment statistics, and Alert Engine. The latest run processed 88 observations, created 30 transit events, computed 1 segment-statistics cell, and inserted 4 alerts: 3 medium delay alerts and 1 medium disruption alert.
•	Main objective: convert vehicle observations into reliable operational decisions.
•	Primary database: PostgreSQL database izee_db on localhost:5433 for this machine.
•	Core pipeline: Observation source -> Service Observation Pipeline -> Vehicle State Engine -> Event Engine -> transit_events -> segment_statistics -> Alert Engine -> alerts.
•	Current limitation: dwell_issue alert generation is blocked because the full pipeline test still does not produce dwell_time events.
2. Current System Architecture
2.1 High-Level Architecture Diagram
flowchart TD
    A[SUMO / Generated / API Observations] --> B[Validation and Normalization]
    B --> C[Service Observation Pipeline]
    C --> D[Vehicle State Engine]
    D --> E[Event Engine Detectors]
    E --> F[Traversal and Dwell Lifecycle]
    F --> G[(transit_events)]
    G --> H[segment_stats.py]
    H --> I[(segment_statistics)]
    G --> J[Alert Engine]
    I --> J
    J --> K[(alerts)]
    K --> L[Passenger / Driver / Supervisor / Control APIs]
2.2 Component Descriptions
Component	Files	Responsibility
Input and replay	scripts/bulk_replay.py, scripts/generate_gtfs_pipeline_observations.py	Loads JSONL observations, normalizes flat or nested location formats, and replays them through the service pipeline.
Validation	utils/validators.py, schemas/*.py	Checks timestamps, lat/lon, speed, and bearing before state processing.
Reference loading	reference/loader.py, gtfs/*	Loads route-specific stops and segments using route_id and direction.
Vehicle State Engine	vehicle_state/*.py	Map-matches observations, computes progress, stop ownership, movement state, and live state.
Event Engine	event_engine/*.py	Detects stop arrivals/departures, segment transitions, traversal completion, and dwell lifecycle events.
Segment statistics	scripts/segment_stats.py	Aggregates segment_completed events into avg/median/std/sample_count cells.
Alert Engine	alert_engine/*.py	Turns events and statistics into delay, dwell_issue, and disruption alerts.
Database	models/*.py, database/connection.py	Stores observations, live state, transit events, segment stats, and alerts.

2.3 Dependencies and Integrations
•	Python runtime with SQLAlchemy and psycopg2 connectivity.
•	PostgreSQL on localhost:5433, database izee_db, user postgres, local password 1234.
•	GTFS static files under gtfs/: agency, routes, trips, stops, stop_times.
•	Environment overrides: IZEE_CONVERTED_DIR and IZEE_REPLAY_FILES for replay file selection.
3. Work Completed
Order	Completed work	Before	Change made	Why required	Expected impact
1	PostgreSQL local connection fixed	Project expected localhost:5432.	database/connection.py now points at localhost:5433.	Postgres service accepted connections on 5433.	Application can connect to local izee_db.
2	Alert Engine implemented	alert_engine files were empty skeletons.	Added model, config, rules, deduplicator, aggregator, engine, and runner.	Needed to satisfy the Alert Engine build document.	Batch alert generation from transit_events and segment_statistics.
3	Alert table registration	init_db.py did not import alert_engine.models.	Added import alert_engine.models.	Required Base.metadata.create_all to include alerts.	alerts table can be created through normal init.
4	Smoke test created	Only manual DB checks existed.	Added scripts/alert_engine_smoke_test.py.	Needed isolated Alert Engine verification.	Verified delay, dwell_issue, disruption, and dedup logic in isolation.
5	GTFS-based observation generator	Smoke test used artificial SMOKE_* database rows.	Added generator using CTA_M_112 GTFS stops.	Needed realistic pipeline input matching user observation shape.	Generated flat lat/lon/speed/bearing rows from GTFS route coordinates.
6	Bulk replay input flexibility	Hardcoded external path and nested speed_kmh/location.	Added IZEE_CONVERTED_DIR, IZEE_REPLAY_FILES, flat lat/lon/speed support.	Required CMD testing with local generated data.	Replay can use generated local JSONL.
7	Database schema sync	Existing DB tables were older than SQLAlchemy models.	Added scripts/sync_db_schema.py.	create_all does not alter existing tables.	Unblocked replay against existing local DB.
8	GTFS test runner	Pipeline steps had to be run manually.	Added scripts/run_gtfs_pipeline_test.cmd.	User wanted CMD-visible testing.	Single command runs generation, init, schema sync, replay, stats, alerts, SQL verification.
9	Event departure lineage improvement	stop_departure used previous next_stop_id only.	Pipeline carries current_stop_id and detector prefers it for departure.	Dwell lifecycle needs departure stop to match arrival stop.	Improves correctness, but dwell_time remains blocked by stop ownership behavior.

4. Event Engine Detectors - Changes, Rationale, and Outcomes
Detector	Purpose	Inputs	Detection logic	Failure handling	Change status
detect_stop_events	Detects stop_arrival and stop_departure from movement_state transitions.	current_state, previous_state	arrival: curr=at_stop and prev!=at_stop; departure: prev=at_stop and curr!=at_stop.	Returns empty list if no transition.	Changed departure stop_id to prefer previous_state.current_stop_id.
detect_segment_transition	Detects forward, skipped, and reverse segment transitions.	current_state, previous_state, route_reference	same sequence=no event; small reverse ignored; larger reverse emits low-confidence segment_travel; forward gaps emit segment_travel.	Missing stop map entries are skipped.	No direct change; documented as central behavior.
detect_delay_event	Detects delay level transitions from current_delay.	current_state, previous_state	Maps delay into minor/moderate/severe and emits only when level changes.	No event if delay values missing.	No direct change; Alert Engine does not depend on these delay events.

4.1 Detector Processing Flow
sequenceDiagram
    participant VS as Vehicle State
    participant EE as Event Engine
    participant DS as detect_stop_events
    participant DT as detect_segment_transition
    participant DD as detect_delay_event
    participant BL as build_event
    participant TL as traversal_lifecycle
    participant DL as dwell_lifecycle

    VS->>EE: current_state + previous_state + route_reference
    EE->>DS: movement_state transition
    EE->>DT: stop_sequence transition
    EE->>DD: current_delay transition
    DS-->>EE: raw stop events
    DT-->>EE: raw segment_travel events
    DD-->>EE: raw delay events
    EE->>BL: standardize raw events
    EE->>TL: generate segment_completed
    EE->>DL: generate dwell_time when arrival/departure match
    EE-->>DB: TransitEvent rows
4.2 Original Implementation and Limitations
•	Stop departure used previous_state.next_stop_id, which can identify the next stop rather than the stop where a vehicle was dwelling.
•	The Event Engine emits print-heavy debug output rather than structured logs.
•	detect_delay_event emits event_type delay, but the Alert Engine design relies on segment_completed and segment_statistics.
•	Dwell lifecycle requires stop_arrival and stop_departure to share the same stop_id; stop ownership changes near segment boundaries can drop dwell_time.
4.3 Changes Implemented
# services/observation_pipeline.py
previous_state = {
    "progress": db_state.progress,
    "movement_state": db_state.movement_state,
    "current_stop_id": db_state.current_stop_id,
    "next_stop_id": db_state.next_stop_id,
    "segment_id": db_state.segment_id,
    "stop_sequence": db_state.stop_sequence,
    "current_delay": db_state.current_delay,
}

# event_engine/detectors.py
"stop_id": (
    previous_state.get("current_stop_id")
    or previous_state.get("next_stop_id")
)
4.4 Before vs After Comparison
Previous behavior	Updated behavior	Reason for change	Result achieved
stop_departure stop_id came from previous next_stop_id only.	stop_departure prefers previous current_stop_id and falls back to next_stop_id.	Dwell lifecycle needs departure from the same stop that generated arrival.	Improved lineage; dwell_time still blocked by stop ownership in current generated scenario.
Previous state carried limited fields.	Previous state includes current_stop_id and segment_id.	Detectors and lifecycle processors need stop/segment ownership context.	Improves correctness of lifecycle decisions.
Debug prints were scattered.	Still present and documented as technical debt.	Structured logging was outside this change set.	Operational visibility remains noisy but useful locally.

5. Service/Observation Pipeline - Changes, Rationale, and Outcomes
Stage	Inputs	Outputs	Internal logic	Failure handling/performance
Ingestion	API payload or JSONL raw observation.	Standard observation dict.	Normalizes timestamp, lat/lon, speed, bearing, route_id, direction, scenario metadata.	Malformed JSON lines are skipped in bulk replay.
Validation	Observation fields.	Validated fields.	validate_location, validate_speed, validate_bearing.	Raises exception and rolls back current batch if processing fails.
Route reference routing	route_id + direction.	route_reference with stops and segments.	route_cache keyed by (route_id, direction).	Missing trip raises route-reference exception.
Previous state loading	vehicle_id.	previous_state dict.	Uses vehicle_state_cache in bulk replay, otherwise DB query.	Cache avoids per-observation DB round trip.
Vehicle state processing	observation + previous_state + route_reference.	current vehicle state.	Map matching, projection, progress stabilization, movement-state detection.	validate_vehicle_state clamps invalid state.
Event processing	current state + previous state + route reference.	TransitEvent dictionaries.	Runs detectors, traversal lifecycle, dwell lifecycle.	Duplicate segment_travel filtered by last_transition_per_vehicle.
Persistence	observation mapping, events, live state.	transit_observations, transit_events, vehicle_live_state.	bulk_insert_mappings for observations; db.add for events/live state.	Savepoint per batch; failed batch rolled back and counted.

5.1 Updated Sequence Diagram
sequenceDiagram
    participant R as bulk_replay.py
    participant P as observation_pipeline
    participant Ref as reference.loader
    participant VS as vehicle_state.engine
    participant EE as event_engine.engine
    participant DB as PostgreSQL

    R->>R: read JSONL observation
    R->>R: normalize flat lat/lon/speed or nested location/speed_kmh
    R->>P: process_observation_pipeline(observation, db, cache, persist=False)
    P->>Ref: load_route_reference(route_id, direction)
    Ref-->>P: route stops + segments
    P->>P: load previous_state from vehicle_state_cache
    P->>VS: process_observation()
    VS-->>P: current vehicle state
    P->>EE: process_event(current_state, previous_state, route_reference)
    EE-->>P: event list
    P->>DB: add TransitEvent objects
    P->>DB: update VehicleLiveState
    R->>DB: bulk insert TransitObservation mappings
    R->>DB: commit batch
5.2 Pipeline Changes Analysis
Change	Original behavior	Updated implementation	Why changed	Result
Optional DB/session ownership	Pipeline always created/owned its own DB session.	process_observation_pipeline accepts db and owns_session flag.	Bulk replay needs batched transactions.	Supports API and replay paths.
Vehicle state cache	DB lookup per observation.	vehicle_state_cache optional dict keyed by vehicle_id.	Improve replay throughput.	Replay can process batches with less DB overhead.
persist_observation flag	Pipeline added observation ORM object per call.	Bulk replay passes persist_observation=False and bulk-inserts mappings.	Avoid one db.add per observation.	Improved replay performance.
Route cache key	Older comments indicate route-only cache.	Current cache key is (route_id, direction).	Direction-specific trips have different stop sequences.	Prevents wrong reference on same route opposite direction.
Previous state enrichment	Previous_state had progress, movement_state, next_stop_id, stop_sequence, current_delay.	Added current_stop_id and segment_id.	Needed by stop departure and lifecycle lineage.	Improves stop ownership context.
Bulk replay flat format support	Expected nested location and speed_kmh.	Accepts flat lat/lon/speed and fills defaults.	User observation format is flat.	Generated GTFS observations run through real pipeline.
Day reset	State could leak across replay days.	reset_day_state clears trackers and live state.	Vehicle IDs repeat across days.	Reduces stale state corruption.

6. Changes Made to the Pipeline
Modification	Original behavior	New behavior	Risks addressed	Benefits gained
IZEE_CONVERTED_DIR	Hardcoded external E: path.	Environment override selects local replay directory.	Missing external dataset path blocked tests.	Reproducible local CMD testing.
IZEE_REPLAY_FILES	Default TEST_FILES expected fixed files.	Environment variable constrains replay to generated file.	Missing day_5/day_6 files would fail.	Single-file integration test.
Schema sync script	create_all did not alter older tables.	ADD COLUMN IF NOT EXISTS for local tables.	Undefined column failures.	Existing local DB can run newer code.
GTFS generator	Smoke test inserted fake DB rows directly.	Generated observations from real GTFS CTA_M_112 stops.	Smoke data bypassed pipeline.	Tests Vehicle State and Event Engine path.
Cleanup script	Repeated tests could mix previous rows.	Deletes GTFS_* observations/events/live state and relevant alerts/stats.	Dedup and stale rows skewed results.	Repeatable integration test.

7. Alert Engine Analysis - Why the Alert Engine Is Blocked From Other Components
The Alert Engine is implemented and works when expected input events exist. The integration blockers are upstream data, schema, and event-production issues that prevent the Alert Engine from receiving complete inputs.
Blocker	Component	Technical evidence	Impact	Severity	Recommended fix	Estimated effort
Missing real replay dataset	bulk_replay.py / observation source	Original configured path E:\Last Semster\IZEE_SUMO\converted was not found. A local GTFS generator was created as substitute.	Cannot validate production-scale SUMO replay.	High	Locate/regenerate real converted JSONL files or standardize generated fixtures.	0.5-1 day once files are available.
Older database schema	PostgreSQL tables	transit_observations and vehicle_live_state missed model columns until sync script.	Replay failed before Event Engine could create events.	High	Use migrations or rebuild DB; keep sync_db_schema.py as dev bridge.	1-2 days for migration baseline.
dwell_time not produced in full test	Event Engine dwell lifecycle / stop ownership	Latest run: dwell events checked = 0; alerts have delay/disruption only.	Alert Engine cannot create dwell_issue alerts in real pipeline.	High	Fix stop ownership around boundaries and add Dwell.json lifecycle tests.	1-2 days.
Segment statistics sample threshold below target	segment_stats.py / generated data	sample_count=14 for CTA_M_112 weekday peak segment 679_1994; target is 30.	Stats are integration-grade but below reliability target.	Medium	Generate >=30 baseline samples or use real replay data.	0.5 day.
DB-heavy Alert Engine lookup	alert_engine/engine.py	_fetch_segment_stats queries DB inside loop.	May be slow for millions of events and couples decisions to storage.	Medium	Prefetch segment_statistics cache.	0.5-1 day.
No temporal window for disruption	alert_engine/aggregator.py	Groups delay alerts by route without event-time clustering.	Can group delays across long periods.	Medium	Group by route plus rolling 10-15 minute window.	0.5 day.

8. End-to-End Event Flow
flowchart LR
    S[Observation Source] --> V[Validation]
    V --> R[Route Reference]
    R --> VS[Vehicle State]
    VS --> DE[Detectors]
    DE --> TL[Traversal Lifecycle]
    DE --> DL[Dwell Lifecycle]
    TL --> TE[(transit_events)]
    DL --> TE
    TE --> SS[segment_stats]
    SS --> ST[(segment_statistics)]
    TE --> AE[Alert Engine]
    ST --> AE
    AE --> AL[(alerts)]
    AL --> API[Notification/Consumer APIs]

    V -. fail .-> F1[Validation exception]
    R -. fail .-> F2[Missing route reference]
    VS -. fail .-> F3[Bad state / matching]
    DE -. drop .-> F4[No detector condition]
    DL -. drop .-> F5[Arrival/departure mismatch]
    SS -. weak .-> F6[Low sample_count]
    AE -. skip .-> F7[Missing stats / dedup]
Known failure/drop locations: validation errors, route-reference lookup failures, batch rollback in bulk replay, no detector condition matched, traversal/dwell lifecycle mismatch, low segment-stat samples, missing segment_statistics rows, and Alert Engine deduplication.
9. Technical Debt and Risks
Risk area	Risk	Evidence	Mitigation
Architecture	Alert engine orchestration mixes SQL loading, rule evaluation, deduplication, and storage.	alert_engine/engine.py contains fetch, loop, dedup, and insert logic.	Split into data_loader.py, repository.py, pure rules.py.
Reliability	Dwell lifecycle is fragile near stop/segment boundary ownership.	GTFS test still produced zero dwell_time events.	Add deterministic dwell unit tests and improve stop ownership tracking.
Scalability	Segment stats queried per segment_completed event.	_fetch_segment_stats called inside loop.	Prefetch stats cache keyed by segment_id/route/direction/day_type/time_period.
Data quality	Sample_count below target in generated integration test.	segment_stats.py warning: sample_count 14, samples_needed 16.	Generate more samples or validate with full replay dataset.
Observability	Debug prints instead of structured logging.	Multiple print statements in detectors and pipeline.	Use logging module with route/vehicle/event context.
Database management	No migrations; schema drift required sync script.	Undefined column errors surfaced during CMD run.	Introduce Alembic migrations or controlled rebuild scripts.
Security/config	DB password and port hardcoded.	database/connection.py contains local URL.	Move DATABASE_URL to environment variable.

10. Recommendations
Priority	Recommendation	Expected impact	Complexity	Estimated effort
Priority 1 - Critical	Fix dwell_time event generation with tests covering arrival, dwell, departure at the same GTFS stop.	Unblocks dwell_issue alerts in full pipeline.	Medium	1-2 days.
Priority 1 - Critical	Create database migrations or a clean rebuild path.	Removes schema drift failures.	Medium	1-2 days.
Priority 1 - Critical	Run against real SUMO converted replay files.	Validates actual system behavior.	Depends on data availability	0.5 day after data is available.
Priority 2 - High	Refactor Alert Engine into data_loader, repository, pure rules, aggregator, engine.	Improves maintainability and future streaming readiness.	Medium	1 day.
Priority 2 - High	Add temporal-window disruption aggregation.	Prevents false route-level disruptions.	Low/Medium	0.5 day.
Priority 2 - High	Add confidence scoring based on sample_count/std_travel_time.	Makes alert reliability explainable.	Low	0.5 day.
Priority 3 - Medium	Replace debug prints with structured logging.	Improves operational visibility.	Low/Medium	1 day.
Priority 3 - Medium	Move DB settings to environment variables.	Improves portability and security hygiene.	Low	0.25 day.

11. Appendix
11.1 Important Files and Folders
Path	Purpose
event_engine/detectors.py	Event detectors
event_engine/engine.py	Event engine orchestrator
event_engine/traversal_lifecycle.py	Traversal lifecycle
event_engine/dwell_lifecycle.py	Dwell lifecycle
services/observation_pipeline.py	Observation pipeline
scripts/bulk_replay.py	Bulk replay
scripts/generate_gtfs_pipeline_observations.py	GTFS observation generator
scripts/sync_db_schema.py	Schema sync
scripts/run_gtfs_pipeline_test.cmd	GTFS pipeline CMD runner
alert_engine/engine.py	Alert engine
alert_engine/rules.py	Alert rules
alert_engine/aggregator.py	Alert aggregator
alert_engine/deduplicator.py	Alert deduplicator
gtfs/	Static GTFS reference CSV files used for route/stop extraction.
local_replay_data/day_1_monday_observations.jsonl	Generated GTFS-based observations used by the CMD integration test.
models/	SQLAlchemy table models.

11.2 Environment Variables and Commands
set PYTHONPATH=D:\GradProject\IZEE
set IZEE_CONVERTED_DIR=D:\GradProject\IZEE\local_replay_data
set IZEE_REPLAY_FILES=day_1_monday_observations.jsonl
set PGPASSWORD=1234

cd /d D:\GradProject\IZEE
scripts\run_gtfs_pipeline_test.cmd
11.3 Latest CMD Test Evidence
Observations processed: 88
transit_events created: 30
segment_completed events created: 14
Errors: 0

Segment statistics:
CTA_M_112 / weekday / peak / 679_1994 -> sample_count 14

Alert Engine:
Segment events checked: 14
Dwell events checked: 0
Alerts created: 4
Delay alerts: 3
Disruptions: 1

Final alert distribution:
delay      medium   3
disruption medium   1
11.4 Selected Code References
Event detectors - event_engine/detectors.py
# event_engine/detectors.py

def detect_stop_events(current_state, previous_state):
    """
    Detect stop arrival and departure events
    """

    events = []

    prev_state = previous_state.get("movement_state") if previous_state else None
    curr_state = current_state.get("movement_state")

    # 🔍 DEBUG FIRST (before logic)
    print("---- DETECTOR DEBUG ----")
    print("previous_state:", previous_state)
    print("current_state:", current_state)
    print("prev_state:", prev_state)
    print("curr_state:", curr_state)

    # Stop Arrival
    if curr_state == "at_stop" and (prev_state != "at_stop"):
        print("✅ ARRIVAL CONDITION TRIGGERED")
        events.append({
            "event_type": "stop_arrival",
            "stop_id": current_state.get("next_stop_id")
        })

    # Stop Departure
    if prev_state == "at_stop" and curr_state != "at_stop":
        print("🚪 DEPARTURE CONDITION TRIGGERED")
        events.append({
            "event_type": "stop_departure",
            "stop_id": (
                previous_state.get("current_stop_id")
                or previous_state.get("next_stop_id")
            )
        })

    return events

from datetime import datetime


from datetime import datetime


def detect_segment_transition(current_state, previous_state, route_reference):
    """
    Detect segment transitions with:
    - normal movement
    - skipped stops
    - reverse movement (with oscillation filtering)
    """

    events = []

    if not previous_state:
        return events

    prev_seq = previous_state.get("stop_sequence")
    curr_seq = current_state.get("stop_sequence")

    if prev_seq is None or curr_seq is None:
        return events

    stops_map = route_reference.get("stops_by_sequence", {})

    # ⚫ SAME → no event
    if curr_seq == prev_seq:
        return events

    # 🔴 REVERSE MOVEMENT (with oscillation filter)
    if curr_seq < prev_seq:

        # 🔥 Ignore small reverse (likely GPS jitter)
        if prev_seq - curr_seq == 1:
            print("IGNORED: oscillation reverse")
            return events

        # Allow larger reverse movement
        events.append({
            "event_type": "segment_travel",
     

... [truncated in report; see repository file for full source]
Event engine orchestrator - event_engine/engine.py
# event_engine/engine.py

from event_engine.detectors import detect_stop_events
from event_engine.builder import build_event
from event_engine.detectors import detect_stop_events, detect_segment_transition
from event_engine.detectors import detect_delay_event
from event_engine.traversal_lifecycle import (
    process_traversal_lifecycle
)
from event_engine.dwell_lifecycle import (
    process_dwell_lifecycle
)
def process_event(current_state, previous_state, route_reference):
    """
    Main Event Engine function

    Input:
        current_state: VehicleState (dict)
        previous_state: VehicleState (dict)

    Output:
        List of events (can be empty)
    """
    events = []

    # 1. Detect stop events (ALWAYS allow)
    stop_events = detect_stop_events(current_state, previous_state)

    # 2. Detect segment transitions (ONLY if previous exists)
    segment_events = []
    if previous_state:
        segment_events = detect_segment_transition(
            current_state,
            previous_state,
            route_reference
        )

    # 3. Detect delay events
    delay_events = []
    if previous_state:
        delay_events = detect_delay_event(current_state, previous_state)

    # 3. Combine
    all_raw_events = stop_events + segment_events + delay_events

    # 4. Build full events
    for event in all_raw_events:
        full_event = build_event(event, current_state)
        events.append(full_event)
    # traversal lifecycle processing
    traversal_events = process_traversal_lifecycle(
        events,
        current_state,
        previous_state,
        route_reference
    )

    events.extend(traversal_events)

    # dwell lifecycle processing
    dwell_events = process_dwell_lifecycle(
        events,
        current_state
    )

    events.extend(dwell_events)

    return events
Traversal lifecycle - event_engine/traversal_lifecycle.py
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
                            "se

... [truncated in report; see repository file for full source]
Dwell lifecycle - event_engine/dwell_lifecycle.py
# event_engine/dwell_lifecycle.py

from datetime import datetime

from event_engine.dwell_tracker import (
    start_dwell,
    get_active_dwell,
    clear_dwell
)

from event_engine.traversal_tracker import (
    get_active_traversal,
    start_traversal,
    clear_traversal
)

from event_engine.builder import build_event


def process_dwell_lifecycle(
    events,
    current_state
):
    """
    Process:
    - dwell lifecycle
    - travel_time generation
    - segment completion
    """

    lifecycle_events = []

    vehicle_id = current_state.get("vehicle_id")

    for event in events:

        event_type = event.get("event_type")
        stop_id = event.get("stop_id")
        timestamp = event.get("timestamp")

        # -----------------------------------
        # ARRIVAL
        # -----------------------------------

        if event_type == "stop_arrival":

            # start dwell lifecycle
            start_dwell(
                vehicle_id,
                stop_id,
                timestamp
            )

            # check traversal completion
            stored = get_active_traversal(vehicle_id)

            if stored:

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

                    raw_segment_completed = {
                        "event_type": "segment_completed",

                        "from_stop_id": stored["from_stop_id"],
                        "to_stop_id": stop_id,

                        "segment_id": stored["segment_id"],

                        "metrics": {
                            "travel_time": travel_time
                        }
                    }

                    full_segment_completed = build_event(
                        raw_segment_completed,
                        current_state
                    )

                    lifecycle_events.append(
                        full_segment_completed
            

... [truncated in report; see repository file for full source]
Observation pipeline - services/observation_pipeline.py
from sqlalchemy.exc import IntegrityError
from database.connection import SessionLocal
from reference.loader import load_route_reference
from vehicle_state.engine import process_observation
from event_engine.engine import process_event
from models.transit_event import TransitEvent
from models.vehicle_live_state import VehicleLiveState


route_cache = {}

last_transition_per_vehicle = {}

# --- KHALED EDIT START ---
def process_observation_pipeline(
    observation,
    db_observation,
    db=None,
    vehicle_state_cache=None,
    persist_observation=True
):
    # vehicle_state_cache is an optional in-memory dict
    # (vehicle_id -> VehicleLiveState instance) supplied by callers
    # like scripts/bulk_replay.py to avoid a DB round trip per
    # observation. The default stays None so the normal API path
    # (which never passes this parameter) keeps querying the DB
    # exactly as before — fully backward compatible.
    #
    # persist_observation controls whether this function ORM-adds
    # db_observation itself. Default True preserves the normal API
    # path exactly as before. bulk_replay.py passes False and instead
    # bulk-inserts TransitObservation rows itself via
    # db.bulk_insert_mappings() at the end of each batch, which is
    # far faster than one db.add() per row. When False, db_observation
    # is unused by this function (the caller is responsible for it).
    # --- KHALED EDIT END ---
    vehicle_id = observation["vehicle_id"]
    # --- KHALED EDIT START ---
    # If no session was passed in, open one and own its lifecycle
    # (commit/close) ourselves — preserves the original behavior.
    # If a session WAS passed in, the caller owns commit/close
    # (used by bulk_replay.py for batched commits across many calls).
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    # --- KHALED EDIT END ---
    try:

        route_id = observation["route_id"]
        direction_id=observation["direction"]
        cache_key = (
        route_id,
        direction_id
        )
        
        if cache_key not in route_cache:
            route_cache[cache_key] = load_route_reference(
                route_id,
            

... [truncated in report; see repository file for full source]
Bulk replay - scripts/bulk_replay.py
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
    "day_7_

... [truncated in report; see repository file for full source]
GTFS observation generator - scripts/generate_gtfs_pipeline_observations.py
import argparse
import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GTFS_DIR = PROJECT_ROOT / "gtfs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "local_replay_data"
DEFAULT_ROUTE_ID = "CTA_M_112"
DEFAULT_DIRECTION = 0
DEFAULT_FILE_NAME = "day_1_monday_observations.jsonl"


def read_csv_by_path(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_route_stops(route_id: str, direction: int, limit: int = 4) -> list[dict]:
    trips = read_csv_by_path(GTFS_DIR / "trips.txt")
    stop_times = read_csv_by_path(GTFS_DIR / "stop_times.txt")
    stops = {
        row["stop_id"]: row
        for row in read_csv_by_path(GTFS_DIR / "stops.txt")
    }

    trip = next(
        (
            row for row in trips
            if row["route_id"] == route_id
            and int(row["direction_id"]) == direction
        ),
        None,
    )
    if not trip:
        raise RuntimeError(f"No GTFS trip found for route={route_id}, direction={direction}")

    rows = [
        row for row in stop_times
        if row["trip_id"] == trip["trip_id"]
    ]
    rows.sort(key=lambda row: int(row["stop_sequence"]))

    route_stops = []
    for row in rows[:limit]:
        stop = stops[row["stop_id"]]
        route_stops.append({
            "trip_id": trip["trip_id"],
            "route_id": route_id,
            "direction": direction,
            "stop_id": row["stop_id"],
            "stop_sequence": int(row["stop_sequence"]),
            "lat": float(stop["stop_lat"]),
            "lon": float(stop["stop_lon"]),
        })

    if len(route_stops) < 3:
        raise RuntimeError("Need at least 3 GTFS stops to generate the pipeline test")

    return route_stops


def interpolate(start: dict, end: dict, ratio: float) -> tuple[float, float]:
    lat = start["lat"] + ((end["lat"] - start["lat"]) * ratio)
    lon = start["lon"] + ((end["lon"] - start["lon"]) * ratio)
    return lat, lon


def bearing_degrees(start: dict, end: dict) -> float:
    lat1 = math.radians(start["lat"])
    lat2 = math.radians(end["lat"])
    delta_lon 

... [truncated in report; see repository file for full source]
Schema sync - scripts/sync_db_schema.py
import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal


STATEMENTS = [
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS route_id VARCHAR",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS direction INTEGER",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS day_of_week VARCHAR",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS day_number INTEGER",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS time_period VARCHAR",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS simulation_seed INTEGER",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS route_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS timestamp VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS matched_lat DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS matched_lon DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS current_stop_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS next_stop_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS stop_sequence INTEGER",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS segment_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS segment_progress DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS progress DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS distance_to_next_stop DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS speed DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS direction VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS movement VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS movement_state VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS current_delay DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS confidence VARCHAR",
    "ALTER TABLE v

... [truncated in report; see repository file for full source]
GTFS pipeline CMD runner - scripts/run_gtfs_pipeline_test.cmd
@echo off
setlocal

set "PROJECT_DIR=D:\GradProject\IZEE"
set "PYTHON_EXE=C:\Users\Omar\AppData\Local\Programs\Python\Python312\python.exe"
set "PGPASSWORD=1234"
set "PYTHONPATH=%PROJECT_DIR%"
set "IZEE_CONVERTED_DIR=%PROJECT_DIR%\local_replay_data"
set "IZEE_REPLAY_FILES=day_1_monday_observations.jsonl"

cd /d "%PROJECT_DIR%"

echo ============================================================
echo IZEE GTFS-Based Full Pipeline Test
echo ============================================================
echo.

echo [1/6] Generate GTFS-based observations...
"%PYTHON_EXE%" scripts\generate_gtfs_pipeline_observations.py
if errorlevel 1 goto fail
echo.

echo [2/6] Initialize database schema...
"%PYTHON_EXE%" init_db.py
if errorlevel 1 goto fail
echo.

echo [3/7] Sync existing database schema...
"%PYTHON_EXE%" scripts\sync_db_schema.py
if errorlevel 1 goto fail
echo.

echo [4/8] Load GTFS reference tables if empty...
"%PYTHON_EXE%" scripts\load_gtfs_if_empty.py
if errorlevel 1 goto fail
echo.

echo [5/8] Clean previous GTFS pipeline test rows...
"%PYTHON_EXE%" scripts\cleanup_gtfs_pipeline_test.py
if errorlevel 1 goto fail
echo.

echo [6/8] Run bulk replay through Vehicle State Engine and Event Engine...
"%PYTHON_EXE%" scripts\bulk_replay.py
if errorlevel 1 goto fail
echo.

echo [7/8] Build segment statistics...
"%PYTHON_EXE%" scripts\segment_stats.py
if errorlevel 1 goto fail
echo.

echo [8/8] Run Alert Engine...
"%PYTHON_EXE%" scripts\alert_engine_run.py
if errorlevel 1 goto fail
echo.

echo ============================================================
echo Final verification counts
echo ============================================================
psql -h localhost -p 5433 -U postgres -d izee_db -c "select 'transit_events' as table_name, count(*) from transit_events union all select 'segment_statistics', count(*) from segment_statistics union all select 'alerts', count(*) from alerts;"
psql -h localhost -p 5433 -U postgres -d izee_db -c "select type, severity, count(*) from alerts group by type, severity order by type, severity;"

echo.
echo DONE. Review the output above.
goto end

:fail
echo.
echo FAILED. Review the error above.

:end
endlocal
Alert engine - alert_engine/engine.py
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from alert_engine.aggregator import check_route_disruptions
from alert_engine.deduplicator import should_create_alert
from alert_engine.models import Alert
from alert_engine.rules import handle_dwell_time, handle_segment_completed


logger = logging.getLogger(__name__)

DAY_TYPE_MAP = {
    "Monday": "weekday",
    "Tuesday": "weekday",
    "Wednesday": "weekday",
    "Thursday": "weekday",
    "Sunday": "weekday",
    "Friday": "friday",
    "Saturday": "saturday",
}


def _fetch_segment_stats(db: Session, event_row: dict) -> dict | None:
    day_type = DAY_TYPE_MAP.get(event_row.get("day_of_week"))
    if not day_type:
        return None

    row = db.execute(text("""
        SELECT avg_travel_time, std_travel_time, sample_count
        FROM segment_statistics
        WHERE segment_id = :segment_id
          AND route_id = :route_id
          AND direction = :direction
          AND day_type = :day_type
          AND time_period = :time_period
        LIMIT 1
    """), {
        "segment_id": event_row.get("segment_id"),
        "route_id": event_row.get("route_id"),
        "direction": event_row.get("direction"),
        "day_type": day_type,
        "time_period": event_row.get("time_period"),
    }).fetchone()

    return dict(row._mapping) if row else None


def _build_alert_orm(alert_dict: dict) -> Alert:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=alert_dict["expires_minutes"])

    return Alert(
        alert_id=uuid.uuid4(),
        type=alert_dict["type"],
        severity=alert_dict["severity"],
        message=alert_dict["message"],
        route_id=alert_dict.get("route_id"),
        vehicle_id=alert_dict.get("vehicle_id"),
        segment_id=alert_dict.get("segment_id"),
        source_event_id=alert_dict.get("source_event_id"),
        lat=alert_dict.get("lat"),
        lon=alert_dict.get("lon"),
        created_at=now,
        expires_at=expires_at,
        eta_based=False,
    )


def _fetch_segment_completed_events(db: Session):
    return db.execute(text("""
        

... [truncated in report; see repository file for full source]
Alert rules - alert_engine/rules.py
from alert_engine.config import (
    ALERT_EXPIRY_DELAY,
    ALERT_EXPIRY_DWELL,
    DELAY_THRESHOLD_HIGH,
    DELAY_THRESHOLD_LOW,
    DELAY_THRESHOLD_MEDIUM,
    DWELL_THRESHOLD_HIGH,
    DWELL_THRESHOLD_MEDIUM,
)


def handle_segment_completed(event_row: dict, segment_stats_row: dict | None) -> dict | None:
    metrics = event_row.get("metrics") or {}
    travel_time = metrics.get("travel_time")
    if travel_time is None or segment_stats_row is None:
        return None

    avg_time = segment_stats_row.get("avg_travel_time")
    if avg_time is None or avg_time <= 0:
        return None

    ratio = float(travel_time) / float(avg_time)
    if ratio < DELAY_THRESHOLD_LOW:
        return None

    if ratio >= DELAY_THRESHOLD_HIGH:
        severity = "high"
    elif ratio >= DELAY_THRESHOLD_MEDIUM:
        severity = "medium"
    else:
        severity = "low"

    route_id = event_row.get("route_id") or "unknown"
    segment_id = event_row.get("segment_id") or "unknown"
    actual_min = round(float(travel_time) / 60, 1)
    expected_min = round(float(avg_time) / 60, 1)

    return {
        "type": "delay",
        "severity": severity,
        "message": (
            f"{route_id} vehicle delayed {actual_min} min on segment "
            f"{segment_id}. Expected {expected_min} min."
        ),
        "route_id": event_row.get("route_id"),
        "vehicle_id": event_row.get("vehicle_id"),
        "segment_id": event_row.get("segment_id"),
        "source_event_id": event_row.get("event_id"),
        "lat": event_row.get("lat"),
        "lon": event_row.get("lon"),
        "expires_minutes": ALERT_EXPIRY_DELAY,
    }


def handle_dwell_time(event_row: dict) -> dict | None:
    metrics = event_row.get("metrics") or {}
    dwell = metrics.get("dwell_time")
    if dwell is None or float(dwell) < DWELL_THRESHOLD_MEDIUM:
        return None

    severity = "high" if float(dwell) >= DWELL_THRESHOLD_HIGH else "medium"
    route_id = event_row.get("route_id") or "unknown"
    stop_id = event_row.get("stop_id") or "unknown"
    dwell_min = round(float(dwell) / 60, 1)

    return {
        "type": "dwell_issue",
        "severity": severity,
        "message": (
     

... [truncated in report; see repository file for full source]
Alert aggregator - alert_engine/aggregator.py
from collections import defaultdict

from alert_engine.config import (
    ALERT_EXPIRY_DISRUPTION,
    DISRUPTION_THRESHOLD_HIGH,
    DISRUPTION_THRESHOLD_MEDIUM,
)


def check_route_disruptions(delay_alerts: list[dict]) -> list[dict]:
    route_vehicles = defaultdict(set)

    for alert in delay_alerts:
        if alert.get("severity") not in ("medium", "high"):
            continue

        route_id = alert.get("route_id")
        vehicle_id = alert.get("vehicle_id")
        if route_id and vehicle_id:
            route_vehicles[route_id].add(vehicle_id)

    disruption_alerts = []
    for route_id, vehicles in route_vehicles.items():
        count = len(vehicles)
        if count < DISRUPTION_THRESHOLD_MEDIUM:
            continue

        severity = "high" if count >= DISRUPTION_THRESHOLD_HIGH else "medium"
        disruption_alerts.append({
            "type": "disruption",
            "severity": severity,
            "message": (
                f"Service disruption on {route_id}. {count} vehicles "
                "experiencing severe delays."
            ),
            "route_id": route_id,
            "vehicle_id": None,
            "segment_id": None,
            "source_event_id": None,
            "lat": None,
            "lon": None,
            "expires_minutes": ALERT_EXPIRY_DISRUPTION,
        })

    return disruption_alerts
Alert deduplicator - alert_engine/deduplicator.py
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from alert_engine.config import DEDUP_WINDOW_MINUTES


_active_alerts_cache = {}


def should_create_alert(entity_id: str | None, alert_type: str, db: Session) -> bool:
    """
    Return False when the same entity already has this alert type inside
    the deduplication window. entity_id is vehicle_id for vehicle alerts
    and route_id for route-level disruption alerts.
    """
    if not entity_id:
        return True

    key = (entity_id, alert_type)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)

    cached_at = _active_alerts_cache.get(key)
    if cached_at and cached_at >= window_start:
        return False
    if cached_at:
        del _active_alerts_cache[key]

    result = db.execute(text("""
        SELECT created_at
        FROM alerts
        WHERE type = :alert_type
          AND created_at >= :window_start
          AND (
              vehicle_id = :entity_id
              OR route_id = :entity_id
          )
        LIMIT 1
    """), {
        "alert_type": alert_type,
        "window_start": window_start,
        "entity_id": entity_id,
    }).fetchone()

    if result:
        return False

    _active_alerts_cache[key] = now
    return True


def clear_cache() -> None:
    _active_alerts_cache.clear()
