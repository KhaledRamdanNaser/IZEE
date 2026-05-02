from fastapi import APIRouter
from vehicle_state.engine import process_observation
from reference.loader import load_route_reference
from database.connection import SessionLocal
from models.vehicle_live_state import VehicleLiveState
from event_engine.engine import process_event #new
router = APIRouter()

# load route once (for now)
route_reference = load_route_reference("CTA_M_112")

@router.post("/vehicle/location")
def receive_vehicle_location(observation: dict):
    vehicle_id = observation["vehicle_id"]
    db = SessionLocal()

    # Query the database to find the previous state of the vehicle
    db_state = (
        db.query(VehicleLiveState)
        .filter(VehicleLiveState.vehicle_id == vehicle_id)
        .first()
    )

    # Initialize previous state to None
    previous_state = None

    # If a previous state is found, pass it to the observation process
    if db_state:
        previous_state = {
            "progress": db_state.progress,
            "movement_state": db_state.movement_state,
            "next_stop_id": db_state.next_stop_id,
            "stop_sequence": db_state.stop_sequence 
        }

    # Process observation using the vehicle state engine
    state = process_observation(
        observation,
        previous_state,
        route_reference
    )
    events = process_event(current_state=state, previous_state=previous_state)
    print("PREV STOP_SEQ:", previous_state.get("stop_sequence") if previous_state else None)
    print("CURR STOP_SEQ:", state.get("stop_sequence"))
    print("EVENTS:", events)
    if db_state:
        # If the vehicle already exists in the database, update the existing record
        db_state.route_id = state["route_id"]
        db_state.timestamp = state["timestamp"]
        db_state.matched_lat = state["matched_position"]["lat"]
        db_state.matched_lon = state["matched_position"]["lon"]
        db_state.current_stop_id = state["current_stop_id"]
        db_state.next_stop_id = state["next_stop_id"]
        db_state.stop_sequence = state["stop_sequence"]
        db_state.segment_id = state["segment_id"]
        db_state.segment_progress = state["segment_progress"]
        db_state.progress = state["progress"]
        db_state.distance_to_next_stop = state["distance_to_next_stop"]
        db_state.speed = state["speed"]
        db_state.direction = state["direction"]
        db_state.movement = state["movement"]
        db_state.movement_state = state["movement_state"]
        db_state.current_delay = state["current_delay"]
        db_state.confidence = state["confidence"]
        db_state.source = state["source"]
        db_state.simulation_flag = state["simulation_flag"]

    else:
        # If no previous vehicle state exists, create a new one
        db_state = VehicleLiveState(
            vehicle_id=state["vehicle_id"],
            route_id=state["route_id"],
            timestamp=state["timestamp"],
            matched_lat=state["matched_position"]["lat"],
            matched_lon=state["matched_position"]["lon"],
            current_stop_id=state["current_stop_id"],
            next_stop_id=state["next_stop_id"],
            stop_sequence=state["stop_sequence"],
            segment_id=state["segment_id"],
            segment_progress=state["segment_progress"],
            progress=state["progress"],
            distance_to_next_stop=state["distance_to_next_stop"],
            speed=state["speed"],
            direction=state["direction"],
            movement=state["movement"],
            movement_state=state["movement_state"],
            current_delay=state["current_delay"],
            confidence=state["confidence"],
            source=state["source"],
            simulation_flag=state["simulation_flag"]
        )

        # Add the new state to the session
        db.add(db_state)

    # Commit changes to the database
    db.commit()
    db.close()

    # Return the current vehicle state as the response
    return state




from fastapi import Query

@router.get("/vehicles/live")
def get_live_vehicles(
    vehicle_id: str = Query(default=None),
    route_id: str = Query(default=None)
):
    db = SessionLocal()

    query = db.query(VehicleLiveState)

    # Apply filters
    if vehicle_id:
        query = query.filter(VehicleLiveState.vehicle_id == vehicle_id)

    if route_id:
        query = query.filter(VehicleLiveState.route_id == route_id)

    vehicles = query.all()

    result = []

    for v in vehicles:
        result.append({
            "vehicle_id": v.vehicle_id,
            "route_id": v.route_id,
            "timestamp": v.timestamp,

            "matched_position": {
                "lat": v.matched_lat,
                "lon": v.matched_lon
            },

            "current_stop_id": v.current_stop_id,
            "next_stop_id": v.next_stop_id,
            "stop_sequence": v.stop_sequence,

            "segment_id": v.segment_id,
            "segment_progress": v.segment_progress,
            "progress": v.progress,

            "distance_to_next_stop": v.distance_to_next_stop,

            "speed": v.speed,
            "direction": v.direction,

            "movement": v.movement,
            "movement_state": v.movement_state,

            "current_delay": v.current_delay,
            "confidence": v.confidence,

            "source": v.source,
            "simulation_flag": v.simulation_flag
        })

    db.close()

    return result