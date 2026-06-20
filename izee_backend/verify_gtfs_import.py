import sys
from database.connection import SessionLocal
from api.routes.trips_workflow import ensure_defaults
from models.agency import Agency
from models.stop import Stop
from models.route import Route
from models.trip import Trip
from models.stop_time import StopTime
from models.shape import Shape
from models.trips_workflow import OperationalRoute, DriverAssignment

db = SessionLocal()
try:
    print("--- STEP 1: Running ensure_defaults (Triggering GTFS import) ---")
    ensure_defaults(db)
    
    print("\n--- STEP 2: Checking row counts in DB ---")
    print(f"Agencies: {db.query(Agency).count()}")
    print(f"Stops: {db.query(Stop).count()}")
    print(f"Routes (GTFS): {db.query(Route).count()}")
    print(f"Operational Routes (Control Center): {db.query(OperationalRoute).count()}")
    print(f"Shapes: {db.query(Shape).count()}")
    print(f"Trips: {db.query(Trip).count()}")
    print(f"Stop Times: {db.query(StopTime).count()}")
    
    print("\n--- STEP 3: Checking trips with shape_ids ---")
    trips_with_shapes = db.query(Trip).filter(Trip.shape_id != None).limit(5).all()
    print(f"Trips with shape_id in DB (Sample of 5):")
    for t in trips_with_shapes:
        print(f"  trip_id: {t.trip_id}, route_id: {t.route_id}, shape_id: {t.shape_id}")
        
    print("\n--- STEP 4: Simulating Route Info Endpoint query ---")
    # Find an assignment or create a temporary one for testing
    assign = db.query(DriverAssignment).first()
    if assign:
        print(f"Found assignment ID: {assign.assignment_id}, route: {assign.route_id}, trip: {assign.trip_id}")
        # Try to resolve trip and shape points
        trip = db.query(Trip).filter(Trip.trip_id == assign.trip_id).first()
        if not trip:
            trip = db.query(Trip).filter(Trip.route_id == assign.route_id).first()
        if trip:
            print(f"Resolved Trip: {trip.trip_id}, Shape ID: {trip.shape_id}")
            if trip.shape_id:
                pts = db.query(Shape).filter(Shape.shape_id == trip.shape_id).order_by(Shape.sequence).all()
                print(f"  Number of shape points for this shape: {len(pts)}")
                if pts:
                    print(f"  First point: {pts[0].lat}, {pts[0].lon}")
            else:
                print("  No shape ID on this trip")
        else:
            print("  No trip resolved for route ID")
    else:
        print("No assignments found in DB")

finally:
    db.close()
