# event_engine/engine.py

from event_engine.detectors import detect_stop_events
from event_engine.builder import build_event


def process_event(current_state, previous_state):
    """
    Main Event Engine function

    Input:
        current_state: VehicleState (dict)
        previous_state: VehicleState (dict)

    Output:
        List of events (can be empty)
    """

    events = []

    # If no previous state → no events
    if not previous_state:
        return events

    # 1. Detect stop-related events (arrival/departure)
    stop_events = detect_stop_events(current_state, previous_state)

    # 2. Build full event objects
    for event in stop_events:
        full_event = build_event(event, current_state)
        events.append(full_event)

    return events