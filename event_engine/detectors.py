# event_engine/detectors.py

def detect_stop_events(current_state, previous_state):
    """
    Detect stop arrival and departure events
    """

    events = []

    prev_state = previous_state.get("movement_state")
    curr_state = current_state.get("movement_state")

    # Stop Arrival
    if prev_state != "at_stop" and curr_state == "at_stop":
        events.append({
            "event_type": "stop_arrival",
            "stop_id": current_state.get("next_stop_id")
        })

    # Stop Departure
    if prev_state == "at_stop" and curr_state != "at_stop":
        events.append({
            "event_type": "stop_departure",
            "stop_id": previous_state.get("next_stop_id")
        })

    return events


def detect_segment_transition(current_state, previous_state):
    """
    Detect when the vehicle transitions to a different stop sequence segment.
    """

    events = []

    if not previous_state:
        return events

    prev_stop_sequence = previous_state.get("stop_sequence")
    curr_stop_sequence = current_state.get("stop_sequence")

    if prev_stop_sequence is None or curr_stop_sequence is None:
        return events

    if prev_stop_sequence != curr_stop_sequence:
        events.append({
            "event_type": "segment_travel",
            "from_stop_id": previous_state.get("next_stop_id"),
            "to_stop_id": current_state.get("next_stop_id")
        })

    return events