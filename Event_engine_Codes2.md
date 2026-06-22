# event_engine/engine.py
{
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
}
output of requested gits :(venv) PS C:\Users\mohamed\IZEE> git log --follow -- event_engine/dwell_lifecycle.py
commit 0f1f3847228440ec35500acd1d609de433b32c8c (origin/Vehicle-State-Refactored, Vehicle-State-Refactored)
Author: MuhammedAhmedSalah <mo2138366@gmail.com>
Date:   Sat May 30 20:49:19 2026 +0300

    Full Pipeline till Event engine, Without Kalman filter
(venv) PS C:\Users\mohamed\IZEE> git blame event_engine/dwell_lifecycle.py
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   1) # event_engine/dwell_lifecycle.py
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   2) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   3) from datetime import datetime
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   4) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   5) from event_engine.dwell_tracker import (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   6)     start_dwell,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   7)     get_active_dwell,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   8)     clear_dwell
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   9) )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  10) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  11) from event_engine.traversal_tracker import (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  12)     get_active_traversal,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  13)     start_traversal,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  14)     clear_traversal
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  15) )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  16) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  17) from event_engine.builder import build_event
:

Rerun of the gits as i think something went wrong :
{
    (venv) PS C:\Users\mohamed\IZEE> git log --follow -- event_engine/dwell_lifecycle.py
commit 0f1f3847228440ec35500acd1d609de433b32c8c (origin/Vehicle-State-Refactored, Vehicle-State-Refactored)
Author: MuhammedAhmedSalah <mo2138366@gmail.com>
Date:   Sat May 30 20:49:19 2026 +0300

    Full Pipeline till Event engine, Without Kalman filter
(venv) PS C:\Users\mohamed\IZEE> git blame event_engine/dwell_lifecycle.py
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   1) # event_engine/dwell_lifecycle.py
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   2) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   3) from datetime import datetime
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   4) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   5) from event_engine.dwell_tracker import (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   6)     start_dwell,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   7)     get_active_dwell,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   8)     clear_dwell
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300   9) )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  10) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  11) from event_engine.traversal_tracker import (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  12)     get_active_traversal,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  13)     start_traversal,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  14)     clear_traversal
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  15) )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  16) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  17) from event_engine.builder import build_event
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  18) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  19) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  20) def process_dwell_lifecycle(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  21)     events,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  22)     current_state
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  23) ):
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  24)     """
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  25)     Process:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  26)     - dwell lifecycle
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  27)     - travel_time generation
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  28)     - segment completion
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  29)     """
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  30) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  31)     lifecycle_events = []
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  32) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  33)     vehicle_id = current_state.get("vehicle_id")
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  34) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  35)     for event in events:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  36) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  37)         event_type = event.get("event_type")
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  38)         stop_id = event.get("stop_id")
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  39)         timestamp = event.get("timestamp")
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  40) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  41)         # -----------------------------------
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  42)         # ARRIVAL
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  43)         # -----------------------------------
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  44) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  45)         if event_type == "stop_arrival":
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  46) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  47)             # start dwell lifecycle
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  48)             start_dwell(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  49)                 vehicle_id,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  50)                 stop_id,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  51)                 timestamp
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  52)             )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  53) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  54)             # check traversal completion
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  55)             stored = get_active_traversal(vehicle_id)
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  56) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  57)             if stored:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  58) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  59)                 try:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  60) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  61)                     t1 = datetime.fromisoformat(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  62)                         stored["departure_time"]
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  63)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  64) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  65)                     t2 = datetime.fromisoformat(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  66)                         timestamp
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  67)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  68) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  69)                     travel_time = (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  70)                         t2 - t1
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  71)                     ).total_seconds()
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  72) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  73)                     raw_segment_completed = {
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  74)                         "event_type": "segment_completed",
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  75) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  76)                         "from_stop_id": stored["from_stop_id"],
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  77)                         "to_stop_id": stop_id,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  78) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  79)                         "segment_id": stored["segment_id"],
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  80) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  81)                         "metrics": {
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  82)                             "travel_time": travel_time
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  83)                         }
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  84)                     }
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  85) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  86)                     full_segment_completed = build_event(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  87)                         raw_segment_completed,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  88)                         current_state
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  89)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  90) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  91)                     lifecycle_events.append(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  92)                         full_segment_completed
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  93)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  94) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  95)                 except Exception:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  96)                     pass
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  97) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  98)                 # cleanup traversal lifecycle
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300  99)                 clear_traversal(vehicle_id)
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 100) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 101)         # -----------------------------------
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 102)         # DEPARTURE
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 103)         # -----------------------------------
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 104) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 105)         elif event_type == "stop_departure":
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 106) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 107)             start_traversal(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 108)                 vehicle_id,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 109)                 stop_id,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 110)                 timestamp,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 111)                 current_state.get("segment_id")
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 112)             )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 113) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 114)             stored_dwell = get_active_dwell(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 115)                 vehicle_id
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 116)             )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 117) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 118)             if (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 119)                 stored_dwell
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 120)                 and stored_dwell.get("stop_id") == stop_id
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 121)             ):
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 122) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 123)                 try:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 124) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 125)                     t1 = datetime.fromisoformat(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 126)                         stored_dwell["arrival_time"]
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 127)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 128) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 129)                     t2 = datetime.fromisoformat(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 130)                         timestamp
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 131)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 132) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 133)                     dwell_time = (
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 134)                         t2 - t1
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 135)                     ).total_seconds()
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 136) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 137)                     raw_dwell_event = {
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 138)                         "event_type": "dwell_time",
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 139)                         "stop_id": stop_id,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 140) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 141)                         "metrics": {
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 142)                             "dwell_time": dwell_time
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 143)                         }
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 144)                     }
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 145) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 146)                     full_dwell_event = build_event(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 147)                         raw_dwell_event,
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 148)                         current_state
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 149)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 150) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 151)                     lifecycle_events.append(
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 152)                         full_dwell_event
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 153)                     )
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 154) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 155)                 except Exception:
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 156)                     pass
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 157) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 158)             # cleanup dwell lifecycle
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 159)             clear_dwell(vehicle_id)
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 160) 
0f1f3847 (MuhammedAhmedSalah 2026-05-30 20:49:19 +0300 161)     return lifecycle_events
(END)
}
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

Try the new cross-platform PowerShell https://aka.ms/pscore6

PS C:\Users\mohamed> Select-String -Path .\* -Pattern "segment_completed" -Recurse
Select-String : A parameter cannot be found that matches parameter name 'Recurse'.
At line:1 char:54
+ Select-String -Path .\* -Pattern "segment_completed" -Recurse
+                                                      ~~~~~~~~
    + CategoryInfo          : InvalidArgument: (:) [Select-String], ParameterBindingException
    + FullyQualifiedErrorId : NamedParameterNotFound,Microsoft.PowerShell.Commands.SelectStringCommand

PS C:\Users\mohamed>
(venv) PS C:\Users\mohamed\IZEE> grep -R "segment_completed" .
grep : The term 'grep' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the spelling of the 
name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ grep -R "segment_completed" .
+ ~~~~
    + CategoryInfo          : ObjectNotFound: (grep:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
 