from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from vehicle_state.engine import process_observation
from typing import Optional
from reference.loader import load_route_reference
from database.connection import SessionLocal
from models.vehicle_live_state import VehicleLiveState
from event_engine.engine import process_event #new
from event_engine.builder import build_event
from models.transit_event import TransitEvent
from models.transit_observation import TransitObservation
from models.trips_workflow import DriverAssignment

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
from datetime import datetime, timedelta, timezone
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

ACTIVE_TRACKING_STATUS = "active"
STALE_SECONDS = 60
UNAVAILABLE_SECONDS = 5 * 60


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_state_timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _location_status(last_updated):
    try:
        parsed = _parse_state_timestamp(last_updated)
    except Exception:
        return "unavailable"
    if parsed is None:
        return "unavailable"
    age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    if age_seconds > UNAVAILABLE_SECONDS:
        return "unavailable"
    if age_seconds > STALE_SECONDS:
        return "stale"
    return "active"


def _normalize_driver_timestamp(timestamp: datetime):
    if timestamp.tzinfo is None:
        normalized = timestamp.replace(tzinfo=timezone.utc)
    else:
        normalized = timestamp.astimezone(timezone.utc)

    now = datetime.now(timezone.utc)
    if normalized > now + timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="future timestamp")
    if normalized < now - timedelta(hours=6):
        raise HTTPException(status_code=400, detail="stale timestamp")
    return normalized.replace(tzinfo=None)


def _vehicle_tracking_response(state, assignment):
    last_updated = state.timestamp
    location_status = _location_status(last_updated)
    return {
        "assignment_id": assignment.assignment_id,
        "trip_id": assignment.trip_id,
        "vehicle_id": assignment.vehicle_id,
        "route_id": assignment.route_id,
        "lat": state.matched_lat,
        "lng": state.matched_lon,
        "lon": state.matched_lon,
        "speed": state.speed,
        "heading": state.direction,
        "last_updated": last_updated,
        "last_update": last_updated,
        "timestamp": last_updated,
        "status": assignment.status,
        "location_status": location_status,
        "stale": location_status == "stale",
    }


def _validate_active_assignment(db: Session, payload: VehicleLocationRequest):
    print("DRIVER_LOCATION_RECEIVED_BODY:", payload.model_dump())
    print("DRIVER_LOCATION_ASSIGNMENT_LOOKUP:", payload.assignment_id)
    if not payload.assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id is required")
    if not payload.driver_id:
        raise HTTPException(status_code=400, detail="driver_id is required")
    if not payload.vehicle_id:
        raise HTTPException(status_code=400, detail="vehicle_id is required")

    assignment = (
        db.query(DriverAssignment)
        .filter(DriverAssignment.assignment_id == payload.assignment_id)
        .first()
    )
    if not assignment:
        print("DRIVER_LOCATION_VALIDATION_RESULT: Assignment not found")
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    print("DRIVER_LOCATION_ASSIGNMENT_STATUS:", assignment.status)
    if assignment.status != ACTIVE_TRACKING_STATUS:
        print(f"DRIVER_LOCATION_VALIDATION_RESULT: Assignment is not active: {assignment.status}")
        raise HTTPException(
            status_code=400,
            detail=f"Assignment is not active: {assignment.status}",
        )
    
    driver_match = assignment.driver_id == payload.driver_id
    vehicle_match = assignment.vehicle_id == payload.vehicle_id
    route_match = payload.route_id in (None, "", assignment.route_id)
    trip_match = payload.trip_id in (None, "", assignment.trip_id)

    print("DRIVER_LOCATION_DRIVER_MATCH:", driver_match)
    print("DRIVER_LOCATION_VEHICLE_MATCH:", vehicle_match)
    print("DRIVER_LOCATION_ROUTE_MATCH:", route_match)

    checks = {
        "driver_id": driver_match,
        "vehicle_id": vehicle_match,
        "route_id": route_match,
        "trip_id": trip_match,
    }
    if not all(checks.values()):
        print("DRIVER_LOCATION_VALIDATION_RESULT: Payload mismatch")
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Driver location payload does not match assignment",
                "checks": checks,
            },
        )
    print("DRIVER_LOCATION_VALIDATION_RESULT: PASS")
    return assignment


@router.post("/driver/location")
def receive_driver_location(raw_payload: dict, db: Session = Depends(get_db)):
    payload = VehicleLocationRequest(**raw_payload)
    assignment = _validate_active_assignment(db, payload)

    normalized_timestamp = _normalize_driver_timestamp(payload.timestamp)
    validate_location(payload.lat, payload.lon)
    validate_speed(payload.speed)
    validate_bearing(payload.bearing)

    db_observation = TransitObservation(
        observation_id=str(uuid.uuid4()),
        vehicle_id=assignment.vehicle_id,
        route_id=assignment.route_id,
        timestamp=normalized_timestamp,
        lat=payload.lat,
        lon=payload.lon,
        speed=payload.speed,
        bearing=payload.bearing,
        source=SourceEnum.driver_app.value,
        simulation_flag=False,
        trust_level=TrustLevelEnum.high.value,
        raw_payload=raw_payload,
        assignment_id=assignment.assignment_id,
        driver_id=assignment.driver_id,
        trip_id=assignment.trip_id,
    )
    db.add(db_observation)

    state = (
        db.query(VehicleLiveState)
        .filter(VehicleLiveState.vehicle_id == assignment.vehicle_id)
        .first()
    )
    
    if state is not None:
        print("LATEST_VEHICLE_POSITION_BEFORE:", {
            "vehicle_id": state.vehicle_id,
            "lat": state.matched_lat,
            "lng": state.matched_lon,
            "timestamp": state.timestamp,
        })
    else:
        print("LATEST_VEHICLE_POSITION_BEFORE: None")

    timestamp_text = normalized_timestamp.replace(tzinfo=timezone.utc).isoformat()
    heading_text = None if payload.bearing is None else str(payload.bearing)

    if state is None:
        state = VehicleLiveState(vehicle_id=assignment.vehicle_id)
        db.add(state)

    state.route_id = assignment.route_id
    state.timestamp = timestamp_text
    state.matched_lat = payload.lat
    state.matched_lon = payload.lon
    state.speed = payload.speed
    state.direction = heading_text
    state.source = SourceEnum.driver_app.value
    state.simulation_flag = False
    state.assignment_id = assignment.assignment_id
    state.driver_id = assignment.driver_id
    state.trip_id = assignment.trip_id

    db.commit()
    db.refresh(state)
    db.refresh(db_observation)
    
    print("TRIP_LOCATION_LOG_CREATED:", db_observation.observation_id)
    print("LATEST_VEHICLE_POSITION_AFTER:", {
        "vehicle_id": state.vehicle_id,
        "lat": state.matched_lat,
        "lng": state.matched_lon,
        "timestamp": state.timestamp,
    })

    return {"status": "success", "vehicle": _vehicle_tracking_response(state, assignment)}


@router.get("/passenger/routes/{route_id}/vehicles")
def get_passenger_route_vehicles(route_id: str, db: Session = Depends(get_db)):
    print("PASSENGER_ROUTE_VEHICLES_REQUEST_ROUTE_ID:", route_id)
    assignments = (
        db.query(DriverAssignment)
        .filter(
            DriverAssignment.route_id == route_id,
            DriverAssignment.status == ACTIVE_TRACKING_STATUS,
        )
        .all()
    )
    print("PASSENGER_ACTIVE_ASSIGNMENTS_FOR_ROUTE:", [a.assignment_id for a in assignments])
    
    vehicles_by_id = {}
    positions_found = []
    for assignment in assignments:
        state = (
            db.query(VehicleLiveState)
            .filter(
                VehicleLiveState.vehicle_id == assignment.vehicle_id,
            )
            .first()
        )
        if state is None:
            continue
        if state.assignment_id and state.assignment_id != assignment.assignment_id:
            continue
        vehicle = _vehicle_tracking_response(state, assignment)
        existing = vehicles_by_id.get(vehicle["vehicle_id"])
        if existing is None or str(vehicle.get("last_updated") or "") > str(existing.get("last_updated") or ""):
            vehicles_by_id[vehicle["vehicle_id"]] = vehicle
        positions_found.append(vehicle["vehicle_id"])

    result = list(vehicles_by_id.values())
    print("PASSENGER_LATEST_POSITIONS_FOUND:", positions_found)
    print("PASSENGER_ROUTE_VEHICLES_RESPONSE:", result)
    return {"vehicles": result, "data": result, "results": result}


@router.get("/passenger/trips/{trip_id}/vehicle-location")
def get_passenger_trip_vehicle_location(trip_id: str, db: Session = Depends(get_db)):
    assignment = (
        db.query(DriverAssignment)
        .filter(
            DriverAssignment.trip_id == trip_id,
            DriverAssignment.status == ACTIVE_TRACKING_STATUS,
        )
        .first()
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="No active assignment for trip")

    state = (
        db.query(VehicleLiveState)
        .filter(
            VehicleLiveState.vehicle_id == assignment.vehicle_id,
        )
        .first()
    )
    if state is None or _location_status(state.timestamp) == "unavailable":
        raise HTTPException(status_code=404, detail="Live vehicle location unavailable")

    return _vehicle_tracking_response(state, assignment)
# TODO (Production):
# Replace temporary simulated defaults when real driver ingestion is introduced.
# source = driver_app
# simulation_flag = False
# trust_level = high

@router.get("/driver/route-info")
def get_driver_route_info(
    vehicle_id: str,
    route_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns detailed route information for a driver.
    The response includes the route stub and vehicle tracking data.
    """
    # Find active or scheduled assignment for the vehicle
    assignment_query = db.query(DriverAssignment).filter(
        DriverAssignment.vehicle_id == vehicle_id,
        DriverAssignment.status.in_([ACTIVE_TRACKING_STATUS, "scheduled"]),
    )
    if assignment_id:
        assignment_query = assignment_query.filter(DriverAssignment.assignment_id == assignment_id)
    assignment = assignment_query.first()
    if not assignment:
        raise HTTPException(status_code=404, detail="No active or scheduled assignment for vehicle")

    # Get live vehicle state
    state = (
        db.query(VehicleLiveState)
        .filter(VehicleLiveState.vehicle_id == assignment.vehicle_id)
        .first()
    )
    if state:
        vehicle_res = _vehicle_tracking_response(state, assignment)
    else:
        # Graceful fallback: return a vehicle response with null coordinates rather than raising a 404
        vehicle_res = {
            "assignment_id": assignment.assignment_id,
            "trip_id": assignment.trip_id,
            "vehicle_id": assignment.vehicle_id,
            "route_id": assignment.route_id,
            "lat": None,
            "lng": None,
            "lon": None,
            "speed": 0.0,
            "heading": None,
            "last_updated": None,
            "last_update": None,
            "timestamp": None,
            "status": assignment.status,
            "location_status": "unavailable",
            "stale": True,
        }

    # Load stops and shape for the route using GTFS data
    trip = None
    if assignment.trip_id:
        from models.trip import Trip
        trip = db.query(Trip).filter(Trip.trip_id == assignment.trip_id).first()
    if not trip:
        from models.trip import Trip
        trip = db.query(Trip).filter(Trip.route_id == assignment.route_id).first()

    stops_list = []
    geometry = []
    if trip:
        # Load shape points if available
        from models.shape import Shape
        shape_points = (
            db.query(Shape)
            .filter(Shape.shape_id == trip.shape_id)
            .order_by(Shape.sequence)
            .all()
        )
        if shape_points:
            geometry = [{"lat": sp.lat, "lon": sp.lon} for sp in shape_points]
        # Load stops for origin/destination display
        from models.stop_time import StopTime
        from models.stop import Stop
        stop_times = (
            db.query(StopTime)
            .filter(StopTime.trip_id == trip.trip_id)
            .order_by(StopTime.stop_sequence)
            .all()
        )
        for st in stop_times:
            stop = db.query(Stop).filter(Stop.stop_id == st.stop_id).first()
            if stop:
                stops_list.append({
                    "stop_id": stop.stop_id,
                    "name": stop.name,
                    "lat": stop.lat,
                    "lon": stop.lon,
                    "sequence": st.stop_sequence,
                })
    # Fallback if no shape geometry was found
    if not geometry:
        geometry = [{"lat": s["lat"], "lon": s["lon"]} for s in stops_list]

    origin = stops_list[0]["name"] if stops_list else "Origin placeholder"
    destination = stops_list[-1]["name"] if len(stops_list) >= 2 else "Destination placeholder"

    # Minimal route object (can be expanded later)
    route_obj = {
        "route_id": assignment.route_id,
        "route_name": assignment.route_id,
        "origin": origin,
        "destination": destination,
        "stops": stops_list,
        "geometry": geometry,
    }

    return {
        "route": route_obj,
        "vehicle": vehicle_res,
    }


@router.post("/driver/route-info/advance")
def advance_driver_route_info(
    vehicle_id: str,
    route_id: Optional[str] = None,
    assignment_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    response = get_driver_route_info(
        vehicle_id=vehicle_id,
        route_id=route_id,
        assignment_id=assignment_id,
        driver_id=driver_id,
        db=db,
    )
    route = response.get("route", {})
    stops = route.get("stops") or []
    total_stops = len(stops)
    route["current_stop_sequence"] = min(total_stops, 2) if total_stops else 1
    route["total_stops"] = total_stops
    route["progress_percent"] = (1 / total_stops * 100.0) if total_stops else 0.0
    response["route"] = route
    return response

# Replace temporary simulated defaults when real driver ingestion is introduced.
# source = driver_app
# simulation_flag = False
# trust_level = high

@router.get("/routes/{route_id}")
def get_route_details(route_id: str, db: Session = Depends(get_db)):
    """
    Returns detailed route information for the passenger app.
    The response format is structured as a route plan with legs.
    """
    from models.trip import Trip
    trip = db.query(Trip).filter(Trip.route_id == route_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail=f"No trip found for route {route_id}")

    # Load stops for origin/destination and timeline display
    from models.stop_time import StopTime
    from models.stop import Stop
    stop_times = (
        db.query(StopTime)
        .filter(StopTime.trip_id == trip.trip_id)
        .order_by(StopTime.stop_sequence)
        .all()
    )

    stops_list = []
    for st in stop_times:
        stop = db.query(Stop).filter(Stop.stop_id == st.stop_id).first()
        if stop:
            stops_list.append({
                "stop_id": stop.stop_id,
                "name": stop.name,
                "lat": stop.lat,
                "lon": stop.lon,
                "sequence": st.stop_sequence,
            })

    if not stops_list:
        raise HTTPException(status_code=404, detail="No stops found for route")

    # Load shape points if available
    from models.shape import Shape
    shape_points = (
        db.query(Shape)
        .filter(Shape.shape_id == trip.shape_id)
        .order_by(Shape.sequence)
        .all()
    )
    shape_list = [{"lat": sp.lat, "lon": sp.lon} for sp in shape_points] if shape_points else []

    # Build legs connecting consecutive stops
    legs = []
    
    def get_nearest_shape_idx(lat, lon, shape):
        if not shape:
            return 0
        best_idx = 0
        best_dist = float('inf')
        for idx, pt in enumerate(shape):
            dist = (pt["lat"] - lat)**2 + (pt["lon"] - lon)**2
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        return best_idx

    # If shape is not empty, slice it between consecutive stops
    for i in range(len(stops_list) - 1):
        from_stop = stops_list[i]
        to_stop = stops_list[i + 1]
        
        leg_geometry = []
        if shape_list:
            from_idx = get_nearest_shape_idx(from_stop["lat"], from_stop["lon"], shape_list)
            to_idx = get_nearest_shape_idx(to_stop["lat"], to_stop["lon"], shape_list)
            if from_idx <= to_idx:
                leg_geometry = shape_list[from_idx : to_idx + 1]
            else:
                leg_geometry = list(reversed(shape_list[to_idx : from_idx + 1]))
        
        if not leg_geometry:
            leg_geometry = [
                {"lat": from_stop["lat"], "lon": from_stop["lon"]},
                {"lat": to_stop["lat"], "lon": to_stop["lon"]}
            ]

        # Formatting times
        departure_time = f"{6 + i:02d}:00:00"
        arrival_time = f"{6 + i:02d}:05:00"

        legs.append({
            "mode": "bus",
            "from_stop_id": from_stop["stop_id"],
            "to_stop_id": to_stop["stop_id"],
            "from_stop": {
                "stop_id": from_stop["stop_id"],
                "name": from_stop["name"],
                "lat": from_stop["lat"],
                "lon": from_stop["lon"],
            },
            "to_stop": {
                "stop_id": to_stop["stop_id"],
                "name": to_stop["name"],
                "lat": to_stop["lat"],
                "lon": to_stop["lon"],
            },
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "travel_time": 300,
            "waiting_time": 0,
            "route_id": route_id,
            "trip_id": trip.trip_id,
            "route_label": route_id,
            "fare": 5.0,
            "fare_currency": "EGP",
            "geometry": leg_geometry,
            "geometry_source": "gtfs_shape" if shape_list else "straight_line"
        })

    return {
        "route_id": route_id,
        "route_name": route_id,
        "label": route_id,
        "total_travel_time": len(legs) * 300,
        "total_fare": len(legs) * 5.0,
        "legs": legs
    }

@router.post("/vehicle/location")
def receive_vehicle_location(raw_payload: dict, db: Session = Depends(get_db)):



    # 🔥 INGESTION NORMALIZATION

    payload = VehicleLocationRequest(**raw_payload)
    
    # Try to resolve route_id, assignment_id, driver_id, and trip_id from active/scheduled driver assignments
    assignment = db.query(DriverAssignment).filter(
        DriverAssignment.vehicle_id == payload.vehicle_id,
        DriverAssignment.status == "active"
    ).first()
    if not assignment:
        assignment = db.query(DriverAssignment).filter(
            DriverAssignment.vehicle_id == payload.vehicle_id,
            DriverAssignment.status == "scheduled"
        ).first()
        
    if assignment:
        if not payload.route_id:
            payload.route_id = assignment.route_id
        if not payload.assignment_id:
            payload.assignment_id = assignment.assignment_id
        if not payload.driver_id:
            payload.driver_id = assignment.driver_id
        if not payload.trip_id:
            payload.trip_id = assignment.trip_id

    if not payload.route_id:
        raise HTTPException(status_code=400, detail="route_id is required")

    # validations
    normalized_timestamp = normalize_timestamp(payload.timestamp)

    validate_location(payload.lat, payload.lon)
    validate_speed(payload.speed)
    validate_bearing(payload.bearing)

    # build standardized TransitObservation
    observation = {
        "observation_id": str(uuid.uuid4()),

        "vehicle_id": payload.vehicle_id,
        "route_id": payload.route_id,
        "direction": payload.direction if payload.direction is not None else 0,

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

    raw_payload=observation["raw_payload"],
    assignment_id=payload.assignment_id,
    driver_id=payload.driver_id,
    trip_id=payload.trip_id
)
    return process_observation_pipeline(
    observation,
    db_observation 
)




from fastapi import Query

@router.get("/vehicles/live")
def get_live_vehicles(
    vehicle_id: str = Query(default=None),
    route_id: str = Query(default=None),
    limit: int = Query(default=100)
):
    db = SessionLocal()

    query = db.query(VehicleLiveState)

    # Apply filters
    if vehicle_id:
        query = query.filter(VehicleLiveState.vehicle_id == vehicle_id)

    if route_id:
        query = query.filter(VehicleLiveState.route_id == route_id)

    vehicles = query.limit(limit).all()

    result = []

    for v in vehicles:
        result.append({
            "vehicle_id": v.vehicle_id,
            "route_id": v.route_id,
            "timestamp": v.timestamp,
            "last_update": v.timestamp,
            "last_updated": v.timestamp,
            "lat": v.matched_lat,
            "lon": v.matched_lon,
            "lng": v.matched_lon,

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
            "speed_kmh": v.speed,
            "direction": v.direction,
            "heading": v.direction,

            "movement": v.movement,
            "movement_state": v.movement_state,

            "current_delay": v.current_delay,
            "confidence": v.confidence,

            "source": v.source,
            "simulation_flag": v.simulation_flag,
            "status": _location_status(v.timestamp)
        })

    db.close()

    return {"vehicles": result, "data": result, "results": result}




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
