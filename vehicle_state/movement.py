def determine_movement_state(distance, speed, previous_state):
    # 1️⃣ At stop
    if distance <= 30 and speed < 5:
        return "at_stop"

    # 2️⃣ Leaving stop
    if previous_state and previous_state.get("movement_state") == "at_stop" and speed > 5:
        return "leaving_stop"

    # 3️⃣ Approaching stop
    if distance <= 150:
        return "approaching_stop"

    # 4️⃣ Default
    return "between_stops"

def determine_direction(current_progress, previous_state):
    """
    Determine direction based on progress change
    """

    # no previous data
    if not previous_state:
        return "unknown"

    prev_progress = previous_state.get("progress")

    if prev_progress is None:
        return "unknown"

    # forward
    if current_progress > prev_progress:
        return "forward"

    # backward
    if current_progress < prev_progress:
        return "backward"

    # same position
    return "unknown"