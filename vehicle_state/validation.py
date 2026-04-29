def validate_vehicle_state(state, previous_state):
    """
    Validate and correct vehicle state
    """

    # 1️⃣ Progress bounds
    if state["progress"] < 0:
        state["progress"] = 0

    if state["progress"] > 1:
        state["progress"] = 1

    # 2️⃣ Speed cannot be negative
    if state["speed"] < 0:
        state["speed"] = 0

    # 3️⃣ Validate movement_state
    valid_states = [
        "between_stops",
        "approaching_stop",
        "at_stop",
        "leaving_stop"
    ]

    if state["movement_state"] not in valid_states:
        state["movement_state"] = "between_stops"

    # 4️⃣ Timestamp check (basic)
    if previous_state:
        prev_time = previous_state.get("timestamp")
        curr_time = state.get("timestamp")

        if prev_time and curr_time and curr_time < prev_time:
            # keep previous timestamp if invalid
            state["timestamp"] = prev_time

    return state