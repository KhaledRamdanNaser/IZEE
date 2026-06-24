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
from models.trips_workflow import DriverAssignment, OperationalRoute
from models.route import Route
from models.transit_incident import TransitIncident
from models.control_message import ControlMessage

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

    # Check for delay incidents with speed checkpoint that haven't been verified yet
    delay_incidents = (
        db.query(TransitIncident)
        .filter(
            TransitIncident.vehicle_id == assignment.vehicle_id,
            TransitIncident.category.ilike("%delay%"),
            TransitIncident.status != "resolved"
        )
        .all()
    )
    for inc in delay_incidents:
        payload_data = inc.raw_payload or {}
        checkpoint = payload_data.get("speed_checkpoint")
        if checkpoint and not checkpoint.get("checked", False):
            ref_speed = checkpoint.get("reference_speed", 0.0)
            if payload.speed <= ref_speed:
                # Driver did not accelerate!
                inc.transmitted_to_control = True
                
                # Append warning to incident details
                warning_note = f"\n\n[System Alert: Driver was asked to speed up (Ref speed: {ref_speed:.1f} km/h) but has not accelerated. Current speed: {payload.speed:.1f} km/h.]"
                if warning_note not in (inc.details or ""):
                    inc.details = (inc.details or "") + warning_note
                
                # Send Control Center Message
                cc_msg = ControlMessage(
                    recipient_type="control_center",
                    recipient_id=None,
                    sender="System",
                    subject="Vehicle Speed Alert",
                    body=f"Driver {assignment.driver_id} did not accelerate vehicle {assignment.vehicle_id} after being requested to speed up. Current speed: {payload.speed:.1f} km/h (Reference: {ref_speed:.1f} km/h).",
                    priority="high",
                    source="system"
                )
                db.add(cc_msg)
                
                # Send Supervisor Message
                if assignment.supervisor_id:
                    sv_msg = ControlMessage(
                        recipient_type="supervisor",
                        recipient_id=assignment.supervisor_id,
                        sender="System",
                        subject="Driver Speed Warning",
                        body=f"Driver {assignment.driver_id} for vehicle {assignment.vehicle_id} did not accelerate after being requested to speed up. Current speed: {payload.speed:.1f} km/h (Reference: {ref_speed:.1f} km/h).",
                        priority="high",
                        source="system"
                    )
                    db.add(sv_msg)
                
                checkpoint["checked"] = True
                checkpoint["accelerated"] = False
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(inc, "raw_payload")
            else:
                # Driver accelerated!
                checkpoint["checked"] = True
                checkpoint["accelerated"] = True
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(inc, "raw_payload")

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

import math
import json
import urllib.request
import urllib.error
import os

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")

def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def decode_polyline(polyline, precision=5):
    coordinates = []
    index = 0
    lat = 0
    lon = 0
    factor = 10 ** precision

    while index < len(polyline):
        result = 1
        shift = 0
        while True:
            byte = ord(polyline[index]) - 63 - 1
            index += 1
            result += byte << shift
            shift += 5
            if byte < 0x1F:
                break
        lat += ~(result >> 1) if result & 1 else result >> 1

        result = 1
        shift = 0
        while True:
            byte = ord(polyline[index]) - 63 - 1
            index += 1
            result += byte << shift
            shift += 5
            if byte < 0x1F:
                break
        lon += ~(result >> 1) if result & 1 else result >> 1
        coordinates.append([lat / factor, lon / factor])
    return coordinates

def get_osrm_driving_geometry(coords):
    if not OSRM_BASE_URL or len(coords) < 2:
        return []
    
    coord_strs = [f"{lon},{lat}" for lat, lon in coords]
    geometry_points = []
    chunk_size = 25
    
    for i in range(0, len(coord_strs) - 1, chunk_size - 1):
        chunk = coord_strs[i:i + chunk_size]
        if len(chunk) < 2:
            break
        
        url = (
            f"{OSRM_BASE_URL.rstrip('/')}/route/v1/driving/"
            f"{';'.join(chunk)}"
            "?overview=full&geometries=polyline"
        )
        
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "IZEE-Graduation-Project/1.0",
                "Accept": "application/json",
            },
        )
        
        try:
            with urllib.request.urlopen(request, timeout=3.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("code") == "Ok" and payload.get("routes"):
                    route = payload["routes"][0]
                    geom_str = route.get("geometry")
                    if geom_str:
                        decoded = decode_polyline(geom_str)
                        for lat, lon in decoded:
                            if not geometry_points or geometry_points[-1] != {"lat": lat, "lon": lon}:
                                geometry_points.append({"lat": lat, "lon": lon})
        except Exception as e:
            print(f"OSRM driving route error: {e}")
            
    return geometry_points

def seconds_to_time_str(seconds):
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

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

    # Retrieve current stop sequence from live state, default to 1
    current_stop_seq = 1
    if state and state.stop_sequence is not None:
        current_stop_seq = state.stop_sequence

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
        # Load stops for display
        from models.stop_time import StopTime
        from models.stop import Stop
        stop_times = (
            db.query(StopTime)
            .filter(StopTime.trip_id == trip.trip_id)
            .order_by(StopTime.stop_sequence)
            .all()
        )
        
        # Load GTFS schedules from RAPTOR index
        import routing_integration
        indexes = routing_integration.get_raptor_indexes()
        
        trip_schedule = []
        if indexes:
            stop_times_by_trip = indexes.get("stop_times_by_trip", {})
            trip_schedule = stop_times_by_trip.get(str(trip.trip_id), [])
            
        # Synthesize schedule if trip is missing from the index (e.g. custom database trips)
        if not trip_schedule:
            start_seconds = 28800  # Default: 08:00:00
            if assignment.planned_start_time:
                try:
                    parts = str(assignment.planned_start_time).split(":")
                    h = int(parts[0])
                    m = int(parts[1]) if len(parts) > 1 else 0
                    s = int(parts[2]) if len(parts) > 2 else 0
                    start_seconds = h * 3600 + m * 60 + s
                except Exception:
                    pass
            trip_schedule = []
            for st in stop_times:
                arrival_time = start_seconds + (st.stop_sequence - 1) * 300
                trip_schedule.append({
                    "stop_id": st.stop_id,
                    "stop_sequence": st.stop_sequence,
                    "arrival_time": arrival_time,
                    "departure_time": arrival_time
                })
            
        schedule_map = {}
        for st_info in trip_schedule:
            schedule_map[(st_info["stop_sequence"], str(st_info["stop_id"]))] = st_info
            
        # Find next stop's scheduled arrival time
        next_stop_sched_time = None
        for st in stop_times:
            if st.stop_sequence == current_stop_seq:
                st_info = schedule_map.get((st.stop_sequence, str(st.stop_id)))
                if st_info:
                    next_stop_sched_time = st_info["arrival_time"]
                break

        # Extract stop models efficiently
        stop_ids = [st.stop_id for st in stop_times]
        stops_by_id = {s.stop_id: s for s in db.query(Stop).filter(Stop.stop_id.in_(stop_ids)).all()}
        
        # Build static cumulative distances for all stops
        static_distances = {}
        cumulative_dist = 0.0
        prev_lat = None
        prev_lon = None
        for st in stop_times:
            stop = stops_by_id.get(st.stop_id)
            if stop:
                if prev_lat is not None and prev_lon is not None:
                    cumulative_dist += haversine_km(prev_lat, prev_lon, stop.lat, stop.lon)
                static_distances[st.stop_sequence] = cumulative_dist
                prev_lat = stop.lat
                prev_lon = stop.lon
        
        veh_lat = state.matched_lat if (state and state.matched_lat is not None) else None
        veh_lon = state.matched_lon if (state and state.matched_lon is not None) else None

        first_stop_sched_time = None
        if trip_schedule:
            sorted_sched = sorted(trip_schedule, key=lambda x: x["stop_sequence"])
            if sorted_sched:
                first_stop_sched_time = sorted_sched[0]["arrival_time"]

        for st in stop_times:
            stop = stops_by_id.get(st.stop_id)
            if not stop:
                continue
                
            seq = st.stop_sequence
            
            # Status, Distance & ETA Calculations
            if seq < current_stop_seq:
                stop_status = "completed"
                distance_km = static_distances.get(seq, 0.0)
                
                st_info = schedule_map.get((seq, str(stop.stop_id)))
                if st_info and first_stop_sched_time is not None:
                    eta_minutes = int(max(0, st_info["arrival_time"] - first_stop_sched_time) // 60)
                else:
                    eta_minutes = (seq - 1) * 5
            elif seq == current_stop_seq:
                stop_status = "next"
                if veh_lat is not None and veh_lon is not None:
                    distance_km = haversine_km(veh_lat, veh_lon, stop.lat, stop.lon)
                else:
                    distance_km = static_distances.get(seq, 0.0)
                eta_minutes = round(max(1.0, distance_km * 2.0))
            else:
                stop_status = "upcoming"
                dist_to_next = 0.0
                if veh_lat is not None and veh_lon is not None:
                    next_stop_model = None
                    for nst in stop_times:
                        if nst.stop_sequence == current_stop_seq:
                            next_stop_model = stops_by_id.get(nst.stop_id)
                            break
                    if next_stop_model:
                        dist_to_next = haversine_km(veh_lat, veh_lon, next_stop_model.lat, next_stop_model.lon)
                    else:
                        dist_to_next = static_distances.get(current_stop_seq, 0.0)
                else:
                    dist_to_next = static_distances.get(current_stop_seq, 0.0)
                
                segment_diff = max(0.0, static_distances.get(seq, 0.0) - static_distances.get(current_stop_seq, 0.0))
                distance_km = dist_to_next + segment_diff
                
                st_info = schedule_map.get((seq, str(stop.stop_id)))
                if st_info and next_stop_sched_time is not None:
                    sched_diff_sec = max(0, st_info["arrival_time"] - next_stop_sched_time)
                    if veh_lat is not None and veh_lon is not None:
                        eta_next_min = max(1.0, dist_to_next * 2.0)
                        eta_minutes = round(eta_next_min + (sched_diff_sec / 60.0))
                    else:
                        eta_minutes = round(5.0 + (sched_diff_sec / 60.0))
                else:
                    eta_minutes = round(max(1.0, distance_km * 2.0))

            st_info = schedule_map.get((seq, str(stop.stop_id)))
            scheduled_time_str = "--"
            if st_info:
                scheduled_time_str = seconds_to_time_str(st_info["arrival_time"])

            stops_list.append({
                "stop_id": stop.stop_id,
                "name": stop.name,
                "lat": stop.lat,
                "lon": stop.lon,
                "sequence": seq,
                "status": stop_status,
                "distance_km": distance_km,
                "eta_minutes": eta_minutes,
                "scheduled_time": scheduled_time_str,
            })

        # Load shape points if available (from cache/db)
        if trip.shape_id:
            shape_id_str = str(trip.shape_id)
            if indexes and "shape_points" in indexes and shape_id_str in indexes["shape_points"]:
                geometry = [{"lat": pt[0], "lon": pt[1]} for pt in indexes["shape_points"][shape_id_str]]
            else:
                from models.shape import Shape
                shape_points = (
                    db.query(Shape)
                    .filter(Shape.shape_id == trip.shape_id)
                    .order_by(Shape.sequence)
                    .all()
                )
                if shape_points:
                    geometry = [{"lat": sp.lat, "lon": sp.lon} for sp in shape_points]
                    
        # Fallback to OSRM driving profile street geometry if no shape geometry is present
        if not geometry and stops_list:
            stop_coords = [(s["lat"], s["lon"]) for s in stops_list]
            geometry = get_osrm_driving_geometry(stop_coords)
            
        # Fallback if both shape points and OSRM fail
        if not geometry:
            geometry = [{"lat": s["lat"], "lon": s["lon"]} for s in stops_list]

    origin = stops_list[0]["name"] if stops_list else "Origin placeholder"
    destination = stops_list[-1]["name"] if len(stops_list) >= 2 else "Destination placeholder"

    # Calculate route progress and status
    total_stops = len(stops_list)
    progress_percent = 0.0
    if total_stops > 0:
        if current_stop_seq > total_stops:
            progress_percent = 100.0
        else:
            progress_percent = ((current_stop_seq - 1) / total_stops) * 100.0

    route_status = "completed" if current_stop_seq > total_stops else "active"

    # Route object with actual sequence, status, progress and stops
    route_obj = {
        "route_id": assignment.route_id,
        "route_name": assignment.route_id,
        "origin": origin,
        "destination": destination,
        "current_stop_sequence": current_stop_seq,
        "total_stops": total_stops,
        "progress_percent": progress_percent,
        "status": route_status,
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
    # Find assignment
    assignment_query = db.query(DriverAssignment).filter(
        DriverAssignment.vehicle_id == vehicle_id,
        DriverAssignment.status.in_([ACTIVE_TRACKING_STATUS, "scheduled"]),
    )
    if assignment_id:
        assignment_query = assignment_query.filter(DriverAssignment.assignment_id == assignment_id)
    assignment = assignment_query.first()
    if not assignment:
        raise HTTPException(status_code=404, detail="No active or scheduled assignment for vehicle")

    # Get or create vehicle live state
    state = (
        db.query(VehicleLiveState)
        .filter(VehicleLiveState.vehicle_id == assignment.vehicle_id)
        .first()
    )
    if not state:
        state = VehicleLiveState(
            vehicle_id=assignment.vehicle_id,
            route_id=assignment.route_id,
            assignment_id=assignment.assignment_id,
            driver_id=assignment.driver_id,
            trip_id=assignment.trip_id,
        )
        db.add(state)

    # Get total stops for the trip
    trip = None
    if assignment.trip_id:
        from models.trip import Trip
        trip = db.query(Trip).filter(Trip.trip_id == assignment.trip_id).first()
    if not trip:
        from models.trip import Trip
        trip = db.query(Trip).filter(Trip.route_id == assignment.route_id).first()

    total_stops = 0
    if trip:
        from models.stop_time import StopTime
        total_stops = db.query(StopTime).filter(StopTime.trip_id == trip.trip_id).count()

    current_seq = state.stop_sequence if state.stop_sequence is not None else 1
    next_seq = current_seq + 1

    # Persist the new sequence in the database
    state.stop_sequence = next_seq

    # Set current and next stop IDs if available
    if trip:
        from models.stop_time import StopTime
        stop_times = (
            db.query(StopTime)
            .filter(StopTime.trip_id == trip.trip_id)
            .order_by(StopTime.stop_sequence)
            .all()
        )
        current_stop_id = None
        next_stop_id = None
        for st in stop_times:
            if st.stop_sequence == next_seq:
                current_stop_id = st.stop_id
            elif st.stop_sequence == next_seq + 1:
                next_stop_id = st.stop_id
        if current_stop_id:
            state.current_stop_id = current_stop_id
        if next_stop_id:
            state.next_stop_id = next_stop_id

    db.commit()
    db.refresh(state)

    return get_driver_route_info(
        vehicle_id=vehicle_id,
        route_id=route_id,
        assignment_id=assignment_id,
        driver_id=driver_id,
        db=db,
    )


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
        route_name = None
        if v.route_id:
            operational_route = db.query(OperationalRoute).filter(
                OperationalRoute.route_id == v.route_id
            ).first()
            gtfs_route = db.query(Route).filter(Route.route_id == v.route_id).first()
            route_name = (
                (operational_route.route_long_name or operational_route.route_short_name)
                if operational_route else None
            ) or (gtfs_route.route_name if gtfs_route else None) or v.route_id
        result.append({
            "vehicle_id": v.vehicle_id,
            "route_id": v.route_id,
            "route_name": route_name,
            "route_label": route_name,
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
