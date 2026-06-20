# event_engine/traversal_tracker.py

"""
Temporary traversal lifecycle memory.

Purpose:
- track active segment traversal
- store departure context
- support segment_completed generation

NOTE:
This is temporary operational memory only.
NOT persistent operational truth.
"""

# vehicle_id -> active traversal lifecycle
active_traversals = {}


def start_traversal(
    vehicle_id,
    from_stop_id,
    departure_time,
    segment_id
):
    """
    Start active traversal lifecycle.
    """

    active_traversals[vehicle_id] = {
        "from_stop_id": from_stop_id,
        "departure_time": departure_time,
        "segment_id": segment_id
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