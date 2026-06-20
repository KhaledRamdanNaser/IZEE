from database.connection import SessionLocal
from models.route import Route
from models.trip import Trip
from models.trips_workflow import OperationalRoute, DriverAssignment

db = SessionLocal()
try:
    print("--- Database Content Check ---")
    routes = db.query(Route).all()
    print(f"GTFS Routes ({len(routes)}):")
    for r in routes[:10]:
        print(f"  route_id: {r.route_id}, route_name: {r.route_name}")
        
    op_routes = db.query(OperationalRoute).all()
    print(f"Operational Routes ({len(op_routes)}):")
    for r in op_routes[:10]:
        print(f"  route_id: {r.route_id}, short: {r.route_short_name}, mode: {r.mode}, active: {r.is_active}")
        
    trips = db.query(Trip).all()
    print(f"GTFS Trips ({len(trips)}):")
    for t in trips[:10]:
        print(f"  trip_id: {t.trip_id}, route_id: {t.route_id}, shape_id: {t.shape_id}")
        
    assignments = db.query(DriverAssignment).all()
    print(f"Driver Assignments ({len(assignments)}):")
    for a in assignments:
        print(f"  id: {a.assignment_id}, driver: {a.driver_id}, vehicle: {a.vehicle_id}, route: {a.route_id}, trip: {a.trip_id}, status: {a.status}")
finally:
    db.close()
