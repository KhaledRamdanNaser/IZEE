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

            # --- SALAH EDIT START ---
            # Departure = leaving the stop vehicle was confirmed at
            "stop_id": previous_state.get("current_stop_id")
            # --- SALAH EDIT END ---
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