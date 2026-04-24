def stabilize_progress(current_progress, previous_state):
    """
    Basic stability rules for route progress
    """

    if not previous_state:
        return current_progress

    prev_progress = previous_state.get("progress")

    if prev_progress is None:
        return current_progress

    delta = current_progress - prev_progress

    # ❌ Prevent big backward jump
    if delta < -0.05:
        return prev_progress

    # ❌ Prevent unrealistic forward jump
    if delta > 0.2:
        return prev_progress

    # 🟡 Small smoothing (optional)
    smoothed = prev_progress + (delta * 0.5)

    return smoothed
def determine_confidence(observation):
    source = observation.get("source")

    if source == "driver_app":
        return "high"
    if source == "simulated":
        return "medium"
    if source == "crowdsensed":
        return "low"

    return "medium"