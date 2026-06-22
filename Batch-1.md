event_engine/detectors.py:{
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
            "stop_id": previous_state.get("next_stop_id")
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
            "from_stop_id": previous_state.get("next_stop_id"),
            "to_stop_id": current_state.get("next_stop_id"),
            "metrics": {},
            "confidence_override": "low"
        })
        return events

    # 🟡 Prevent rapid duplicate forward transitions (oscillation bounce)
# 🟡 Prevent oscillation bounce using progress
    """
    prev_progress = previous_state.get("progress")
    curr_progress = current_state.get("progress")

    if prev_progress is not None and curr_progress is not None:
        delta_progress = abs(curr_progress - prev_progress)

         # very small movement → likely noise
        if delta_progress < 0.01 and curr_seq > prev_seq:
           print("IGNORED: tiny forward movement (oscillation)")
           return events
"""
    # 🟢 NORMAL or 🟡 SKIPPED (forward movement)
    for seq in range(prev_seq, curr_seq):
        from_stop = stops_map.get(seq)
        to_stop = stops_map.get(seq + 1)

        if not from_stop or not to_stop:
            continue

        events.append({
            "event_type": "segment_travel",
            "from_stop_id": from_stop["stop_id"],
            "to_stop_id": to_stop["stop_id"],
            "metrics": {}
        })

    return events


def get_delay_level(delay):
    if delay < 60:
        return None
    elif delay < 180:
        return "minor"
    elif delay < 300:
        return "moderate"
    else:
        return "severe"
    

def detect_delay_event(current_state, previous_state):
    events = []

    curr_delay = current_state.get("current_delay")
    prev_delay = previous_state.get("current_delay") if previous_state else None

    if curr_delay is None or prev_delay is None:
        return events

    curr_level = get_delay_level(curr_delay)
    prev_level = get_delay_level(prev_delay)

    # Only emit when level changes
    if curr_level and curr_level != prev_level:
        events.append({
            "event_type": "delay",
            "metrics": {
                "delay": curr_delay,
                "level": curr_level
            }
        })

    return events
}
event_engine/dwell_lifecycle.py:{
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
                    )

                except Exception:
                    pass

                # cleanup traversal lifecycle
                clear_traversal(vehicle_id)

        # -----------------------------------
        # DEPARTURE
        # -----------------------------------

        elif event_type == "stop_departure":

            start_traversal(
                vehicle_id,
                stop_id,
                timestamp,
                current_state.get("segment_id")
            )

            stored_dwell = get_active_dwell(
                vehicle_id
            )

            if (
                stored_dwell
                and stored_dwell.get("stop_id") == stop_id
            ):

                try:

                    t1 = datetime.fromisoformat(
                        stored_dwell["arrival_time"]
                    )

                    t2 = datetime.fromisoformat(
                        timestamp
                    )

                    dwell_time = (
                        t2 - t1
                    ).total_seconds()

                    raw_dwell_event = {
                        "event_type": "dwell_time",
                        "stop_id": stop_id,

                        "metrics": {
                            "dwell_time": dwell_time
                        }
                    }

                    full_dwell_event = build_event(
                        raw_dwell_event,
                        current_state
                    )

                    lifecycle_events.append(
                        full_dwell_event
                    )

                except Exception:
                    pass

            # cleanup dwell lifecycle
            clear_dwell(vehicle_id)

    return lifecycle_events
}
event_engine/engine.py:{
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
}