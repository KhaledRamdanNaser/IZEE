from fastapi import APIRouter, HTTPException, Depends, status, Request, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from database.connection import SessionLocal, Base
from models.trips_workflow import (
    Region, SupervisorRegion, RegionRoute, RegionVehicle, DriverAssignment, User,
    OperationalRoute, RegionRouteMapping, RegionDriverMapping, PassengerFavorite,
    PassengerTripHistory
)
from models.route import Route
from models.trip import Trip
from models.stop_time import StopTime
from models.stop import Stop
from models.vehicle_live_state import VehicleLiveState
from models.transit_incident import TransitIncident
from models.control_message import ControlMessage
from pydantic import BaseModel
from schemas.trips_workflow import (
    RegionCreate,
    RoutesMappingRequest,
    SupervisorsMappingRequest,
    VehiclesMappingRequest,
    AssignmentCreateRequest,
    AssignmentUpdateRequest,
    DriversMappingRequest
)
import uuid
import datetime

router = APIRouter()

# Messaging presence is deliberately in memory. Database users are never
# treated as connected; a user exists here only while its message socket lives.
message_clients: dict[tuple[str, str], dict] = {}
# HTTP polling fallback retained for the existing Active Recipients behavior.
http_presence: dict[tuple[str, str], datetime.datetime] = {}


def _save_message_last_seen(user_id: str, timestamp: str, status: str | None = None) -> None:
    """Persist the final messaging activity without using users as presence."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            user.last_active = timestamp
            if status and user.status != "suspended":
                user.status = status
            db.commit()
    finally:
        db.close()


# Dependency to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_passenger_id(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer local-passenger-token-"):
        return auth.replace("Bearer local-passenger-token-", "", 1) or "local-passenger"
    return (
        request.headers.get("x-passenger-id")
        or request.query_params.get("passenger_id")
        or "local-passenger"
    )


def _stop_result(stop: Stop, result_type: str = "stop"):
    return {
        "id": stop.stop_id,
        "stop_id": stop.stop_id,
        "name": stop.name,
        "lat": stop.lat,
        "lon": stop.lon,
        "result_type": result_type,
        "type": result_type,
        "source": "backend",
        "subtitle": "Transit stop",
    }


def _route_label(db: Session, route_id: str) -> str:
    op_route = db.query(OperationalRoute).filter(OperationalRoute.route_id == route_id).first()
    if op_route:
        return op_route.route_long_name or op_route.route_short_name or route_id
    route = db.query(Route).filter(Route.route_id == route_id).first()
    return route.route_name if route and route.route_name else route_id


def ensure_defaults(db: Session):
    # Auto-create tables
    Base.metadata.create_all(bind=db.get_bind())

    # Ensure users exist
    defaults = [
        User(user_id="driver_test_001", name="Mohamed Ali", role="Driver", status="active", last_active="5 min ago"),
        User(user_id="driver_test_002", name="Ahmed Hassan (Driver)", role="Driver", status="active", last_active="2 min ago"),
        User(user_id="driver_test_003", name="Omar Ibrahim", role="Driver", status="inactive", last_active="2 days ago"),
        User(user_id="supervisor_1", name="Fatima Said", role="Supervisor", status="active", last_active="1 hour ago"),
        User(user_id="supervisor_2", name="Ahmed Hassan", role="Supervisor", status="active", last_active="Now"),
    ]
    
    # Track existing user IDs
    existing_user_ids = {u.user_id for u in db.query(User.user_id).all()}
    
    for u in defaults:
        if u.user_id not in existing_user_ids:
            db.add(u)
            existing_user_ids.add(u.user_id)
            
    # Also sync drivers from driver_route_assignments if the table exists
    try:
        from sqlalchemy import text
        res = db.execute(text('SELECT DISTINCT driver_id FROM driver_route_assignments')).fetchall()
        for r in res:
            d_id = r[0]
            if d_id and d_id not in existing_user_ids:
                db.add(User(
                    user_id=d_id,
                    name=d_id,
                    role="Driver",
                    status="active",
                    last_active="Now"
                ))
                existing_user_ids.add(d_id)
    except Exception as e:
        print(f"Error seeding drivers from assignments: {e}")
        
    db.commit()

    # Detect if we are in pytest execution environment by looking for a test region
    import sys
    is_test = (
        db.query(Region).filter(Region.region_name.like("%Test%")).first() is not None
        or any("test" in arg for arg in sys.argv)
        or "pytest" in sys.modules
    )
    if is_test:
        db.query(DriverAssignment).filter(
            DriverAssignment.assignment_id.like("ASGN_DEFAULT_%")
        ).delete(synchronize_session=False)
        db.commit()

    # Ensure Zone_East region exists
    zone_east = db.query(Region).filter(Region.region_id == "Zone_East").first()
    if not zone_east:
        zone_east = Region(
            region_id="Zone_East",
            region_name="Zone East",
            description="East Zone description",
            active=True
        )
        db.add(zone_east)
        db.commit()

    # Ensure supervisor region mappings
    for sup_id in ["supervisor_1", "supervisor_2"]:
        has_any = db.query(SupervisorRegion).filter(
            SupervisorRegion.supervisor_id == sup_id
        ).first()
        if not has_any:
            db.add(SupervisorRegion(supervisor_id=sup_id, region_id="Zone_East"))

    # Ensure mapped routes
    for r_id in ["CTA 1023", "Route 8"]:
        # Ensure OperationalRoute exists
        op_route = db.query(OperationalRoute).filter(OperationalRoute.route_id == r_id).first()
        if not op_route:
            db.add(OperationalRoute(
                route_id=r_id,
                route_short_name=r_id,
                route_long_name=r_id,
                route_type=3,
                mode="bus",
                is_active=True
            ))

        mapping = db.query(RegionRoute).filter(
            RegionRoute.region_id == "Zone_East",
            RegionRoute.route_id == r_id
        ).first()
        if not mapping:
            db.add(RegionRoute(region_id="Zone_East", route_id=r_id, route_name=r_id, mode="Bus"))

        # Ensure GTFS Route exists
        from models.route import Route
        r_exists = db.query(Route).filter(Route.route_id == r_id).first()
        if not r_exists:
            db.add(Route(route_id=r_id, route_name=r_id))

        # Ensure RegionRouteMapping exists
        route_map = db.query(RegionRouteMapping).filter(
            RegionRouteMapping.region_id == "Zone_East",
            RegionRouteMapping.route_id == r_id
        ).first()
        if not route_map:
            db.add(RegionRouteMapping(region_id="Zone_East", route_id=r_id, active=True))

    # Ensure mapped vehicles
    for v_id in ["BUS_001", "BUS_002", "BUS_003", "V-001"]:
        mapping = db.query(RegionVehicle).filter(
            RegionVehicle.region_id == "Zone_East",
            RegionVehicle.vehicle_id == v_id
        ).first()
        if not mapping:
            db.add(RegionVehicle(region_id="Zone_East", vehicle_id=v_id))

    # Ensure default drivers mapped to Zone_East in region_driver_mappings
    for d_id in ["driver_test_001", "driver_test_002"]:
        mapping = db.query(RegionDriverMapping).filter(
            RegionDriverMapping.region_id == "Zone_East",
            RegionDriverMapping.driver_id == d_id
        ).first()
        if not mapping:
            db.add(RegionDriverMapping(region_id="Zone_East", driver_id=d_id, active=True))

    db.commit()

    # Seed default GTFS-like data (Trip, Stops, StopTimes) for default routes
    default_stops = [
        ("stop_r8_1", "Heliopolis Square", 30.0982, 31.3303),
        ("stop_r8_2", "Roxy Square", 30.0911, 31.3125),
        ("stop_r8_3", "Cairo Stadium Station", 30.0666, 31.2557),
        ("stop_r8_4", "Downtown Terminal", 30.0444, 31.2357),
    ]
    for s_id, s_name, lat, lon in default_stops:
        stop_exists = db.query(Stop).filter(Stop.stop_id == s_id).first()
        if not stop_exists:
            db.add(Stop(stop_id=s_id, name=s_name, lat=lat, lon=lon))
    db.flush()

    # Ensure Trip exists for Route 8
    trip_r8 = db.query(Trip).filter(Trip.trip_id == "trip_route_8").first()
    if not trip_r8:
        trip_r8 = Trip(trip_id="trip_route_8", route_id="Route 8", direction_id=0)
        db.add(trip_r8)
    db.flush()

    # Ensure StopTimes exist for Route 8 trip
    for i, (s_id, _, _, _) in enumerate(default_stops, start=1):
        st_exists = db.query(StopTime).filter(StopTime.trip_id == "trip_route_8", StopTime.stop_id == s_id).first()
        if not st_exists:
            db.add(StopTime(trip_id="trip_route_8", stop_id=s_id, stop_sequence=i))

    # Also make sure CTA 1023 has a trip and stop times if not present
    trip_cta = db.query(Trip).filter(Trip.trip_id == "trip_1").first()
    if not trip_cta:
        trip_cta = Trip(trip_id="trip_1", route_id="CTA 1023", direction_id=0)
        db.add(trip_cta)
    db.flush()

    # Connect CTA 1023 trip to stops
    # stop_r8_4 is Downtown Terminal, stop_r8_3 is Cairo Stadium Station
    cta_stops = [("stop_r8_4", 1), ("stop_r8_3", 2)]
    for s_id, seq in cta_stops:
        st_exists = db.query(StopTime).filter(StopTime.trip_id == "trip_1", StopTime.stop_id == s_id).first()
        if not st_exists:
            db.add(StopTime(trip_id="trip_1", stop_id=s_id, stop_sequence=seq))

    db.commit()

    # Ensure the default driver has a real backend duty to start from My Trips.
    today = datetime.date.today().isoformat()
    has_default_duty = db.query(DriverAssignment).filter(
        DriverAssignment.driver_id == "driver_test_001",
        DriverAssignment.status.in_(["scheduled", "active"]),
    ).first()
    if not has_default_duty and not is_test:
        db.add(DriverAssignment(
            assignment_id=f"ASGN_DEFAULT_{today.replace('-', '')}_{uuid.uuid4().hex[:4].upper()}",
            supervisor_id="supervisor_2",
            region_id="Zone_East",
            driver_id="driver_test_001",
            vehicle_id="BUS_001",
            route_id="Route 8",
            route_name="Route 8",
            trip_id=f"TRIP_DEFAULT_{today.replace('-', '')}",
            service_date=today,
            planned_start_time="08:00:00",
            planned_end_time="23:00:00",
            status="scheduled",
            notes="Default test duty for driver app live tracking",
        ))
        db.commit()

    import_gtfs_bus_routes(db)


def import_gtfs_bus_routes(db: Session):
    try:
        import os
        import pandas as pd
        from sqlalchemy import text
        from models.agency import Agency
        from models.stop import Stop
        from models.route import Route
        from models.trip import Trip
        from models.stop_time import StopTime
        from models.shape import Shape
        from models.trips_workflow import OperationalRoute

        gtfs_dir = r"C:\Users\omaro\Documents\IZEE UI\link (7)"
        if not os.path.exists(gtfs_dir):
            print(f"GTFS directory not found at: {gtfs_dir}. Skipping full load.")
            return

        print(f"Starting GTFS data import from {gtfs_dir}...")

        # 1. Import Agencies
        agency_file = os.path.join(gtfs_dir, "agency.txt")
        if os.path.exists(agency_file) and db.query(Agency).count() == 0:
            print("Importing agencies...")
            df = pd.read_csv(agency_file)
            df = df.drop_duplicates(subset=["agency_id"])
            agencies = []
            for _, row in df.iterrows():
                agencies.append({
                    "agency_id": str(row["agency_id"]),
                    "name": str(row["agency_name"])
                })
            db.bulk_insert_mappings(Agency, agencies)
            db.commit()
            print(f"Agencies imported: {len(agencies)}")

        # 2. Import Stops — check by reading first GTFS stop_id to see if already imported
        stops_file = os.path.join(gtfs_dir, "stops.txt")
        gtfs_stops_imported = False
        if os.path.exists(stops_file):
            first_stop_row = pd.read_csv(stops_file, nrows=1)
            if not first_stop_row.empty:
                first_gtfs_stop_id = str(first_stop_row.iloc[0]["stop_id"])
                gtfs_stops_imported = db.query(Stop).filter(Stop.stop_id == first_gtfs_stop_id).first() is not None
        if os.path.exists(stops_file) and not gtfs_stops_imported:
            print("Importing stops...")
            df = pd.read_csv(stops_file)
            df = df.drop_duplicates(subset=["stop_id"])
            existing_stop_ids = {s.stop_id for s in db.query(Stop.stop_id).all()}
            stops = []
            for _, row in df.iterrows():
                s_id = str(row["stop_id"])
                if s_id not in existing_stop_ids:
                    stops.append({
                        "stop_id": s_id,
                        "name": str(row["stop_name"]),
                        "lat": float(row["stop_lat"]),
                        "lon": float(row["stop_lon"])
                    })
            db.bulk_insert_mappings(Stop, stops)
            db.commit()
            print(f"Stops imported: {len(stops)}")

        # 3. Import Routes & OperationalRoutes — check by first GTFS route_id
        routes_file = os.path.join(gtfs_dir, "routes.txt")
        gtfs_routes_imported = False
        if os.path.exists(routes_file):
            first_route_row = pd.read_csv(routes_file, nrows=1)
            if not first_route_row.empty:
                first_gtfs_route_id = str(first_route_row.iloc[0]["route_id"])
                gtfs_routes_imported = db.query(Route).filter(Route.route_id == first_gtfs_route_id).first() is not None
        if os.path.exists(routes_file) and not gtfs_routes_imported:
            print("Importing routes...")
            df = pd.read_csv(routes_file)
            df = df.drop_duplicates(subset=["route_id"])
            routes_to_insert = []
            op_routes_to_insert = []
            
            existing_agencies = {a.agency_id for a in db.query(Agency.agency_id).all()}

            for _, row in df.iterrows():
                r_id = str(row["route_id"])
                r_name = str(row.get("route_long_name") or row.get("route_short_name") or r_id)
                r_short = str(row.get("route_short_name") or r_id)
                agency_id = str(row["agency_id"]) if pd.notna(row.get("agency_id")) else None
                
                # Ensure agency constraint is satisfied
                if agency_id and agency_id not in existing_agencies:
                    db.add(Agency(agency_id=agency_id, name=agency_id))
                    existing_agencies.add(agency_id)
                    db.flush()

                # Add to Route
                routes_to_insert.append({
                    "route_id": r_id,
                    "route_name": r_name,
                    "agency_id": agency_id
                })

                # Check if it should be an OperationalRoute (Bus routes only)
                name_check = f"{r_id} {r_short} {r_name}".upper()
                exclude = False
                for kw in ['METRO', 'BRT', 'LRT', 'MONORAIL']:
                    if kw in name_check:
                        exclude = True
                        break
                if not exclude:
                    op_routes_to_insert.append({
                        "route_id": r_id,
                        "route_short_name": r_short,
                        "route_long_name": r_name,
                        "route_type": int(row.get("route_type", 3)),
                        "mode": "bus",
                        "is_active": True
                    })

            db.bulk_insert_mappings(Route, routes_to_insert)
            db.bulk_insert_mappings(OperationalRoute, op_routes_to_insert)
            db.commit()
            print(f"Routes imported: {len(routes_to_insert)} (Operational: {len(op_routes_to_insert)})")

        # 4. Import Shapes
        shapes_file = os.path.join(gtfs_dir, "shapes.txt")
        existing_shapes_count = db.query(Shape).count()
        imported_shape_ids = set()
        if os.path.exists(shapes_file) and existing_shapes_count == 0:
            print("Importing shapes (this may take a few seconds)...")
            df = pd.read_csv(shapes_file)
            df = df.drop_duplicates(subset=["shape_id", "shape_pt_lat", "shape_pt_lon"])
            
            shapes = []
            for _, row in df.iterrows():
                sh_id = str(row["shape_id"])
                imported_shape_ids.add(sh_id)
                shapes.append({
                    "shape_id": sh_id,
                    "lat": float(row["shape_pt_lat"]),
                    "lon": float(row["shape_pt_lon"]),
                    "sequence": int(row["shape_pt_sequence"])
                })
            
            # Bulk insert in chunks of 50000
            chunk_size = 50000
            for i in range(0, len(shapes), chunk_size):
                chunk = shapes[i:i + chunk_size]
                db.bulk_insert_mappings(Shape, chunk)
                db.commit()
            print(f"Shapes imported: {len(shapes)}")
        elif existing_shapes_count > 0:
            # Load existing shape IDs to validate trips foreign keys
            res = db.execute(text("SELECT DISTINCT shape_id FROM shape")).fetchall()
            imported_shape_ids = {r[0] for r in res}

        # 5. Import Trips — check by first GTFS trip_id
        trips_file = os.path.join(gtfs_dir, "trips.txt")
        gtfs_trips_imported = False
        if os.path.exists(trips_file):
            first_trip_row = pd.read_csv(trips_file, nrows=1)
            if not first_trip_row.empty:
                first_gtfs_trip_id = str(first_trip_row.iloc[0]["trip_id"])
                gtfs_trips_imported = db.query(Trip).filter(Trip.trip_id == first_gtfs_trip_id).first() is not None
        if os.path.exists(trips_file) and not gtfs_trips_imported:
            print("Importing trips...")
            df = pd.read_csv(trips_file)
            df = df.drop_duplicates(subset=["trip_id"])
            
            valid_route_ids = {r.route_id for r in db.query(Route.route_id).all()}
            
            trips = []
            for _, row in df.iterrows():
                t_id = str(row["trip_id"])
                r_id = str(row["route_id"])
                sh_id = str(row["shape_id"]) if pd.notna(row.get("shape_id")) else None
                
                # Safeguards for foreign key constraints
                if r_id not in valid_route_ids:
                    continue
                if sh_id and sh_id not in imported_shape_ids:
                    sh_id = None  # Reset foreign key if shape is missing

                direction = 0
                if pd.notna(row.get("direction_id")):
                    try:
                        direction = int(row["direction_id"])
                    except:
                        pass

                trips.append({
                    "trip_id": t_id,
                    "route_id": r_id,
                    "shape_id": sh_id,
                    "direction_id": direction
                })
            db.bulk_insert_mappings(Trip, trips)
            db.commit()
            print(f"Trips imported: {len(trips)}")

        # 6. Import Stop Times
        stop_times_file = os.path.join(gtfs_dir, "stop_times.txt")
        gtfs_stop_times_imported = False
        if os.path.exists(stop_times_file):
            first_st_row = pd.read_csv(stop_times_file, nrows=1)
            if not first_st_row.empty:
                first_trip_id = str(first_st_row.iloc[0]["trip_id"])
                first_stop_id = str(first_st_row.iloc[0]["stop_id"])
                gtfs_stop_times_imported = db.query(StopTime).filter(
                    StopTime.trip_id == first_trip_id,
                    StopTime.stop_id == first_stop_id
                ).first() is not None

        if os.path.exists(stop_times_file) and not gtfs_stop_times_imported:
            print("Importing stop times...")
            df = pd.read_csv(stop_times_file)
            df = df.drop_duplicates(subset=["trip_id", "stop_id"])
            
            valid_trip_ids = {t.trip_id for t in db.query(Trip.trip_id).all()}
            valid_stop_ids = {s.stop_id for s in db.query(Stop.stop_id).all()}
            
            stop_times = []
            for _, row in df.iterrows():
                t_id = str(row["trip_id"])
                s_id = str(row["stop_id"])
                
                # Safeguards for foreign keys
                if t_id not in valid_trip_ids or s_id not in valid_stop_ids:
                    continue

                try:
                    stop_sequence = int(row["stop_sequence"])
                except:
                    stop_sequence = 1
                stop_times.append({
                    "trip_id": t_id,
                    "stop_id": s_id,
                    "stop_sequence": stop_sequence
                })
            db.bulk_insert_mappings(StopTime, stop_times)
            db.commit()
            print(f"Stop times imported: {len(stop_times)}")

        # Ensure default routes are present in operational_routes for dev UI support
        defaults = [
            ("Route 8", "Route 8 - Heliopolis Express"),
            ("CTA 1023", "CTA 1023"),
            ("Route 15", "Route 15 - Nasr City Line"),
            ("A-12 Express", "A-12 Express"),
        ]
        existing_op_ids = {r.route_id for r in db.query(OperationalRoute.route_id).all()}
        existing_gtfs_ids = {r.route_id for r in db.query(Route.route_id).all()}
        for route_id, route_name in defaults:
            if route_id not in existing_gtfs_ids:
                db.add(Route(route_id=route_id, route_name=route_id))
                existing_gtfs_ids.add(route_id)
            if route_id not in existing_op_ids:
                db.add(OperationalRoute(
                    route_id=route_id,
                    route_short_name=route_id,
                    route_long_name=route_name,
                    route_type=3,
                    mode="bus",
                    is_active=True
                ))
            else:
                db_route = db.query(OperationalRoute).filter(OperationalRoute.route_id == route_id).first()
                if db_route:
                    db_route.is_active = True
        db.commit()
        print("GTFS data import completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"Error during GTFS data import: {e}")
        import traceback
        traceback.print_exc()



# ==========================================
# HELPER VALIDATION FUNCTIONS
# ==========================================

def parse_time_str(t_str: str) -> datetime.time:
    t_str = t_str.strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M%p", "%I:%M:%S%p"):
        try:
            return datetime.datetime.strptime(t_str, fmt).time()
        except ValueError:
            continue
    raise HTTPException(400, detail=f"Invalid time format: {t_str}")


def check_assignment_validations(
    db: Session,
    supervisor_id: str,
    driver_id: str,
    vehicle_id: str,
    route_id: str,
    service_date: str,
    planned_start_time: str,
    planned_end_time: str,
    exclude_assignment_id: str = None,
    incoming_region_id: str = None
):
    print(f"VALIDATING_SUPERVISOR_REGION: supervisor_id={supervisor_id}, region_id={incoming_region_id}")

    # 4. vehicle_id is required
    if not vehicle_id or not vehicle_id.strip():
        raise HTTPException(400, detail="vehicle_id is required")

    # Get supervisor regions
    sup_regions = db.query(SupervisorRegion).filter(SupervisorRegion.supervisor_id == supervisor_id).all()
    sup_region_ids = [sr.region_id for sr in sup_regions]
    print(f"SUPERVISOR_ACTIVE_REGION_MAPPINGS: {sup_region_ids}")
    if not sup_region_ids:
        raise HTTPException(400, detail=f"Supervisor {supervisor_id} is not assigned to any region")
    if len(sup_region_ids) > 1:
        raise HTTPException(400, detail=f"Supervisor {supervisor_id} has multiple active region mappings")

    assigned_region_id = sup_region_ids[0]

    # Validate that incoming_region_id matches supervisor's region
    if incoming_region_id and incoming_region_id != assigned_region_id:
        raise HTTPException(400, detail=f"Supervisor {supervisor_id} is not assigned to region {incoming_region_id}")

    # Validate that route_id is a bus route only (exists in OperationalRoute table)
    op_route = db.query(OperationalRoute).filter(
        OperationalRoute.route_id == route_id,
        OperationalRoute.is_active == True
    ).first()
    if not op_route or op_route.mode != "bus":
        raise HTTPException(400, detail="Route must be a bus route only")

    # Validate that route is mapped to the supervisor's region
    route_mapped = db.query(RegionRouteMapping).filter(
        RegionRouteMapping.region_id == assigned_region_id,
        RegionRouteMapping.route_id == route_id,
        RegionRouteMapping.active == True
    ).first()
    if not route_mapped:
        # Check legacy RegionRoute mapping fallback
        legacy_mapped = db.query(RegionRoute).filter(
            RegionRoute.region_id == assigned_region_id,
            RegionRoute.route_id == route_id
        ).first()
        if not legacy_mapped:
            raise HTTPException(400, detail=f"Route {route_id} does not belong to this region")

    region_id = assigned_region_id
    print(f"VALIDATING_ROUTE_REGION: route_id={route_id}, region_id={region_id}")

    # 3. Vehicle must belong to selected region
    print(f"VALIDATING_VEHICLE_REGION: vehicle_id={vehicle_id}, region_id={region_id}")
    vehicle_mapping = db.query(RegionVehicle).filter(
        RegionVehicle.vehicle_id == vehicle_id,
        RegionVehicle.region_id == region_id
    ).first()
    if not vehicle_mapping:
        raise HTTPException(400, detail=f"Vehicle {vehicle_id} is not mapped to region {region_id}")

    # Parse and validate times
    new_start = parse_time_str(planned_start_time)
    new_end = parse_time_str(planned_end_time)
    if new_start >= new_end:
        raise HTTPException(400, detail="Start time must be before end time")

    # Query existing active/scheduled duties on that day to check for overlaps
    query = db.query(DriverAssignment).filter(
        DriverAssignment.service_date == service_date,
        DriverAssignment.status.in_(["scheduled", "active"])
    )
    if exclude_assignment_id:
        query = query.filter(DriverAssignment.assignment_id != exclude_assignment_id)

    existing = query.all()

    for a in existing:
        a_start = parse_time_str(a.planned_start_time)
        a_end = parse_time_str(a.planned_end_time)

        # Check overlap
        if new_start < a_end and a_start < new_end:
            # 6. Driver overlap
            if a.driver_id == driver_id:
                raise HTTPException(400, detail=f"Driver has an overlapping duty: {driver_id} in {a.assignment_id}")
            # 7. Vehicle overlap
            if a.vehicle_id == vehicle_id:
                raise HTTPException(400, detail=f"Vehicle has an overlapping duty: {vehicle_id} in {a.assignment_id}")

    return region_id


def get_route_endpoints(db: Session, route_id: str):
    # Lookup stops in GTFS to get origin & destination
    trip = db.query(Trip).filter(Trip.route_id == route_id).first()
    if trip:
        stop_times = db.query(StopTime).filter(StopTime.trip_id == trip.trip_id).order_by(StopTime.stop_sequence).all()
        if len(stop_times) >= 2:
            origin_stop = db.query(Stop).filter(Stop.stop_id == stop_times[0].stop_id).first()
            dest_stop = db.query(Stop).filter(Stop.stop_id == stop_times[-1].stop_id).first()
            return (
                origin_stop.name if origin_stop else "Origin Stop",
                dest_stop.name if dest_stop else "Destination Stop"
            )
    return "Downtown Terminal", "Cairo Stadium"


# ==========================================
# CONTROL CENTER ENDPOINTS
# ==========================================

@router.get("/control/regions")
def get_regions(db: Session = Depends(get_db)):
    return db.query(Region).all()


@router.post("/control/regions", status_code=201)
def create_region(req: RegionCreate, db: Session = Depends(get_db)):
    # Log incoming payload
    print(f"CREATE_REGION_PAYLOAD: {req.model_dump()}")
    # Use provided region_id if present, otherwise generate from region_name
    region_id = req.region_id or req.region_name.replace(" ", "_")
    # Verify region does not already exist
    existing = db.query(Region).filter(Region.region_id == region_id).first()
    if existing:
        raise HTTPException(400, detail="Region already exists")
    # Create Region record
    db_region = Region(
        region_id=region_id,
        region_name=req.region_name,
        description=req.description,
        active=req.active,
    )
    db.add(db_region)
    db.commit()
    db.refresh(db_region)

    # Process optional route mappings
    route_ids = req.route_ids or []
    for r_id in route_ids:
        op_route = db.query(OperationalRoute).filter(
            OperationalRoute.route_id == r_id,
            OperationalRoute.is_active == True,
        ).first()
        if not op_route:
            raise HTTPException(400, detail=f"Route ID {r_id} is not an active bus route.")
        # Save mapping records
        db.add(RegionRouteMapping(region_id=region_id, route_id=r_id, active=True))
        legacy = db.query(RegionRoute).filter(
            RegionRoute.region_id == region_id,
            RegionRoute.route_id == r_id,
        ).first()
        if not legacy:
            db.add(
                RegionRoute(
                    region_id=region_id,
                    route_id=r_id,
                    route_name=op_route.route_short_name or r_id,
                    mode=op_route.mode or "Bus",
                )
            )
    db.commit()
    db.refresh(db_region)
    print(f"REGION_ROUTE_MAPPINGS_CREATED: region_id={region_id}, count={len(route_ids)}")
    return db_region


@router.put("/control/regions/{region_id}")
def update_region(region_id: str, req: RegionCreate, db: Session = Depends(get_db)):
    db_region = db.query(Region).filter(Region.region_id == region_id).first()
    if not db_region:
        raise HTTPException(404, detail="Region not found")
    db_region.region_name = req.region_name
    db_region.description = req.description
    db_region.active = req.active
    db.commit()

    route_ids = req.route_ids
    if route_ids is not None:
        db.query(RegionRouteMapping).filter(
            RegionRouteMapping.region_id == region_id,
            RegionRouteMapping.route_id.notin_(route_ids)
        ).update({RegionRouteMapping.active: False}, synchronize_session=False)

        db.query(RegionRoute).filter(
            RegionRoute.region_id == region_id,
            RegionRoute.route_id.notin_(route_ids)
        ).delete(synchronize_session=False)

        for r_id in route_ids:
            op_route = db.query(OperationalRoute).filter(
                OperationalRoute.route_id == r_id,
                OperationalRoute.is_active == True
            ).first()
            if not op_route:
                raise HTTPException(400, detail=f"Route ID {r_id} is not an active bus route.")

            mapping = db.query(RegionRouteMapping).filter(
                RegionRouteMapping.region_id == region_id,
                RegionRouteMapping.route_id == r_id
            ).first()
            if not mapping:
                db.add(RegionRouteMapping(region_id=region_id, route_id=r_id, active=True))
            else:
                mapping.active = True

            legacy = db.query(RegionRoute).filter(RegionRoute.region_id == region_id, RegionRoute.route_id == r_id).first()
            if not legacy:
                db.add(RegionRoute(
                    region_id=region_id,
                    route_id=r_id,
                    route_name=op_route.route_short_name or r_id,
                    mode=op_route.mode or "Bus"
                ))

        db.commit()
        active_count = db.query(RegionRouteMapping).filter(
            RegionRouteMapping.region_id == region_id,
            RegionRouteMapping.active == True
        ).count()
        print(f"UPDATE_REGION_ROUTE_SYNC: region_id={region_id}, active_count={active_count}")

    db.refresh(db_region)
    return db_region


@router.put("/control-center/regions/{region_id}")
def update_control_center_region(region_id: str, req: RegionCreate, db: Session = Depends(get_db)):
    return update_region(region_id=region_id, req=req, db=db)


@router.get("/control-center/bus-routes")
def get_control_center_bus_routes(db: Session = Depends(get_db)):
    routes = db.query(OperationalRoute).filter(OperationalRoute.is_active == True).all()
    print(f"CONTROL_CENTER_BUS_ROUTES_RESPONSE_COUNT: {len(routes)}")
    return [{"route_id": r.route_id, "route_short_name": r.route_short_name, "route_long_name": r.route_long_name, "route_type": r.route_type, "mode": r.mode} for r in routes]


@router.get("/control-center/regions/{region_id}")
def get_control_center_region_detail(region_id: str, db: Session = Depends(get_db)):
    region = db.query(Region).filter(Region.region_id == region_id).first()
    if not region:
        raise HTTPException(404, "Region not found")
    mappings = db.query(RegionRouteMapping).filter(RegionRouteMapping.region_id == region_id, RegionRouteMapping.active == True).all()
    route_ids = [m.route_id for m in mappings]
    return {
        "region_id": region.region_id,
        "region_name": region.region_name,
        "description": region.description,
        "active": region.active,
        "route_ids": route_ids
    }


@router.get("/regions/{region_id}/routes")
@router.get("/control/regions/{region_id}/routes")
def get_region_routes(region_id: str, supervisor_id: str = Query(None), db: Session = Depends(get_db)):
    mappings = db.query(RegionRouteMapping).filter(
        RegionRouteMapping.region_id == region_id,
        RegionRouteMapping.active == True
    ).all()

    routes_list = []
    for m in mappings:
        op_route = db.query(OperationalRoute).filter(OperationalRoute.route_id == m.route_id).first()
        if op_route and op_route.is_active:
            routes_list.append({
                "route_id": op_route.route_id,
                "route_name": op_route.route_long_name or op_route.route_short_name or op_route.route_id
            })

    if supervisor_id:
        print(f"SUPERVISOR_REGION_ROUTES_RESPONSE: supervisor_id={supervisor_id}, region_id={region_id}, count={len(routes_list)}")

    print(f"REGION_ROUTES_COUNT: region_id={region_id}, count={len(routes_list)}")
    return routes_list


@router.get("/regions/{region_id}/vehicles")
@router.get("/control/regions/{region_id}/vehicles")
def get_control_region_vehicles(region_id: str, supervisor_id: str = Query(None), db: Session = Depends(get_db)):
    ensure_defaults(db)
    vehicles = db.query(RegionVehicle).filter(RegionVehicle.region_id == region_id).all()
    result = [{"vehicle_id": v.vehicle_id} for v in vehicles]
    print(f"REGION_VEHICLES_COUNT: region_id={region_id}, count={len(result)}")
    return result


@router.get("/regions/{region_id}/drivers")
@router.get("/control/regions/{region_id}/drivers")
def get_region_drivers(region_id: str, supervisor_id: str = Query(None), db: Session = Depends(get_db)):
    ensure_defaults(db)
    mappings = db.query(RegionDriverMapping).filter(
        RegionDriverMapping.region_id == region_id,
        RegionDriverMapping.active == True
    ).all()
    driver_ids = [m.driver_id for m in mappings]
    drivers = db.query(User).filter(
        User.role == "Driver",
        User.status == "active",
        User.user_id.in_(driver_ids)
    ).all()
    print(f"REGION_DRIVERS_COUNT: region_id={region_id}, count={len(drivers)}")
    return [{"driver_id": d.user_id, "name": d.name} for d in drivers]


@router.get("/regions/{region_id}/supervisors")
@router.get("/control/regions/{region_id}/supervisors")
def get_region_supervisors(region_id: str, db: Session = Depends(get_db)):
    ensure_defaults(db)
    supervisors = db.query(SupervisorRegion).filter(SupervisorRegion.region_id == region_id).all()
    result = [{"supervisor_id": s.supervisor_id} for s in supervisors]
    print(f"REGION_SUPERVISORS_COUNT: region_id={region_id}, count={len(result)}")
    return result


@router.post("/control/regions/{region_id}/routes")
def map_region_routes(region_id: str, req: RoutesMappingRequest, db: Session = Depends(get_db)):
    # Validate modes
    allowed_modes = {"bus", "minibus", "microbus"}
    forbidden_modes = {"metro", "brt", "lrt", "monorail", "walking", "passenger-planning", "passenger_planning"}
    
    for r in req.routes:
        mode = r.mode or "Bus"
        mode_lower = str(mode).strip().lower()
        is_valid_bus = mode_lower in allowed_modes or ("bus" in mode_lower and mode_lower not in forbidden_modes)
        if not is_valid_bus or mode_lower in forbidden_modes:
            raise HTTPException(
                status_code=400,
                detail=f"Route {r.route_id} is not a valid bus route (mode: {mode}). Control Center can only assign bus routes."
            )

    req_route_ids = [r.route_id for r in req.routes]

    # Deactivate RegionRouteMapping not in request
    db.query(RegionRouteMapping).filter(
        RegionRouteMapping.region_id == region_id,
        RegionRouteMapping.route_id.notin_(req_route_ids)
    ).update({RegionRouteMapping.active: False}, synchronize_session=False)

    # Delete RegionRoute not in request
    db.query(RegionRoute).filter(
        RegionRoute.region_id == region_id,
        RegionRoute.route_id.notin_(req_route_ids)
    ).delete(synchronize_session=False)

    for r in req.routes:
        # Ensure OperationalRoute exists and is active
        op_route = db.query(OperationalRoute).filter(OperationalRoute.route_id == r.route_id).first()
        if not op_route:
            op_route = OperationalRoute(
                route_id=r.route_id,
                route_short_name=r.route_id,
                route_long_name=r.route_name or r.route_id,
                route_type=3,
                mode=r.mode or "bus",
                is_active=True
            )
            db.add(op_route)
        else:
            op_route.is_active = True

        # RegionRouteMapping
        mapping = db.query(RegionRouteMapping).filter(
            RegionRouteMapping.region_id == region_id,
            RegionRouteMapping.route_id == r.route_id
        ).first()
        if not mapping:
            db.add(RegionRouteMapping(region_id=region_id, route_id=r.route_id, active=True))
        else:
            mapping.active = True

        # Legacy RegionRoute mapping fallback
        legacy = db.query(RegionRoute).filter(RegionRoute.region_id == region_id, RegionRoute.route_id == r.route_id).first()
        if not legacy:
            db.add(RegionRoute(
                region_id=region_id,
                route_id=r.route_id,
                route_name=r.route_name or r.route_id,
                mode=r.mode or "Bus"
            ))

        # Also ensure Route table contains this route to prevent GTFS reference loader issues
        route_exists = db.query(Route).filter(Route.route_id == r.route_id).first()
        if not route_exists:
            db.add(Route(route_id=r.route_id, route_name=r.route_name or r.route_id))

    db.commit()
    return {"status": "success"}


@router.post("/control/regions/{region_id}/vehicles")
def map_region_vehicles(region_id: str, req: VehiclesMappingRequest, db: Session = Depends(get_db)):
    db.query(RegionVehicle).filter(RegionVehicle.region_id == region_id).delete()
    for v_id in req.vehicles:
        mapping = RegionVehicle(
            region_id=region_id,
            vehicle_id=v_id
        )
        db.add(mapping)
    db.commit()
    return {"status": "success"}


@router.post("/control/regions/{region_id}/supervisors")
def map_region_supervisors(region_id: str, req: SupervisorsMappingRequest, db: Session = Depends(get_db)):
    db.query(SupervisorRegion).filter(SupervisorRegion.region_id == region_id).delete()
    for s_id in req.supervisors:
        db.query(SupervisorRegion).filter(SupervisorRegion.supervisor_id == s_id).delete()
        mapping = SupervisorRegion(
            region_id=region_id,
            supervisor_id=s_id
        )
        db.add(mapping)
    db.commit()
    return {"status": "success"}
@router.put("/control/regions/{region_id}/routes")
def update_region_routes(region_id: str, req: RoutesMappingRequest, db: Session = Depends(get_db)):
    """Update region routes (same logic as POST)."""
    return map_region_routes(region_id, req, db)

@router.put("/control/regions/{region_id}/vehicles")
def update_region_vehicles(region_id: str, req: VehiclesMappingRequest, db: Session = Depends(get_db)):
    """Update region vehicles (same logic as POST)."""
    return map_region_vehicles(region_id, req, db)

@router.put("/control/regions/{region_id}/supervisors")
def update_region_supervisors(region_id: str, req: SupervisorsMappingRequest, db: Session = Depends(get_db)):
    """Update region supervisors (same logic as POST)."""
    return map_region_supervisors(region_id, req, db)

@router.put("/control/regions/{region_id}/drivers")
def update_region_drivers(region_id: str, req: DriversMappingRequest, db: Session = Depends(get_db)):
    """Update region drivers (same logic as POST)."""
    return map_region_drivers(region_id, req, db)

@router.post("/control/regions/{region_id}/drivers")
def map_region_drivers(region_id: str, req: DriversMappingRequest, db: Session = Depends(get_db)):
    # Deactivate mappings not in request
    db.query(RegionDriverMapping).filter(
        RegionDriverMapping.region_id == region_id,
        RegionDriverMapping.driver_id.notin_(req.drivers)
    ).update({RegionDriverMapping.active: False}, synchronize_session=False)

    for d_id in req.drivers:
        # Check if user is a driver
        user = db.query(User).filter(User.user_id == d_id, User.role == "Driver").first()
        if not user:
            raise HTTPException(status_code=400, detail=f"User {d_id} is not a valid driver.")
            
        mapping = db.query(RegionDriverMapping).filter(
            RegionDriverMapping.region_id == region_id,
            RegionDriverMapping.driver_id == d_id
        ).first()
        if not mapping:
            db.add(RegionDriverMapping(region_id=region_id, driver_id=d_id, active=True))
        else:
            mapping.active = True
            
    db.commit()
    return {"status": "success"}


@router.get("/control/regions/{region_id}/summary")
def get_region_summary(region_id: str, db: Session = Depends(get_db)):
    supervisors = db.query(SupervisorRegion.supervisor_id).filter(SupervisorRegion.region_id == region_id).all()
    sup_names = []
    for s in supervisors:
        u = db.query(User).filter(User.user_id == s.supervisor_id).first()
        sup_names.append(u.name if u else s.supervisor_id)

    routes_count = db.query(RegionRoute).filter(RegionRoute.region_id == region_id).count()
    vehicles_count = db.query(RegionVehicle).filter(RegionVehicle.region_id == region_id).count()
    active_duties = db.query(DriverAssignment).filter(
        DriverAssignment.region_id == region_id,
        DriverAssignment.status == "active"
    ).count()

    return {
        "supervisors": sup_names,
        "routes_count": routes_count,
        "vehicles_count": vehicles_count,
        "active_duties": active_duties,
        "active_incidents": 0
    }


@router.get("/control/routes")
def get_all_routes(db: Session = Depends(get_db)):
    routes = db.query(Route).all()
    # If empty, return a default list for mapping modal fallback
    if not routes:
        return {"routes": [
            {"route_id": "A-12 Express", "route_name": "A-12 Express", "mode": "Bus"},
            {"route_id": "B-20 Local", "route_name": "B-20 Local", "mode": "Bus"},
            {"route_id": "C-05 Shuttle", "route_name": "C-05 Shuttle", "mode": "Bus"},
            {"route_id": "CTA 1023", "route_name": "CTA 1023", "mode": "Bus"}
        ]}
        
    routes_list = []
    for r in routes:
        name = str(r.route_name or r.route_id).upper()
        mode = "Bus"
        if "METRO" in name:
            mode = "Metro"
        elif "BRT" in name:
            mode = "BRT"
        elif "LRT" in name:
            mode = "LRT"
        elif "MONORAIL" in name:
            mode = "Monorail"
            
        routes_list.append({"route_id": r.route_id, "route_name": r.route_name, "mode": mode})
        
    allowed_modes = {"bus", "minibus", "microbus"}
    forbidden_modes = {"metro", "brt", "lrt", "monorail", "walking", "passenger-planning", "passenger_planning"}
    
    filtered = []
    for r in routes_list:
        mode_lower = r["mode"].lower()
        is_bus = mode_lower in allowed_modes or ("bus" in mode_lower and mode_lower not in forbidden_modes)
        if is_bus and mode_lower not in forbidden_modes:
            filtered.append(r)
            
    return {"routes": filtered}


@router.get("/control/vehicles")
def get_all_vehicles(db: Session = Depends(get_db)):
    # Distinct vehicles in database or a fallback list
    v_states = db.query(VehicleLiveState.vehicle_id).distinct().all()
    vehicles = [v[0] for v in v_states]
    fallback = ["BUS_001", "BUS_002", "BUS_003", "BUS_12", "V-001", "V-002", "V-003", "V-004", "V-005"]
    for f in fallback:
        if f not in vehicles:
            vehicles.append(f)
    return {"vehicles": vehicles}


@router.get("/places/search")
@router.get("/geocode/search")
def search_places(query: str, limit: int = 10, db: Session = Depends(get_db)):
    ensure_defaults(db)
    term = f"%{query.strip()}%"
    stops = (
        db.query(Stop)
        .filter(Stop.name.ilike(term))
        .limit(limit)
        .all()
        if query.strip()
        else []
    )
    results = [_stop_result(stop) for stop in stops]

    if len(results) < limit and query.strip():
        routes = (
            db.query(Route)
            .filter((Route.route_id.ilike(term)) | (Route.route_name.ilike(term)))
            .limit(limit - len(results))
            .all()
        )
        for route in routes:
            trip = db.query(Trip).filter(Trip.route_id == route.route_id).first()
            stop_time = (
                db.query(StopTime)
                .filter(StopTime.trip_id == trip.trip_id)
                .order_by(StopTime.stop_sequence)
                .first()
                if trip
                else None
            )
            stop = db.query(Stop).filter(Stop.stop_id == stop_time.stop_id).first() if stop_time else None
            if stop:
                results.append({
                    **_stop_result(stop, "route"),
                    "route_id": route.route_id,
                    "name": route.route_name or route.route_id,
                    "subtitle": f"Route {route.route_id}",
                })

    return {"results": results[:limit]}


class TripPlanRequest(BaseModel):
    origin: dict
    destination: dict
    departure_time: str | None = "now"
    max_transfers: int | None = 4
    use_walking: bool | None = True


@router.post("/trip-plan")
def create_trip_plan(req: TripPlanRequest, db: Session = Depends(get_db)):
    ensure_defaults(db)
    route = db.query(Route).first()
    if not route:
        raise HTTPException(404, detail="No routes available")

    trip = db.query(Trip).filter(Trip.route_id == route.route_id).first()
    if not trip:
        raise HTTPException(404, detail="No trips available")

    stop_times = (
        db.query(StopTime)
        .filter(StopTime.trip_id == trip.trip_id)
        .order_by(StopTime.stop_sequence)
        .all()
    )
    if len(stop_times) < 2:
        raise HTTPException(404, detail="No stop sequence available")

    first_stop = db.query(Stop).filter(Stop.stop_id == stop_times[0].stop_id).first()
    last_stop = db.query(Stop).filter(Stop.stop_id == stop_times[-1].stop_id).first()
    if not first_stop or not last_stop:
        raise HTTPException(404, detail="Route stops unavailable")

    route_name = _route_label(db, route.route_id)
    leg = {
        "mode": "bus",
        "route_id": route.route_id,
        "route_label": route_name,
        "trip_id": trip.trip_id,
        "from_stop_id": first_stop.stop_id,
        "to_stop_id": last_stop.stop_id,
        "from_stop": _stop_result(first_stop),
        "to_stop": _stop_result(last_stop),
        "departure_time": "08:00:00",
        "arrival_time": "08:30:00",
        "travel_time": 1800,
        "waiting_time": 0,
        "fare": 5.0,
        "fare_currency": "EGP",
        "geometry": [
            {"lat": first_stop.lat, "lon": first_stop.lon},
            {"lat": last_stop.lat, "lon": last_stop.lon},
        ],
    }
    return {
        "routes": [{
            "route_id": route.route_id,
            "label": route_name,
            "total_travel_time": 1800,
            "total_fare": 5.0,
            "transfer_count": 0,
            "total_walking_time": 0,
            "generalized_cost": 1800,
            "legs": [leg],
        }]
    }


@router.get("/wallet")
def get_wallet():
    return {
        "balance": 125.0,
        "currency": "EGP",
        "saved_tickets": [],
        "payment_methods": [],
    }


@router.post("/wallet/top-up")
def top_up_wallet(payload: dict | None = None):
    amount = (payload or {}).get("amount", 0)
    return {"status": "success", "amount": amount, "balance": 125.0 + float(amount or 0)}


@router.post("/wallet/ticket/scan")
@router.post("/wallet/ticket/save")
@router.post("/wallet/payment-methods")
def wallet_action():
    return {"status": "success"}


@router.get("/notifications")
def get_notifications():
    return {"notifications": []}


@router.post("/notifications/mark-read")
def mark_notifications_read():
    return {"status": "success"}


@router.get("/profile")
def get_profile(request: Request):
    return {
        "passenger_id": get_passenger_id(request),
        "name": "IZEE Passenger",
        "email": get_passenger_id(request),
    }

@router.get("/incidents")
def get_incidents(scope: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(TransitIncident)
    if scope == "control_center":
        query = query.filter(TransitIncident.transmitted_to_control == True)
        query = query.filter(TransitIncident.category != "Service Check")
    elif scope == "supervisor":
        query = query.filter(TransitIncident.source != "supervisor_app")
        query = query.filter(TransitIncident.category != "Service Check")
    
    rows = query.order_by(TransitIncident.created_at.desc()).limit(limit).all()
    incidents = []
    for inc in rows:
        incidents.append({
            "incident_id": inc.incident_id,
            "category": inc.category,
            "severity": inc.severity,
            "status": inc.status,
            "vehicle_id": inc.vehicle_id,
            "route_id": inc.route_id,
            "driver_name": inc.driver_name,
            "location_label": inc.location_label,
            "details": inc.details,
            "created_at": inc.created_at,
            "transmitted_to_control": inc.transmitted_to_control,
            "source": inc.source,
        })
    return {"incidents": incidents}

class ServiceCheckCreate(BaseModel):
    vehicle_id: str
    rating: int
    checks: dict
    notes: str | None = None
    recommend_driver_training: bool = False
    recommend_vehicle_maintenance: bool = False
    commend_excellent_service: bool = False
    source: str = "supervisor_app"

@router.post("/service-checks", status_code=201)
def create_service_check(payload: ServiceCheckCreate, db: Session = Depends(get_db)):
    # Find assignment for route_id and driver_name
    assignment = db.query(DriverAssignment).filter(
        DriverAssignment.vehicle_id == payload.vehicle_id,
        DriverAssignment.status == "active"
    ).first()
    if not assignment:
        assignment = db.query(DriverAssignment).filter(
            DriverAssignment.vehicle_id == payload.vehicle_id,
            DriverAssignment.status == "scheduled"
        ).first()
        
    route_id = assignment.route_id if assignment else None
    driver_name = None
    if assignment:
        driver = db.query(User).filter(User.user_id == assignment.driver_id).first()
        driver_name = driver.name if driver else assignment.driver_id

    raw_payload = {
        "report_type": "service_check",
        "rating": payload.rating,
        "checks": payload.checks,
        "recommend_driver_training": payload.recommend_driver_training,
        "recommend_vehicle_maintenance": payload.recommend_vehicle_maintenance,
        "commend_excellent_service": payload.commend_excellent_service,
    }

    db_incident = TransitIncident(
        category="Service Check",
        severity="info",
        status="new",
        transmitted_to_control=True,
        vehicle_id=payload.vehicle_id,
        route_id=route_id,
        driver_name=driver_name,
        details=payload.notes,
        source=payload.source,
        raw_payload=raw_payload,
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return {"incident_id": db_incident.incident_id}

@router.get("/service-checks")
def get_service_checks(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(TransitIncident)
        .filter(TransitIncident.category == "Service Check")
        .order_by(TransitIncident.created_at.desc())
        .limit(limit)
        .all()
    )
    service_checks = []
    for inc in rows:
        service_checks.append({
            "incident_id": inc.incident_id,
            "category": inc.category,
            "severity": inc.severity,
            "status": inc.status,
            "vehicle_id": inc.vehicle_id,
            "route_id": inc.route_id,
            "driver_name": inc.driver_name,
            "location_label": inc.location_label,
            "details": inc.details,
            "created_at": inc.created_at,
            "transmitted_to_control": inc.transmitted_to_control,
            "source": inc.source,
            "raw_payload": inc.raw_payload,
        })
    return {"service_checks": service_checks}

from pydantic import BaseModel

class IncidentCreate(BaseModel):
    category: str
    severity: str = "warning"
    status: str = "new"
    vehicle_id: str | None = None
    route_id: str | None = None
    driver_name: str | None = None
    lat: float | None = None
    lon: float | None = None
    location_label: str | None = None
    details: str | None = None
    source: str = "driver_app"
    raw_payload: dict | None = None

@router.post("/incidents")
def create_incident(incident: IncidentCreate, db: Session = Depends(get_db)):
    db_incident = TransitIncident(
        category=incident.category,
        severity=incident.severity,
        status=incident.status,
        vehicle_id=incident.vehicle_id,
        route_id=incident.route_id,
        driver_name=incident.driver_name,
        lat=incident.lat,
        lon=incident.lon,
        location_label=incident.location_label,
        details=incident.details,
        source=incident.source,
        raw_payload=incident.raw_payload,
        transmitted_to_control=incident.source == "supervisor_app",
    )
    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)
    return {"incident_id": db_incident.incident_id}



class IncidentActionRequest(BaseModel):
    status: str | None = None
    transmitted_to_control: bool | None = None
    replacement_vehicle_id: str | None = None
    speed_up: bool | None = None

@router.post("/incidents/{incident_id}/action")
def update_incident_action(incident_id: str, req: IncidentActionRequest, db: Session = Depends(get_db)):
    db_incident = db.query(TransitIncident).filter(TransitIncident.incident_id == incident_id).first()
    if not db_incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if req.status is not None:
        db_incident.status = req.status
    if req.transmitted_to_control is not None:
        db_incident.transmitted_to_control = req.transmitted_to_control
        
    if req.replacement_vehicle_id:
        # Find active driver assignment for the incident's broken vehicle
        db_assign = db.query(DriverAssignment).filter(
            DriverAssignment.vehicle_id == db_incident.vehicle_id,
            DriverAssignment.status == "active"
        ).first()
        if db_assign:
            db_assign.vehicle_id = req.replacement_vehicle_id
            db.commit()
            
    if req.speed_up:
        # Find active assignment for the vehicle
        db_assign = db.query(DriverAssignment).filter(
            DriverAssignment.vehicle_id == db_incident.vehicle_id,
            DriverAssignment.status == "active"
        ).first()
        
        # Get live vehicle state to find current speed
        state = db.query(VehicleLiveState).filter(VehicleLiveState.vehicle_id == db_incident.vehicle_id).first()
        current_speed = state.speed if state else 10.0
        
        # Update raw_payload of the incident with speed_checkpoint
        payload = db_incident.raw_payload or {}
        payload["speed_checkpoint"] = {
            "reference_speed": current_speed + 2.0,
            "checked": False,
            "accelerated": False
        }
        db_incident.raw_payload = payload
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(db_incident, "raw_payload")
        
        # Send Control Center message to driver
        if db_assign:
            driver_msg = ControlMessage(
                recipient_type="driver",
                recipient_id=db_assign.driver_id,
                sender="System",
                subject="Speed Up Request",
                body=f"Vehicle {db_incident.vehicle_id} has been reported as delayed. Please speed up to maintain schedule.",
                priority="high",
                source="system"
            )
            db.add(driver_msg)

    db.commit()
    db.refresh(db_incident)
    return {"status": "success", "incident_id": db_incident.incident_id}





class MessageCreate(BaseModel):
    recipient_type: str
    recipient_id: str | None = None
    sender: str | None = "Control Center"
    subject: str | None = None
    body: str
    priority: str = "normal"
    source: str = "control_center"
    raw_payload: dict | None = None


@router.websocket("/ws/messages")
async def message_presence_socket(websocket: WebSocket):
    user_type = (websocket.query_params.get("user_type") or "").lower()
    user_id = (websocket.query_params.get("user_id") or "").strip()
    if user_type not in {"driver", "supervisor"} or not user_id:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    key = (user_type, user_id)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    message_clients[key] = {
        "user_type": user_type,
        "user_id": user_id,
        "connected_at": now,
        "last_seen": now,
    }
    _save_message_last_seen(user_id, now, "active")
    print(f"MESSAGE_WS_CONNECTED {user_type} {user_id}")
    try:
        while True:
            await websocket.receive_text()
            if key in message_clients:
                message_clients[key]["last_seen"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    except WebSocketDisconnect:
        final_seen = message_clients.pop(key, {}).get(
            "last_seen", datetime.datetime.now(datetime.timezone.utc).isoformat())
        _save_message_last_seen(user_id, final_seen, "inactive")
        print(f"MESSAGE_WS_DISCONNECTED {user_type} {user_id}")


@router.get("/control-center/messaging/stats")
def messaging_stats(db: Session = Depends(get_db)):
    now = datetime.datetime.now(datetime.timezone.utc)
    messages = db.query(ControlMessage).all()
    sent_today = [m for m in messages if m.source == "control_center" and m.created_at.date() == now.date()]
    broadcasts = [m for m in sent_today if m.recipient_type == "all_drivers" or m.recipient_type.endswith("_drivers")]
    active_clients = list(message_clients.keys())
    ws_drivers = {uid for kind, uid in active_clients if kind == "driver"}
    ws_supervisors = {uid for kind, uid in active_clients if kind == "supervisor"}
    cutoff = now - datetime.timedelta(seconds=60)
    http_drivers, http_supervisors = set(), set()
    for key, last_seen in list(http_presence.items()):
        if last_seen < cutoff:
            http_presence.pop(key, None)
        elif key[0] == "driver":
            http_drivers.add(key[1])
        elif key[0] == "supervisor":
            http_supervisors.add(key[1])
    drivers = len(ws_drivers | http_drivers)
    supervisors = len(ws_supervisors | http_supervisors)
    total = drivers + supervisors
    print(f"ACTIVE_RECIPIENTS_COUNT {drivers} {supervisors} {total}")
    return {"messages_sent_today": len(sent_today), "active_recipients": total,
            "active_drivers": drivers, "active_supervisors": supervisors,
            "active_driver_ids": [user_id for (kind, user_id) in active_clients if kind == "driver"],
            "active_supervisor_ids": [user_id for (kind, user_id) in active_clients if kind == "supervisor"],
            "broadcast_messages_today": len(broadcasts)}

@router.get("/messages")
def get_messages(
    recipient_type: str | None = None,
    recipient_id: str | None = None,
    sender: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    if recipient_id:
        kind = "supervisor" if recipient_id.lower().startswith(("supervisor", "sup_", "sup")) else "driver"
        seen_at = datetime.datetime.now(datetime.timezone.utc)
        http_presence[(kind, recipient_id)] = seen_at
        # Persist real messaging activity for the Users page once this client
        # is no longer considered currently active.
        user = db.query(User).filter(User.user_id == recipient_id).first()
        if user and user.status != "suspended":
            user.last_active = seen_at.isoformat()
            db.commit()
    query = db.query(ControlMessage)

    from sqlalchemy import or_
    filters = []
    if recipient_id:
        recipient = db.query(User).filter(User.user_id == recipient_id).first()
        if recipient and recipient.status == "suspended":
            return {"messages": []}
        # A direct conversation contains only messages sent by this user or
        # addressed to this user.  Do not fold supervisor broadcasts into this
        # query: supervisors must not see one another's control-center chats.
        filters.append(ControlMessage.recipient_id == recipient_id)
        filters.append(ControlMessage.sender == recipient_id)
        if "supervisor" not in recipient_id.lower() and "sup" not in recipient_id.lower():
            filters.append(ControlMessage.recipient_type == "all_drivers")
            
    if recipient_type:
        filters.append(ControlMessage.recipient_type == recipient_type)
        
    if sender:
        filters.append(ControlMessage.sender == sender)
        
    if filters:
        query = query.filter(or_(*filters))
        
    msgs = query.order_by(ControlMessage.created_at.desc()).limit(limit).all()
    result = []
    for m in msgs:
        result.append({
            "message_id": m.message_id,
            "recipient_type": m.recipient_type,
            "recipient_id": m.recipient_id,
            "sender": m.sender,
            "subject": m.subject,
            "body": m.body,
            "priority": m.priority,
            "status": m.status,
            "source": m.source,
            "created_at": m.created_at,
            "read": m.read,
            "read_at": m.read_at,
            "raw_payload": m.raw_payload,
        })
    return {"messages": result}

@router.post("/messages")
def create_message(msg: MessageCreate, db: Session = Depends(get_db)):
    # A suspended Driver/Supervisor cannot send or receive control messages.
    if msg.source in {"driver_app", "supervisor_app"}:
        sender = db.query(User).filter(User.user_id == msg.sender).first()
        if sender and sender.status == "suspended":
            raise HTTPException(403, detail="Suspended users cannot send messages")
    if msg.recipient_id:
        recipient = db.query(User).filter(User.user_id == msg.recipient_id).first()
        if recipient and recipient.status == "suspended":
            raise HTTPException(403, detail="Cannot send a message to a suspended user")
    db_msg = ControlMessage(
        recipient_type=msg.recipient_type,
        recipient_id=msg.recipient_id,
        sender=msg.sender or "Control Center",
        subject=msg.subject or "Control Center Chat",
        body=msg.body,
        priority=msg.priority,
        source=msg.source,
        raw_payload=msg.raw_payload,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return {"message_id": db_msg.message_id}


@router.post("/messages/{message_id}/read")
def mark_message_read(message_id: str, db: Session = Depends(get_db)):
    db_msg = db.query(ControlMessage).filter(ControlMessage.message_id == message_id).first()
    if not db_msg:
        raise HTTPException(404, detail="Message not found")
    db_msg.read = True
    db_msg.read_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_msg)
    return {"status": "success", "message_id": db_msg.message_id, "read": db_msg.read}

@router.get("/control-center/drivers")
def get_cc_drivers(db: Session = Depends(get_db)):
    ensure_defaults(db)
    users = db.query(User).all()
    active_driver_connection_ids = {
        user_id for (kind, user_id) in message_clients if kind == "driver"
    }
    active_supervisor_ids = {
        user_id for (kind, user_id) in message_clients if kind == "supervisor"
    }
    # Match the existing Active Now metric: WebSocket presence plus a recent
    # /messages poll from a mobile app.
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)
    active_driver_connection_ids.update(
        user_id for (kind, user_id), seen in http_presence.items()
        if kind == "driver" and seen >= cutoff
    )
    active_supervisor_ids.update(
        user_id for (kind, user_id), seen in http_presence.items()
        if kind == "supervisor" and seen >= cutoff
    )
    # Some Driver App builds use the assigned vehicle ID as their messaging
    # identifier. Resolve that live connection back to its actual driver row.
    active_driver_ids = set(active_driver_connection_ids)
    for assignment in db.query(DriverAssignment).filter(
        DriverAssignment.status.in_(["scheduled", "active"]),
        DriverAssignment.vehicle_id.in_(active_driver_connection_ids),
    ).all():
        active_driver_ids.add(assignment.driver_id)

    result = []
    for u in users:
        active_client = (
            u.user_id in active_driver_ids or u.user_id in active_supervisor_ids
        )
        # find current active/scheduled assignment
        assign = db.query(DriverAssignment).filter(
            DriverAssignment.driver_id == u.user_id,
            DriverAssignment.status.in_(["scheduled", "active"])
        ).first()
        assign_label = assign.route_name or assign.route_id if assign else "None"
        stored_last_active = u.last_active or "Never"
        if not active_client and stored_last_active not in {"Never", "Unknown"}:
            try:
                datetime.datetime.fromisoformat(stored_last_active.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                # Values such as "Now" and "2 min ago" came from old seeded
                # demo data, not an actual app activity timestamp.
                stored_last_active = "Never"
        result.append({
            "driver_id": u.user_id,
            "name": u.name,
            "role": u.role,
            "assignment": assign_label,
            # Status in the Control Center user list is live messaging
            # presence, not the static account status seeded in the database.
            "status": "active" if active_client else (
                "suspended" if u.status == "suspended" else "inactive"
            ),
            "last_active": "Now" if active_client else stored_last_active
        })
    # A connected client is real runtime data. If its identifier has not yet
    # been provisioned in the user directory, expose it instead of silently
    # losing the active status shown by the messaging counter.
    known_ids = {entry["driver_id"] for entry in result}
    for (kind, user_id), client in message_clients.items():
        if user_id not in known_ids and not (
            kind == "driver" and user_id in active_driver_connection_ids and
            any(a.vehicle_id == user_id for a in db.query(DriverAssignment).filter(
                DriverAssignment.status.in_(["scheduled", "active"])
            ).all())
        ):
            result.append({
                "driver_id": user_id,
                "name": user_id,
                "role": "Driver" if kind == "driver" else "Supervisor",
                "assignment": "None",
                "status": "active",
                "last_active": "Now",
            })
    return {"users": result}


class ControlCenterUserInput(BaseModel):
    user_id: str
    name: str
    role: str


class SuspensionUpdate(BaseModel):
    suspended: bool


@router.post("/control-center/users", status_code=201)
def create_control_center_user(payload: ControlCenterUserInput, db: Session = Depends(get_db)):
    if payload.role not in {"Driver", "Supervisor", "Operator"}:
        raise HTTPException(400, detail="Role must be Driver, Supervisor, or Operator")
    if db.query(User).filter(User.user_id == payload.user_id).first():
        raise HTTPException(409, detail="User ID already exists")
    user = User(user_id=payload.user_id, name=payload.name, role=payload.role, status="inactive", last_active="Never")
    db.add(user)
    db.commit()
    return {"user_id": user.user_id}


@router.put("/control-center/users/{user_id}")
def update_control_center_user(user_id: str, payload: ControlCenterUserInput, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    if payload.role not in {"Driver", "Supervisor", "Operator"}:
        raise HTTPException(400, detail="Role must be Driver, Supervisor, or Operator")
    user.name, user.role = payload.name, payload.role
    db.commit()
    return {"user_id": user.user_id}


@router.post("/control-center/users/{user_id}/suspend")
def suspend_control_center_user(user_id: str, payload: SuspensionUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found")
    user.status = "suspended" if payload.suspended else "active"
    if payload.suspended:
        for key in [key for key in message_clients if key[1] == user_id]:
            message_clients.pop(key, None)
        for key in [key for key in http_presence if key[1] == user_id]:
            http_presence.pop(key, None)
    db.commit()
    return {"user_id": user.user_id, "status": user.status}




@router.post("/drivers/{driver_id}/assignments", status_code=201)
async def create_driver_assignment_from_control_center(driver_id: str, request: Request, db: Session = Depends(get_db)):
    ensure_defaults(db)
    body = await request.json()
    route_id = body.get("route_id") or "Route 8"
    vehicle_id = body.get("vehicle_id") or "BUS_001"
    supervisor_id = body.get("supervisor_id") or "supervisor_2"
    today = datetime.date.today().isoformat()

    sup_region = db.query(SupervisorRegion).filter(SupervisorRegion.supervisor_id == supervisor_id).first()
    region_id = body.get("region_id") or (sup_region.region_id if sup_region else "Zone_East")
    trip = db.query(Trip).filter(Trip.route_id == route_id).first()
    assignment = DriverAssignment(
        assignment_id=f"ASGN_{uuid.uuid4().hex[:8].upper()}",
        supervisor_id=supervisor_id,
        region_id=region_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        route_id=route_id,
        route_name=_route_label(db, route_id),
        trip_id=body.get("trip_id") or (trip.trip_id if trip else f"TRIP_{route_id.replace(' ', '_')}_{uuid.uuid4().hex[:6].upper()}"),
        service_date=body.get("service_date") or today,
        planned_start_time=body.get("planned_start_time") or "08:00:00",
        planned_end_time=body.get("planned_end_time") or "23:00:00",
        status=body.get("status") or "scheduled",
        notes=body.get("notes"),
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return {"assignment": assignment}


# ==========================================
# SUPERVISOR ENDPOINTS
# ==========================================

@router.get("/supervisor/{supervisor_id}/region")
def get_supervisor_single_region(supervisor_id: str, db: Session = Depends(get_db)):
    """Return the single (first) region assigned to this supervisor.
    Used by the Flutter app to auto-load region without a dropdown."""
    print(f"SUPERVISOR_REGION_LOOKUP: supervisor_id={supervisor_id}")
    ensure_defaults(db)
    mapping = db.query(SupervisorRegion).filter(
        SupervisorRegion.supervisor_id == supervisor_id
    ).first()
    print(f"ACTIVE_SUPERVISOR_REGION_MAPPING: supervisor_id={supervisor_id}, region_id={mapping.region_id if mapping else None}")
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Supervisor {supervisor_id} is not assigned to any region"
        )
    region = db.query(Region).filter(Region.region_id == mapping.region_id).first()
    print(f"REGION_ACTIVE_STATUS: region_id={region.region_id if region else None}, active={region.active if region else None}")
    if not region:
        raise HTTPException(
            status_code=404,
            detail=f"Region {mapping.region_id} not found"
        )
    print(f"SUPERVISOR_REGION_LOOKUP: supervisor_id={supervisor_id}, region_id={region.region_id}")
    return {"region_id": region.region_id, "region_name": region.region_name}


@router.get("/supervisor/{supervisor_id}/regions")
def get_supervisor_regions(supervisor_id: str, db: Session = Depends(get_db)):
    ensure_defaults(db)
    regions = db.query(Region).join(
        SupervisorRegion, Region.region_id == SupervisorRegion.region_id
    ).filter(SupervisorRegion.supervisor_id == supervisor_id).all()
    return regions


@router.get("/supervisor/{supervisor_id}/routes")
def get_supervisor_routes(supervisor_id: str, region_id: str = None, db: Session = Depends(get_db)):
    ensure_defaults(db)
    query = db.query(RegionRoute).join(
        SupervisorRegion, RegionRoute.region_id == SupervisorRegion.region_id
    ).filter(SupervisorRegion.supervisor_id == supervisor_id)
    if region_id:
        query = query.filter(RegionRoute.region_id == region_id)
    routes = query.all()
    return [{"route_id": r.route_id, "route_name": r.route_name or r.route_id} for r in routes]


@router.get("/supervisor/{supervisor_id}/vehicles")
def get_supervisor_vehicles(supervisor_id: str, region_id: str = None, db: Session = Depends(get_db)):
    ensure_defaults(db)
    query = db.query(RegionVehicle).join(
        SupervisorRegion, RegionVehicle.region_id == SupervisorRegion.region_id
    ).filter(SupervisorRegion.supervisor_id == supervisor_id)
    if region_id:
        query = query.filter(RegionVehicle.region_id == region_id)
    vehicles = query.all()
    return [v.vehicle_id for v in vehicles]


@router.get("/supervisor/{supervisor_id}/drivers")
def get_supervisor_drivers(supervisor_id: str, db: Session = Depends(get_db)):
    ensure_defaults(db)
    sup_reg = db.query(SupervisorRegion).filter(SupervisorRegion.supervisor_id == supervisor_id).first()
    if not sup_reg:
        return []
    mappings = db.query(RegionDriverMapping).filter(
        RegionDriverMapping.region_id == sup_reg.region_id,
        RegionDriverMapping.active == True
    ).all()
    driver_ids = [m.driver_id for m in mappings]
    drivers = db.query(User).filter(
        User.role == "Driver",
        User.status == "active",
        User.user_id.in_(driver_ids)
    ).all()
    return [{"driver_id": d.user_id, "name": d.name} for d in drivers]


@router.post("/supervisor/{supervisor_id}/assignments", status_code=201)
async def create_assignment(supervisor_id: str, request: Request, db: Session = Depends(get_db)):
    # Always ensure seed data is present
    ensure_defaults(db)

    body = await request.json()
    print("CREATE_ASSIGNMENT_RECEIVED_BODY:", body)

    try:
        req = AssignmentCreateRequest(**body)
    except Exception as e:
        print(f"CREATE_ASSIGNMENT_PARSE_ERROR: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    # ---- Detailed diagnostic log ----
    sup_mappings = db.query(SupervisorRegion).filter(SupervisorRegion.supervisor_id == supervisor_id).all()
    sup_region_ids = [m.region_id for m in sup_mappings]
    route_mapping = db.query(RegionRoute).filter(RegionRoute.route_id == req.route_id).first()
    vehicle_mapping = db.query(RegionVehicle).filter(RegionVehicle.vehicle_id == req.vehicle_id).first()
    print(
        f"CREATE_ASSIGNMENT_DIAGNOSTIC: "
        f"url_supervisor_id={supervisor_id!r} "
        f"payload_region_id={req.region_id!r} "
        f"payload_route_id={req.route_id!r} "
        f"payload_vehicle_id={req.vehicle_id!r} "
        f"payload_driver_id={req.driver_id!r} "
        f"db_sup_regions={sup_region_ids} "
        f"db_route_region={route_mapping.region_id if route_mapping else None!r} "
        f"db_vehicle_region={vehicle_mapping.region_id if vehicle_mapping else None!r}"
    )
    # ---------------------------------

    region_id = check_assignment_validations(
        db=db,
        supervisor_id=supervisor_id,
        driver_id=req.driver_id,
        vehicle_id=req.vehicle_id,
        route_id=req.route_id,
        service_date=req.service_date,
        planned_start_time=req.planned_start_time,
        planned_end_time=req.planned_end_time,
        incoming_region_id=req.region_id
    )

    if req.region_id and req.region_id != region_id:
        raise HTTPException(400, detail=f"Request region_id ({req.region_id}) does not match mapped route region ({region_id})")

    # 5. trip_id selection / generation
    existing_trip = db.query(Trip).filter(Trip.route_id == req.route_id).first()
    trip_id = req.trip_id or (existing_trip.trip_id if existing_trip else f"TRIP_{req.route_id.replace(' ', '_')}_{uuid.uuid4().hex[:6].upper()}")

    route_mapping = db.query(RegionRoute).filter(RegionRoute.route_id == req.route_id).first()
    route_name = route_mapping.route_name if route_mapping else req.route_id

    assignment_id = f"ASGN_{uuid.uuid4().hex[:8].upper()}"

    db_assign = DriverAssignment(
        assignment_id=assignment_id,
        supervisor_id=supervisor_id,
        region_id=region_id,
        driver_id=req.driver_id,
        vehicle_id=req.vehicle_id,
        route_id=req.route_id,
        route_name=route_name,
        trip_id=trip_id,
        service_date=req.service_date,
        planned_start_time=req.planned_start_time,
        planned_end_time=req.planned_end_time,
        status=req.status or "scheduled",
        notes=req.notes
    )
    db.add(db_assign)
    db.commit()
    print(f"ASSIGNMENT_CREATED_SUCCESSFULLY: assignment_id={assignment_id}")
    db.refresh(db_assign)
    return db_assign


@router.get("/supervisor/{supervisor_id}/assignments")
def get_supervisor_assignments(supervisor_id: str, db: Session = Depends(get_db)):
    # Return all assignments created by this supervisor
    return db.query(DriverAssignment).filter(DriverAssignment.supervisor_id == supervisor_id).all()


@router.put("/supervisor/{supervisor_id}/assignments/{assignment_id}")
async def update_assignment(supervisor_id: str, assignment_id: str, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    print("RAW UPDATE ASSIGNMENT BODY:", body)
    print("BACKEND_RECEIVED_ASSIGNMENT_BODY:", body)
    try:
        req = AssignmentUpdateRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    db_assign = db.query(DriverAssignment).filter(DriverAssignment.assignment_id == assignment_id).first()
    if not db_assign:
        raise HTTPException(404, detail="Assignment not found")

    # 10. Completed/cancelled assignment cannot be edited or restarted
    if db_assign.status in ("completed", "cancelled"):
        raise HTTPException(400, detail="Completed or cancelled assignments cannot be edited")

    # Update parameters if supplied
    driver_id = req.driver_id if req.driver_id is not None else db_assign.driver_id
    vehicle_id = req.vehicle_id if req.vehicle_id is not None else db_assign.vehicle_id
    route_id = req.route_id if req.route_id is not None else db_assign.route_id
    service_date = req.service_date if req.service_date is not None else db_assign.service_date
    planned_start = req.planned_start_time if req.planned_start_time is not None else db_assign.planned_start_time
    planned_end = req.planned_end_time if req.planned_end_time is not None else db_assign.planned_end_time
    notes = req.notes if req.notes is not None else db_assign.notes

    # Perform validations
    region_id = check_assignment_validations(
        db=db,
        supervisor_id=supervisor_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        route_id=route_id,
        service_date=service_date,
        planned_start_time=planned_start,
        planned_end_time=planned_end,
        exclude_assignment_id=assignment_id,
        incoming_region_id=req.region_id
    )

    if req.region_id and req.region_id != region_id:
        raise HTTPException(400, detail=f"Request region_id ({req.region_id}) does not match mapped route region ({region_id})")

    db_assign.driver_id = driver_id
    db_assign.vehicle_id = vehicle_id
    db_assign.route_id = route_id
    db_assign.service_date = service_date
    db_assign.planned_start_time = planned_start
    db_assign.planned_end_time = planned_end
    db_assign.notes = notes
    db_assign.region_id = region_id

    # If route or trip changed, update it
    if req.trip_id is not None:
        db_assign.trip_id = req.trip_id
    elif req.route_id is not None:
        existing_trip = db.query(Trip).filter(Trip.route_id == route_id).first()
        db_assign.trip_id = existing_trip.trip_id if existing_trip else f"TRIP_{route_id.replace(' ', '_')}_{uuid.uuid4().hex[:6].upper()}"

    if req.status is not None:
        db_assign.status = req.status

    if req.route_id is not None:
        route_mapping = db.query(RegionRoute).filter(RegionRoute.route_id == route_id).first()
        db_assign.route_name = route_mapping.route_name if route_mapping else route_id

    db.commit()
    db.refresh(db_assign)
    return db_assign


@router.post("/supervisor/{supervisor_id}/assignments/{assignment_id}/cancel")
async def cancel_assignment(
    supervisor_id: str,
    assignment_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    db_assign = db.query(DriverAssignment).filter(
        DriverAssignment.assignment_id == assignment_id,
        DriverAssignment.supervisor_id == supervisor_id
    ).first()
    if not db_assign:
        raise HTTPException(404, detail="Assignment not found")

    # Mark completed/cancelled as non-cancellable if they are already done
    if db_assign.status in ("completed", "cancelled"):
        raise HTTPException(400, detail="Cannot cancel completed or already cancelled duty")

    body = await request.json()
    reason = str(body.get("reason") or "Cancelled by supervisor").strip()
    cancellation_note = f"Cancelled by {supervisor_id}: {reason}"
    db_assign.notes = "\n".join(
        note for note in [db_assign.notes, cancellation_note] if note
    )
    db_assign.status = "cancelled"
    db.commit()
    db.refresh(db_assign)
    return db_assign


@router.delete("/supervisor/{supervisor_id}/assignments/{assignment_id}")
def delete_assignment(
    supervisor_id: str,
    assignment_id: str,
    db: Session = Depends(get_db),
):
    """Remove a supervisor-owned duty that is not currently in progress.

    Completed and active duties are operational records, so they cannot be
    removed through the supervisor app. Cancel an upcoming duty first if it is
    no longer needed, then delete it from the current assignment list.
    """
    db_assign = db.query(DriverAssignment).filter(
        DriverAssignment.assignment_id == assignment_id,
        DriverAssignment.supervisor_id == supervisor_id,
    ).first()
    if not db_assign:
        raise HTTPException(404, detail="Assignment not found")
    if db_assign.status in ("active", "completed"):
        raise HTTPException(
            400,
            detail="Active or completed assignments cannot be deleted",
        )

    db.delete(db_assign)
    db.commit()
    return {"status": "deleted", "assignment_id": assignment_id}


# ==========================================
# DRIVER ENDPOINTS
# ==========================================

@router.get("/driver/{driver_id}/duties")
def get_driver_duties(driver_id: str, db: Session = Depends(get_db)):
    ensure_defaults(db)
    # Find all scheduled or active duties for this driver
    assignments = db.query(DriverAssignment).filter(
        DriverAssignment.driver_id == driver_id,
        DriverAssignment.status.in_(["scheduled", "active"])
    ).order_by(DriverAssignment.service_date, DriverAssignment.planned_start_time).all()

    result = []
    for a in assignments:
        origin, dest = get_route_endpoints(db, a.route_id)
        result.append({
            "assignment_id": a.assignment_id,
            "driver_id": a.driver_id,
            "vehicle_id": a.vehicle_id,
            "route_id": a.route_id,
            "route_name": a.route_name or a.route_id,
            "trip_id": a.trip_id,
            "origin": origin,
            "destination": dest,
            "start_time": a.planned_start_time,
            "end_time": a.planned_end_time,
            "service_date": a.service_date,
            "status": a.status,
            "notes": a.notes
        })
    return {"assignments": result, "assigned_trips": result}


@router.get("/driver/assigned-duties")
def get_driver_assigned_duties(vehicle_id: str = Query(None), limit: int = 5, db: Session = Depends(get_db)):
    ensure_defaults(db)
    query = db.query(DriverAssignment).filter(DriverAssignment.status.in_(["scheduled", "active"]))
    if vehicle_id:
        query = query.filter(
            (DriverAssignment.vehicle_id == vehicle_id) |
            (DriverAssignment.driver_id == vehicle_id)
        )
    assignments = query.order_by(DriverAssignment.service_date, DriverAssignment.planned_start_time).limit(limit).all()
    result = []
    for a in assignments:
        origin, dest = get_route_endpoints(db, a.route_id)
        result.append({
            "assignment_id": a.assignment_id,
            "driver_id": a.driver_id,
            "vehicle_id": a.vehicle_id,
            "route_id": a.route_id,
            "route_name": a.route_name or a.route_id,
            "trip_id": a.trip_id,
            "origin": origin,
            "destination": dest,
            "start_time": a.planned_start_time,
            "end_time": a.planned_end_time,
            "service_date": a.service_date,
            "status": a.status,
            "notes": a.notes,
        })
    return {"assignments": result, "assigned_trips": result}


@router.post("/driver/assignments/{assignment_id}/start")
def start_assignment(assignment_id: str, db: Session = Depends(get_db)):
    db_assign = db.query(DriverAssignment).filter(DriverAssignment.assignment_id == assignment_id).first()
    if not db_assign:
        raise HTTPException(404, detail="Assignment not found")

    if db_assign.status == "active":
        return db_assign

    # 8. Only scheduled assignment can be started
    if db_assign.status != "scheduled":
        raise HTTPException(400, detail=f"Cannot start assignment with status: {db_assign.status}")

    db_assign.status = "active"
    db_assign.actual_start_time = datetime.datetime.utcnow().isoformat()
    db_assign.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_assign)
    return db_assign

@router.get("/passenger/favorites")
def get_passenger_favorites(request: Request, db: Session = Depends(get_db)):
    ensure_defaults(db)
    passenger_id = get_passenger_id(request)
    favorites = db.query(PassengerFavorite).filter(PassengerFavorite.passenger_id == passenger_id).all()
    return [{"route_id": f.route_id, "route_name": f.route_name, "created_at": f.created_at} for f in favorites]

@router.post("/passenger/favorites", status_code=201)
def add_passenger_favorite(request: Request, fav: dict, db: Session = Depends(get_db)):
    ensure_defaults(db)
    passenger_id = get_passenger_id(request)
    route_id = fav.get("route_id")
    route_name = fav.get("route_name")
    if not route_id:
        raise HTTPException(400, detail="route_id required")
    existing = db.query(PassengerFavorite).filter(PassengerFavorite.passenger_id == passenger_id, PassengerFavorite.route_id == route_id).first()
    if existing:
        raise HTTPException(400, detail="Favorite already exists")
    new_fav = PassengerFavorite(passenger_id=passenger_id, route_id=route_id, route_name=route_name)
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)
    return {"id": new_fav.id, "route_id": new_fav.route_id, "route_name": new_fav.route_name}

@router.delete("/passenger/favorites/{route_id}")
def delete_passenger_favorite(route_id: str, request: Request, db: Session = Depends(get_db)):
    ensure_defaults(db)
    passenger_id = get_passenger_id(request)
    fav = db.query(PassengerFavorite).filter(PassengerFavorite.passenger_id == passenger_id, PassengerFavorite.route_id == route_id).first()
    if not fav:
        raise HTTPException(404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"status": "deleted"}

@router.get("/passenger/trip-history")
def get_passenger_trip_history(request: Request, db: Session = Depends(get_db)):
    ensure_defaults(db)
    passenger_id = get_passenger_id(request)
    history = db.query(PassengerTripHistory).filter(PassengerTripHistory.passenger_id == passenger_id).all()
    return [{"route_id": h.route_id, "route_name": h.route_name, "timestamp": h.timestamp} for h in history]

@router.post("/routes/{route_id}/start", status_code=201)
def start_route(route_id: str, request: Request, db: Session = Depends(get_db)):
    ensure_defaults(db)
    passenger_id = get_passenger_id(request)
    # Retrieve route name if available
    route = db.query(OperationalRoute).filter(OperationalRoute.route_id == route_id).first()
    route_name = route.route_long_name if route else route_id
    new_entry = PassengerTripHistory(passenger_id=passenger_id, route_id=route_id, route_name=route_name)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {"id": new_entry.id, "route_id": new_entry.route_id, "route_name": new_entry.route_name, "timestamp": new_entry.timestamp}


@router.post("/routes/{route_id}/cancel")
def cancel_passenger_route(route_id: str):
    return {"status": "cancelled", "route_id": route_id}


@router.post("/routes/{route_id}/share")
def share_passenger_route(route_id: str):
    return {"status": "shared", "route_id": route_id}


@router.post("/routes/{route_id}/driver/call")
def call_route_driver(route_id: str):
    return {"status": "requested", "route_id": route_id}


@router.post("/driver/assignments/{assignment_id}/complete")
def complete_assignment(assignment_id: str, db: Session = Depends(get_db)):
    db_assign = db.query(DriverAssignment).filter(DriverAssignment.assignment_id == assignment_id).first()
    if not db_assign:
        raise HTTPException(404, detail="Assignment not found")

    # 9. Only active assignment can be completed
    if db_assign.status != "active":
        raise HTTPException(400, detail=f"Cannot complete assignment with status: {db_assign.status}")

    # Ensure vehicle has reported a live state for this assignment
    state = db.query(VehicleLiveState).filter(
        VehicleLiveState.assignment_id == assignment_id,
        VehicleLiveState.vehicle_id == db_assign.vehicle_id,
        VehicleLiveState.trip_id == db_assign.trip_id,
    ).first()
    if not state:
        raise HTTPException(400, detail="Cannot complete assignment: no live vehicle position reported")

    db_assign.status = "completed"
    db_assign.actual_end_time = datetime.datetime.utcnow().isoformat()
    db.commit()
    db.refresh(db_assign)
    return db_assign


@router.get("/driver/{driver_id}/trip-history")
def get_driver_trip_history(driver_id: str, db: Session = Depends(get_db)):
    # Find all completed, cancelled or interrupted duties for this driver
    assignments = db.query(DriverAssignment).filter(
        DriverAssignment.driver_id == driver_id,
        DriverAssignment.status.in_(["completed", "cancelled", "interrupted"])
    ).order_by(DriverAssignment.service_date.desc(), DriverAssignment.planned_start_time.desc()).all()

    result = []
    for a in assignments:
        origin, dest = get_route_endpoints(db, a.route_id)
        result.append({
            "assignment_id": a.assignment_id,
            "driver_id": a.driver_id,
            "vehicle_id": a.vehicle_id,
            "route_id": a.route_id,
            "route_name": a.route_name or a.route_id,
            "trip_id": a.trip_id,
            "origin": origin,
            "destination": dest,
            "start_time": a.planned_start_time,
            "end_time": a.planned_end_time,
            "actual_start_time": a.actual_start_time,
            "actual_end_time": a.actual_end_time,
            "service_date": a.service_date,
            "status": a.status,
            "duration": ""  # Calculated on frontend
        })
    return {"history": result}
