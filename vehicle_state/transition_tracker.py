# vehicle_state/transition_tracker.py

"""
Temporary transition persistence memory
for operational movement-state stabilization.

Purpose:
- prevent noisy state oscillation
- support hysteresis
- accumulate transition evidence

NOTE:
This is NOT operational truth storage.
This is temporary evidence memory only.
"""

# 🔥 vehicle_id -> transition evidence
movement_transition_tracker = {}

# 🔥 Continuous operational continuity memory
# vehicle_id -> operational continuity state
vehicle_operational_memory = {}

def get_transition_memory(vehicle_id):
    """
    Retrieve current transition evidence memory
    for a vehicle.
    """

    return movement_transition_tracker.get(vehicle_id)


def reset_transition_memory(vehicle_id):
    """
    Remove transition evidence memory.
    """

    if vehicle_id in movement_transition_tracker:
        del movement_transition_tracker[vehicle_id]

def update_transition_memory(
    vehicle_id,
    candidate_state,
    current_distance
):
    """
    Update transition evidence persistence.

    Stores:
    - candidate movement state
    - persistence count
    - distance continuity information
    """

    existing = movement_transition_tracker.get(vehicle_id)

    # -----------------------------------
    # FIRST OBSERVATION
    # -----------------------------------

    if not existing:

        movement_transition_tracker[vehicle_id] = {
            "candidate_state": candidate_state,
            "count": 1
            #"previous_distance": current_distance
        }

        return movement_transition_tracker[vehicle_id]
    
    # -----------------------------------
    # SAME CANDIDATE
    # -----------------------------------

    if existing["candidate_state"] == candidate_state:

        existing["count"] += 1

    # -----------------------------------
    # DIFFERENT CANDIDATE
    # -----------------------------------

    else:

        existing["candidate_state"] = candidate_state
        existing["count"] = 1
    """"
    # -----------------------------------
    # ALWAYS UPDATE DISTANCE MEMORY
    # -----------------------------------

    existing["previous_distance"] = current_distance
    """
    return existing

def get_operational_memory(vehicle_id):
    """
    Retrieve continuous operational continuity memory.
    """

    return vehicle_operational_memory.get(vehicle_id)


def update_operational_memory(
    vehicle_id,
    current_distance,
    current_progress
):
    """
    Continuously update operational continuity memory.

    This memory:
    - survives stable states
    - tracks lifecycle evolution
    - supports convergence/divergence logic
    """

    existing = vehicle_operational_memory.get(vehicle_id)

    # first observation
    if not existing:

        vehicle_operational_memory[vehicle_id] = {
            "previous_distance": current_distance,
            "previous_progress": current_progress
        }

        return vehicle_operational_memory[vehicle_id]

    # continuous updates
    existing["previous_distance"] = current_distance
    existing["previous_progress"] = current_progress

    return existing