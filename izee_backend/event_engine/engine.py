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