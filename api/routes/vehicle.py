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
from services.observation_pipeline import (
    process_observation_pipeline
)
from schemas.simulation_observation import (
    SimulationObservationRequest
)

router = APIRouter()
# 🔥 NEW: short-term memory for transitions
last_transition_per_vehicle = {}
# load route once (for now)
#route_reference = load_route_reference("CTA_M_112")
# 🔥 GLOBAL dwell memory
#dwell_tracker = {}

#segment_completion_tracker = {}

route_cache = {}
# TODO (Production):
# Replace temporary simulated defaults when real driver ingestion is introduced.
# source = driver_app
# simulation_flag = False
# trust_level = high
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
        "direction": payload.direction,

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
    return process_observation_pipeline(
    observation,
    db_observation 
)






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




@router.post("/simulation/observation")
def receive_simulation_observation(raw_payload: dict):

    payload = SimulationObservationRequest(**raw_payload)

    normalized_timestamp = normalize_timestamp(
        payload.timestamp
    )

    validate_location(
        payload.location["lat"],
        payload.location["lon"]
    )

    validate_speed(payload.speed_kmh)

    validate_bearing(payload.bearing)

    observation = {
    "observation_id": str(uuid.uuid4()),

    "vehicle_id": payload.vehicle_id,
    "route_id": payload.route_id,
    "direction": payload.direction,

    "timestamp": normalized_timestamp.isoformat(),

    "location": {
    "lat": payload.location["lat"],
    "lon": payload.location["lon"]
    },

    "speed": payload.speed_kmh,
    "bearing": payload.bearing,

    "day_of_week": payload.day_of_week,
    "day_number": payload.day_number,
    "time_period": payload.time_period,
    "simulation_seed": payload.simulation_seed,

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

    direction=observation["direction"],

    day_of_week=observation["day_of_week"],
    day_number=observation["day_number"],
    time_period=observation["time_period"],

    simulation_seed=observation["simulation_seed"],

    source=observation["source"],
    simulation_flag=observation["simulation_flag"],
    trust_level=observation["trust_level"],

    raw_payload=observation["raw_payload"]
)
    return process_observation_pipeline(
    observation,
    db_observation
)