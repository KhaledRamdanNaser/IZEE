# IZEE TMS — Future Improvements / Technical Debt

This document tracks intentionally postponed architectural improvements,
temporary implementation decisions, scalability limitations,
and future subsystem evolution plans.

Current review coverage:
- api/routes/vehicle.py

---

# 🔷 API Layer

## 1. Move duplicate filtering into Event Engine

### Current
Duplicate transition filtering exists inside API layer (`vehicle.py`).

### Problem
- Event correctness logic is split between API and Event Engine
- Event ownership boundaries are unclear
- Harder to maintain as event complexity grows

### Future Direction
Move duplicate filtering into Event Engine internal pipeline.

### Priority
High

---

## 2. Move dwell event generation fully into Event Engine

### Current
Dwell event generation and temporal tracking occur inside API layer.

### Problem
- API contains event-processing responsibilities
- Event lifecycle ownership is split
- Temporal event logic should belong to Event Engine

### Why Acceptable Currently
Needed temporary in-memory state for rapid implementation.

### Future Direction
Event Engine should fully own:
- arrival tracking
- departure tracking
- dwell computation
- dwell event emission

### Priority
Medium

---

## 3. Replace in-memory dwell tracking

### Current
```python
dwell_tracker = {}
Problem
Lost on restart
Single-instance only
Not horizontally scalable
Future Direction

Replace with:

Redis
stateful stream processing
distributed state layer
Priority

High

4. Replace in-memory transition memory
Current
last_transition_per_vehicle = {}
Problem
Not persistent
Not multi-instance safe
Not scalable
Future Direction

Shared/distributed transition memory:

Redis
event-state cache
streaming state management
Priority

High

5. Reduce orchestration responsibility of vehicle.py
Current

vehicle.py currently handles:

processing orchestration
filtering
dwell tracking
DB persistence
serialization
Problem

Too many responsibilities concentrated in one layer.

Future Direction

Move toward cleaner orchestration boundaries while preserving modular monolith architecture.

Priority

Medium

🔷 Delay System
6. Replace externally injected delay with real delay computation
Current

current_delay is manually injected through POST requests.

Problem

Not operationally correct.

Future Direction

Compute delay using:

GTFS scheduled stop times
actual arrival/departure timestamps
schedule deviation calculations
Notes

This should happen before mature ETA prediction work.

Priority

High

🔷 Logging & Monitoring
7. Replace debug prints with structured logging
Current

Uses temporary print() debugging.

Future Direction

Introduce:

logging levels
structured logs
centralized logging format
Priority

Low

🔷 API Serialization
8. Replace manual response serialization
Current

Manual dictionary construction in API responses.

Future Direction

Use:

Pydantic response schemas
DTO-style response contracts
Priority

Low

🔷 Event Engine
9. Replace debug prints with structured detector logging
Current

Detector logic uses direct debug prints such as:

print("---- DETECTOR DEBUG ----")
print("IGNORED: oscillation reverse")
Problem
noisy console output
no log levels
difficult production monitoring
poor observability scaling
Future Direction

Replace with:

structured logging
debug/info/warning levels
centralized logging pipeline
Priority

Low

10. Improve oscillation and GPS jitter handling
Current

Oscillation handling uses rule-based heuristics:

reverse sequence filtering
optional progress threshold filtering
Problem
heuristic-only approach
may fail under noisy real-world GPS
difficult to generalize across routes and densities
Future Direction

Potential future improvements:

Kalman filtering
probabilistic transition validation
confidence-weighted event generation
trajectory smoothing
Priority

Medium

11. Replace hardcoded delay severity thresholds
Current

Delay levels use fixed thresholds:

<60   → none
<180  → minor
<300  → moderate
else  → severe
Problem
not context-aware
does not adapt to route characteristics
ignores traffic conditions
ignores service type differences
Future Direction

Delay severity should eventually consider:

route characteristics
service frequency
historical traffic patterns
passenger impact
peak/off-peak context
Priority

Medium

12. Improve event ordering and pipeline orchestration
Current

Events are combined manually:

all_raw_events = stop_events + segment_events + delay_events
Problem
implicit ordering assumptions
future event dependencies may become fragile
scaling event categories may complicate orchestration
Future Direction

Introduce explicit internal event pipeline ordering strategy.

Priority

Low

13. Remove duplicate detector imports in engine.py
Current

detect_stop_events imported twice.

Problem

Minor code hygiene issue.

Future Direction

Consolidate imports cleanly.

Priority

Low

14. Replace dictionary-based contracts with typed schemas
Current

Events and states use raw dictionaries throughout engine and detectors.

Problem
weak validation
typo-prone
harder refactoring
implicit contracts
Future Direction

Introduce typed schemas/models:

Pydantic
dataclasses
explicit event/state contracts
Priority

Medium

15. Improve event confidence modeling
Current

Confidence is mostly inherited from Vehicle State or manually overridden.

Problem

Confidence logic is simplistic and not event-aware.

Future Direction

Event confidence should eventually consider:

GPS quality
transition certainty
oscillation probability
temporal consistency
sensor reliability
Priority

Medium
🔷 Vehicle State Engine
16. Replace simplified nearest-segment matching with advanced map matching
Current

Nearest segment is selected using geometric distance only.

Problem
ignores heading/bearing
ignores road topology
sensitive to GPS noise
may fail in dense urban areas
cannot handle overlapping segments robustly
Future Direction

Introduce advanced map matching:

Hidden Markov Models (HMM)
probabilistic map matching
heading-aware matching
temporal trajectory matching
Priority

High

17. Improve progress stabilization logic
Current

Progress stabilization uses simple threshold heuristics:

if delta < -0.05
if delta > 0.2

with simple smoothing:

prev_progress + (delta * 0.5)
Problem
heuristic thresholds
route-dependent behavior
may over-smooth or under-smooth
not adaptive to speed or GPS quality
Future Direction

Introduce:

adaptive smoothing
confidence-aware stabilization
Kalman filtering
trajectory-aware smoothing
Priority

High

18. Replace hardcoded movement-state thresholds
Current

Movement states use fixed thresholds:

distance <= 30
distance <= 150
speed < 5
Problem
not route-aware
not vehicle-aware
may fail under real traffic conditions
sensitive to GPS quality
Future Direction

Movement-state determination should eventually consider:

vehicle type
route geometry
stop density
traffic conditions
GPS uncertainty
Priority

High

19. Improve direction determination logic
Current

Direction determined solely using progress comparison.

Problem
vulnerable to GPS jitter
ignores heading/bearing
ignores temporal consistency
Future Direction

Direction should eventually incorporate:

bearing
trajectory history
map topology
confidence weighting
Priority

Medium

20. Replace externally injected delay placeholder
Current

Delay is directly injected from observation:

observation.get("current_delay", 0)
Problem

Placeholder implementation only.

Future Direction

Compute real operational delay from:

GTFS schedules
actual stop arrival/departure times
trip progress
Notes

Critical before mature ETA implementation.

Priority

High

21. Improve confidence modeling
Current

Confidence determined only by source type:

driver_app → high
simulated → medium
crowdsensed → low
Problem

Oversimplified confidence model.

Future Direction

Confidence should eventually consider:

GPS quality
sensor reliability
movement consistency
map matching certainty
temporal consistency
crowdsensing agreement
Priority

Medium

22. Improve validation robustness
Current

Validation performs only basic sanity checks.

Problem

Limited protection against:

unrealistic movement
teleportation
timestamp anomalies
impossible speeds
inconsistent state transitions
Future Direction

Introduce stronger validation:

temporal consistency validation
physics-aware validation
speed plausibility checks
trajectory consistency validation
Priority

Medium

23. Replace raw dictionary-based state contracts with typed schemas
Current

VehicleState represented using raw dictionaries.

Problem
weak typing
typo-prone
implicit contracts
harder refactoring
Future Direction

Introduce typed state contracts:

Pydantic
dataclasses
explicit schemas
Priority

Medium

24. Optimize nearest-segment search scalability
Current

Segment search scans all route segments sequentially.

Problem

Scalability limitations for:

large routes
many routes
real-time fleet scale
Future Direction

Introduce spatial indexing:

R-tree
KD-tree
PostGIS spatial queries
Priority

Medium