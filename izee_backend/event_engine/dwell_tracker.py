# event_engine/dwell_tracker.py

"""
Temporary dwell lifecycle memory.

Purpose:
- track stop arrival timestamps
- support dwell duration computation

NOTE:
This is temporary operational memory only.
NOT persistent operational truth.
"""

# vehicle_id -> active dwell lifecycle
active_dwells = {}


def start_dwell(
    vehicle_id,
    stop_id,
    arrival_time
):
    """
    Start dwell lifecycle at stop arrival.
    """

    active_dwells[vehicle_id] = {
        "stop_id": stop_id,
        "arrival_time": arrival_time
    }


def get_active_dwell(vehicle_id):
    """
    Retrieve active dwell lifecycle.
    """

    return active_dwells.get(vehicle_id)


def clear_dwell(vehicle_id):
    """
    Clear dwell lifecycle after departure.
    """

    if vehicle_id in active_dwells:
        del active_dwells[vehicle_id]