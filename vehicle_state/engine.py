from vehicle_state.matcher import find_nearest_segment, project_point_on_segment
from vehicle_state.matcher import haversine_distance
from vehicle_state.movement import determine_movement_state
from vehicle_state.movement import determine_direction
from vehicle_state.utils import stabilize_progress
from vehicle_state.utils import determine_confidence
from vehicle_state.validation import validate_vehicle_state
from vehicle_state.transition_tracker import (
    update_operational_memory
)
# --- SALAH EDIT START ---

def stabilize_segment(
    matched_segment,
    previous_state,
    segments
):
    print("🔥🔥🔥 STABILIZE_SEGMENT CALLED 🔥🔥🔥")
    """
    Prevent segment bouncing near boundaries.
    """
    # ⬇️ ADDED  Debugging PRINTS HERE ⬇️
    print("===== SEGMENT STABILIZER =====")
    print("candidate:", matched_segment["segment_id"])  # Changed candidate_segment to matched_segment

    if previous_state:
        print("previous:", previous_state.get("segment_id"))
        print("previous progress:", previous_state.get("segment_progress"))
    else:
        print("previous: NONE")
    # ⬆️ END OF ADDED PRINTS ⬆️

    if previous_state is None:
        return matched_segment

    previous_segment_id = previous_state.get("segment_id")

    if previous_segment_id is None:
        return matched_segment

    matched_id = (
        matched_segment["start"]["stop_id"]
        + "_"
        + matched_segment["end"]["stop_id"]
    )

    if matched_id == previous_segment_id:
        return matched_segment

    previous_progress = previous_state.get(
        "segment_progress",
        1
    )

    # vehicle has not finished current segment yet
    if previous_progress < 0.90:

        for seg in segments:
            sid = (
                seg["start"]["stop_id"]
                + "_"
                + seg["end"]["stop_id"]
            )

            if sid == previous_segment_id:
                return seg

    return matched_segment
# --- SALAH EDIT END ---


def process_observation(observation, previous_state, route_reference):

    # 1️⃣ Extract GPS
    lat = observation["location"]["lat"]
    lon = observation["location"]["lon"]

    # 2️⃣ Find nearest segment
    matched_segment = find_nearest_segment(
        lat,
        lon,
        route_reference["segments"]
    )

    segment = stabilize_segment(
        matched_segment,
        previous_state,
        route_reference["segments"]
    )
    print("MATCHED SEGMENT:", segment)
    
    segments = route_reference["segments"]
    segment_index = segments.index(segment)
    total_segments = len(segments)
    

    # 3️⃣ Project onto segment
    start = segment["start"]
    end = segment["end"]

    proj_lat, proj_lon, t = project_point_on_segment(
        lat, lon,
        start["lat"], start["lon"],
        end["lat"], end["lon"]
    )
# AFTER projection
    raw_progress = (segment_index + t) / total_segments

    route_progress = stabilize_progress(
    raw_progress,
    previous_state
)
# 3.5️⃣ Determine next stop
    next_stop_id = end["stop_id"]
# Calculate Distance to next stop
    distance = haversine_distance(
    proj_lat, proj_lon,
    end["lat"], end["lon"]
)
    print("DISTANCE TO NEXT STOP:", distance)
    print("NEXT STOP:", next_stop_id)
#Movement State
    movement_state = determine_movement_state(
    observation["vehicle_id"],
    distance,
    observation["speed"],
    t,
    previous_state
)
    direction = determine_direction(
    route_progress,
    previous_state
)
    current_stop_id = None

    if movement_state == "at_stop":
        current_stop_id = next_stop_id

    confidence = determine_confidence(observation)
    # 🔥 continuously update operational continuity memory
    update_operational_memory(
        observation["vehicle_id"],
        distance,
        t
    )
# 4️⃣ Build vehicle state
    vehicle_state = {   
        "vehicle_id": observation["vehicle_id"],
        "route_id": route_reference["route_id"],
        "trip_id": None,
        "timestamp": observation["timestamp"],

        "matched_position": {
            "lat": proj_lat,
            "lon": proj_lon
        },

        "current_stop_id": current_stop_id,
        "next_stop_id": next_stop_id,
        "stop_sequence": end["sequence"],

        "segment_id": segment["segment_id"],
        "segment_progress": t,
        "progress": route_progress,

        "distance_to_next_stop": distance,

        "speed": observation["speed"],
        "direction": direction,

        "movement": "moving" if observation["speed"] > 0 else "stopped",
        "movement_state": movement_state,

        "current_delay": observation.get("current_delay", 0),
        "confidence": confidence,

        "source": observation["source"],
        "simulation_flag": observation["simulation_flag"]
    }

    vehicle_state = validate_vehicle_state(
    vehicle_state,
    previous_state
)

    return vehicle_state