from fastapi import APIRouter
from vehicle_state.engine import process_observation
from reference.loader import load_route_reference
from database.connection import SessionLocal
from models.vehicle_live_state import VehicleLiveState
from event_engine.engine import process_event #new
from event_engine.builder import build_event
from models.transit_event import TransitEvent
from models.transit_observation import TransitObservation

from schemas.transit import VehicleLocationRequest
from utils.validators import (
    normalize_timestamp,
    validate_location,
    validate_speed,
    validate_bearing
)
from event_engine.traversal_tracker import (
    start_traversal,
    get_active_traversal,
    clear_traversal
)
from event_engine.dwell_tracker import (
    start_dwell,
    get_active_dwell,
    clear_dwell
)
from enums.transit import SourceEnum, TrustLevelEnum

import uuid
from datetime import datetime


router = APIRouter()
# 🔥 NEW: short-term memory for transitions
last_transition_per_vehicle = {}
# load route once (for now)
#route_reference = load_route_reference("CTA_M_112")
# 🔥 GLOBAL dwell memory
#dwell_tracker = {}

#segment_completion_tracker = {}

route_cache = {}

@router.post("/vehicle/location")

def receive_vehicle_location(raw_payload: dict):


    # 🔥 INGESTION NORMALIZATION

    payload = VehicleLocationRequest(**raw_payload)

    # validations
    normalized_timestamp = normalize_timestamp(payload.timestamp)
   # normalized_timestamp =payload.timestamp

    validate_location(payload.lat, payload.lon)
    validate_speed(payload.speed)
    validate_bearing(payload.bearing)

    # build standardized TransitObservation
    observation = {
        "observation_id": str(uuid.uuid4()),

        "vehicle_id": payload.vehicle_id,
        "route_id": payload.route_id,

        "timestamp": normalized_timestamp.isoformat(),

        "location": {
            "lat": payload.lat,
            "lon": payload.lon
        },

        "speed": payload.speed,
        "bearing": payload.bearing,

        # temporary defaults
        "source": SourceEnum.simulated.value,
        "simulation_flag": True,
        "trust_level": TrustLevelEnum.medium.value,

        "raw_payload": raw_payload,

        "ingested_at": datetime.utcnow().isoformat()
    }
    db_observation = TransitObservation(
    observation_id=observation["observation_id"],
    vehicle_id=observation["vehicle_id"],
    route_id=observation["route_id"],
    timestamp=normalized_timestamp,

    lat=observation["location"]["lat"],
    lon=observation["location"]["lon"],

    speed=observation["speed"],
    bearing=observation["bearing"],

    source=observation["source"],
    simulation_flag=observation["simulation_flag"],
    trust_level=observation["trust_level"],

    raw_payload=observation["raw_payload"]
)


    vehicle_id = observation["vehicle_id"]
    db = SessionLocal()

    route_id = observation["route_id"]

    if route_id not in route_cache:
        route_cache[route_id] = load_route_reference(route_id)

    route_reference = route_cache[route_id]

    print("ROUTE:", route_reference["route_id"])
    db.add(db_observation)

    # 1️⃣ Load previous state
    db_state = (
        db.query(VehicleLiveState)
        .filter(VehicleLiveState.vehicle_id == vehicle_id)
        .first()
    )

    previous_state = None

    if db_state:
        previous_state = {
            "progress": db_state.progress,
            "movement_state": db_state.movement_state,
            "next_stop_id": db_state.next_stop_id,
            "stop_sequence": db_state.stop_sequence,
            "current_delay": db_state.current_delay 
        }

    # 2️⃣ Process observation
    state = process_observation(
        observation,
        previous_state,
        route_reference
    )

    events = process_event(
        current_state=state,
        previous_state=previous_state,
        route_reference=route_reference
    )

    print("PREV STOP_SEQ:", previous_state.get("stop_sequence") if previous_state else None)
    print("CURR STOP_SEQ:", state.get("stop_sequence"))

    prev_seq = previous_state.get("stop_sequence") if previous_state else None
    curr_seq = state.get("stop_sequence")
    current_transition = (prev_seq, curr_seq)

    # 3️⃣ Filter duplicate transitions
    filtered_events = []
    last_transition = last_transition_per_vehicle.get(vehicle_id)

    for event in events:
        # 🔵 Apply duplicate filter ONLY for segment_travel
        if event["event_type"] == "segment_travel":
            if last_transition == current_transition:
                print("IGNORED: duplicate transition", current_transition)
                continue
        filtered_events.append(event)
    # Update only if segment event occurred
    if any(e["event_type"] == "segment_travel" for e in filtered_events):
        last_transition_per_vehicle[vehicle_id] = current_transition

    print("EVENTS:", filtered_events)

    
                            

    # 5️⃣ Merge events
    final_events = filtered_events 

    print("FINAL EVENTS:", final_events)
    print("STATE:", state["movement_state"])
    # 🔥 6️⃣ STORE EVENTS IN DB (ADD HERE)
    for event in final_events:
     db_event = TransitEvent(
        event_id=event["event_id"],
        event_type=event["event_type"],
        vehicle_id=event["vehicle_id"],
        route_id=event["route_id"],
        timestamp=event["timestamp"],

        stop_id=event.get("stop_id"),
        from_stop_id=event.get("from_stop_id"),
        to_stop_id=event.get("to_stop_id"),
        segment_id=event.get("segment_id"),

        stop_sequence=event.get("stop_sequence"),

        metrics=event.get("metrics", {}),

        confidence=event.get("confidence"),
        source=event.get("source"),
        simulation_flag=event.get("simulation_flag")
    )
     db.add(db_event)

    # 6️⃣ Update DB
    if db_state:
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
        db.add(db_state)

    db.commit()
    db.close()

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




@router.get("/events")
def get_events(
    vehicle_id: str = None,
    route_id: str = None
):
    db = SessionLocal()

    query = db.query(TransitEvent)

    # Optional filtering
    if vehicle_id:
        query = query.filter(
            TransitEvent.vehicle_id == vehicle_id
        )

    if route_id:
        query = query.filter(
            TransitEvent.route_id == route_id
        )

    # Newest first
    events = query.order_by(
        TransitEvent.timestamp.desc()
    ).all()

    db.close()

    return events