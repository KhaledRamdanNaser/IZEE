# event_engine/traversal_tracker.py

"""
Temporary segment traversal lifecycle memory.

Purpose:
- track active segment execution
- store segment start timestamp
- support segment_completed generation
- expose active segment state for ETA features
"""
# TODO:
# traversal lifecycle should use segment_progress instead of route progress

# vehicle_id -> active traversal lifecycle
active_traversals = {}


def start_traversal(
    vehicle_id,
    from_stop_id,
    departure_time,
    segment_id,
    bootstrap=False
):
    """
    Start active traversal lifecycle.
    """

    active_traversals[vehicle_id] = {
        "from_stop_id": from_stop_id,
        "departure_time": departure_time,
        "segment_id": segment_id,

        # --- SALAH EDIT START ---
        "bootstrap": bootstrap
        # --- SALAH EDIT END ---
    }


def get_active_traversal(vehicle_id):
    """
    Retrieve active traversal lifecycle.
    """

    return active_traversals.get(vehicle_id)


def clear_traversal(vehicle_id):
    """
    Clear traversal lifecycle after completion.
    """

    if vehicle_id in active_traversals:
        del active_traversals[vehicle_id]

# --- SALAH EDIT START ---

def get_active_segment_state(vehicle_id):
    """
    ETA-facing interface.

    Returns the currently active segment execution.
    """

    traversal = get_active_traversal(vehicle_id)

    if not traversal:
        return None

    return {
        "segment_id": traversal["segment_id"],
        "segment_start_time": traversal["departure_time"]
    }

# --- SALAH EDIT END ---        