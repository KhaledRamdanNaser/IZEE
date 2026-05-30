"""""
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
"""""



from vehicle_state.transition_tracker import (
    get_transition_memory,
    update_transition_memory,
    reset_transition_memory,
    get_operational_memory
)

def determine_movement_state(
    vehicle_id,
    distance,
    speed,
    segment_progress,
    previous_state
):
    """
    Operational lifecycle-aware movement-state detection.

    Uses:
    - persistence
    - hysteresis
    - transition confirmation
    """

    # -----------------------------
    # CONFIGURATION
    # -----------------------------

    STOP_RADIUS = 40
    APPROACH_RADIUS = 150

    STOP_SPEED = 5
    DEPARTURE_SPEED = 7

    PERSISTENCE_THRESHOLD = 2

    # -----------------------------
    # PREVIOUS CONFIRMED STATE
    # -----------------------------

    previous_confirmed_state = None

    if previous_state:
        previous_confirmed_state = previous_state.get(
            "movement_state"
        )

    # -----------------------------
    # CANDIDATE STATE INFERENCE
    # -----------------------------

    candidate_state = "between_stops"

    # at_stop candidate
    if distance <= STOP_RADIUS and speed <= STOP_SPEED:
        candidate_state = "at_stop"

    # leaving_stop candidate
    elif (
        previous_confirmed_state == "at_stop"
    ):

        # operational departure evidence
        has_departure_speed = (
            speed > DEPARTURE_SPEED
        )

        # exited origin influence zone
        has_origin_divergence = (
            segment_progress > 0.08
        )

        # stable operational departure
        if (
            has_departure_speed
            and has_origin_divergence
        ):

            candidate_state = "leaving_stop"

        else:

            candidate_state = "at_stop"
    # approaching_stop candidate
    elif distance <= APPROACH_RADIUS:

        # retrieve transition continuity memory
        memory = get_operational_memory(vehicle_id)

        previous_distance = None

        if memory:
            previous_distance = memory.get(
                "previous_distance"
            )

        # convergence validation
        is_converging = False

        if previous_distance is not None:

            # vehicle moving closer to stop
            if distance < previous_distance:
                is_converging = True
        """
        # additional traversal continuity protection
        has_stable_traversal = True

        # if already between stops,
        # require stronger persistence
        if previous_confirmed_state == "between_stops":

            if memory:

                traversal_persistence = memory.get(
                    "count",
                    0
                )

                # require stronger evidence
                if traversal_persistence < 2:
                    has_stable_traversal = False
        """
        # operational approach confirmation
        if (
            is_converging
            #and has_stable_traversal
        ):

            candidate_state = "approaching_stop"

        else:

            candidate_state = "between_stops"

    # default
    else:
        candidate_state = "between_stops"

    # -----------------------------
    # NO PREVIOUS STATE
    # -----------------------------

    if not previous_confirmed_state:
        return candidate_state

    # -----------------------------
    # SAME STATE → stable
    # -----------------------------

    if candidate_state == previous_confirmed_state:

        reset_transition_memory(vehicle_id)

        return previous_confirmed_state

    # -----------------------------
    # TERMINAL SERVICING SEMANTICS
    # -----------------------------

    # approaching_stop -> at_stop
    # uses stronger servicing confidence
    if (
        previous_confirmed_state == "approaching_stop"
        and candidate_state == "at_stop"
    ):

        return "at_stop"
    # -----------------------------
    # APPROACH OWNERSHIP SEMANTICS
    # -----------------------------

    # approaching_stop is a soft operational
    # ownership transition.
    # Do not require full persistence.

    if (
        previous_confirmed_state == "between_stops"
        and candidate_state == "approaching_stop"
    ):

        return "approaching_stop"

    # -----------------------------
    # STANDARD TRANSITION EVIDENCE
    # -----------------------------

    memory = update_transition_memory(
        vehicle_id,
        candidate_state,
        distance
    )

    # not enough evidence yet
    if memory["count"] < PERSISTENCE_THRESHOLD:
        return previous_confirmed_state

    # -----------------------------
    # CONFIRMED TRANSITION
    # -----------------------------

    reset_transition_memory(vehicle_id)

    return candidate_state

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