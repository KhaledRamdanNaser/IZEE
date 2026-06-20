import sys
import os
import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from database.connection import SessionLocal, engine
from models.agency import Agency
from models.route import Route
from models.trip import Trip
from models.stop import Stop
from models.stop_time import StopTime
from models.trips_workflow import Region, SupervisorRegion, RegionRoute, RegionVehicle, DriverAssignment, User, RegionDriverMapping
from main import app

client = TestClient(app)

def seed_test_data():
    db = SessionLocal()
    try:
        # Clear existing trips workflow data to make tests repeatable
        db.query(RegionDriverMapping).delete()
        db.query(DriverAssignment).delete()
        db.query(RegionVehicle).delete()
        db.query(RegionRoute).delete()
        db.query(SupervisorRegion).delete()
        db.query(Region).delete()
        db.query(User).delete()

        # Seed GTFS reference data
        # Agency
        if not db.query(Agency).filter(Agency.agency_id == "agency_1").first():
            db.add(Agency(agency_id="agency_1", name="Cairo Transit Authority"))
        
        # Route
        if not db.query(Route).filter(Route.route_id == "CTA 1023").first():
            db.add(Route(route_id="CTA 1023", route_name="CTA 1023", agency_id="agency_1"))
            
        # Trip
        if not db.query(Trip).filter(Trip.trip_id == "trip_1").first():
            db.add(Trip(trip_id="trip_1", route_id="CTA 1023", direction_id=0))
            
        # Stops
        if not db.query(Stop).filter(Stop.stop_id == "stop_1").first():
            db.add(Stop(stop_id="stop_1", name="Downtown Terminal", lat=30.0444, lon=31.2357))
        if not db.query(Stop).filter(Stop.stop_id == "stop_2").first():
            db.add(Stop(stop_id="stop_2", name="Cairo Stadium Station", lat=30.0666, lon=31.2557))
            
        # Stop Times
        if not db.query(StopTime).filter(StopTime.trip_id == "trip_1", StopTime.stop_id == "stop_1").first():
            db.add(StopTime(trip_id="trip_1", stop_id="stop_1", stop_sequence=1))
        if not db.query(StopTime).filter(StopTime.trip_id == "trip_1", StopTime.stop_id == "stop_2").first():
            db.add(StopTime(trip_id="trip_1", stop_id="stop_2", stop_sequence=2))

        # Seed Workflow users
        db.add(User(user_id="supervisor_2", name="Ahmed Hassan", role="Supervisor", status="active"))
        db.add(User(user_id="driver_test_001", name="Mohamed Ali", role="Driver", status="active"))

        db.commit()
    finally:
        db.close()

def run_tests():
    print("Seeding test data...")
    seed_test_data()
    print("Test data seeded.")

    # PART 2 Scenario setups
    print("\n--- Running Test Case A: Happy Path ---")
    
    # 1. CC creates region Zone East
    resp = client.post("/control/regions", json={"region_name": "Zone East", "description": "East Zone description", "active": True})
    assert resp.status_code == 201, f"Failed to create region: {resp.text}"
    region = resp.json()
    print("DEBUG REGION:", region)
    region_id = region["region_id"]
    print("Region created:", region_id)

    # Debug: Check if region is committed
    db_debug = SessionLocal()
    try:
        print("DEBUG: Regions in DB right after creation:", [(r.region_id, r.region_name) for r in db_debug.query(Region).all()])
    finally:
        db_debug.close()

    # 2. CC maps route and vehicle to region
    resp = client.post(f"/control/regions/{region_id}/routes", json={"routes": [{"route_id": "CTA 1023", "route_name": "CTA 1023"}]})
    assert resp.status_code == 200, f"Failed mapping route: {resp.text}"
    
    resp = client.post(f"/control/regions/{region_id}/vehicles", json={"vehicles": ["BUS_001"]})
    assert resp.status_code == 200, f"Failed mapping vehicle: {resp.text}"
    
    resp = client.post(f"/control/regions/{region_id}/supervisors", json={"supervisors": ["supervisor_2"]})
    assert resp.status_code == 200, f"Failed mapping supervisor: {resp.text}"
    print("Mapppings saved successfully.")

    # 3. Supervisor Ahmed Hassan creates a duty assignment
    planned_date = datetime.date.today().isoformat()
    payload = {
        "region_id": region_id,
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "CTA 1023",
        "service_date": planned_date,
        "planned_start_time": "08:00:00",
        "planned_end_time": "10:00:00",
        "notes": "Test happy path duty assignment"
    }
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload)
    assert resp.status_code == 201, f"Failed creating assignment: {resp.text}"
    assignment = resp.json()
    assignment_id = assignment["assignment_id"]
    assert assignment["status"] == "scheduled"
    assert assignment["trip_id"] == "trip_1", "Should select existing GTFS trip_1"
    print("Assignment created successfully. ID:", assignment_id, "Trip ID:", assignment["trip_id"])

    # 5. Driver opens My Trips
    resp = client.get("/driver/driver_test_001/duties")
    assert resp.status_code == 200
    duties = resp.json()["assignments"]
    assert len(duties) == 1
    assert duties[0]["assignment_id"] == assignment_id
    assert duties[0]["status"] == "scheduled"
    print("Driver My Trips displays duty.")

    # 6. Driver starts trip
    resp = client.post(f"/driver/assignments/{assignment_id}/start")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    print("Driver starts trip. Status becomes active.")

    # 7. Driver sends location
    loc_payload = {
        "vehicle_id": "BUS_001",
        "driver_id": "driver_test_001",
        "assignment_id": assignment_id,
        "route_id": "CTA 1023",
        "trip_id": "trip_1",
        "timestamp": datetime.datetime.now().isoformat(),
        "lat": 30.045,
        "lon": 31.236,
        "speed": 35.0,
        "bearing": 120.0
    }
    resp = client.post("/vehicle/location", json=loc_payload)
    assert resp.status_code == 200, f"Location send failed: {resp.text}"
    print("Location payload accepted by backend.")

    # Check vehicle live state
    resp = client.get("/vehicles/live?vehicle_id=BUS_001")
    assert resp.status_code == 200
    live_states = resp.json()
    assert len(live_states) == 1
    # Check that assignment, driver, trip are mapped if supported
    print("Live state checked. Speed:", live_states[0]["speed"])

    # 8. Driver completes trip
    resp = client.post(f"/driver/assignments/{assignment_id}/complete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    print("Driver completes trip. Status becomes completed.")

    # Check that it moves to Trip History
    resp = client.get("/driver/driver_test_001/trip-history")
    assert resp.status_code == 200
    history = resp.json()["history"]
    assert len(history) == 1
    assert history[0]["assignment_id"] == assignment_id
    assert history[0]["status"] == "completed"
    print("Completed duty appears in Trip History.")

    # 9. Check that it doesn't show in active duties list anymore
    resp = client.get("/driver/driver_test_001/duties")
    assert resp.status_code == 200
    assert len(resp.json()["assignments"]) == 0
    print("Completed duty removed from active My Trips list.")

    print("\n--- Running Test Case B: Missing vehicle ---")
    payload_no_vehicle = payload.copy()
    payload_no_vehicle["vehicle_id"] = ""
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload_no_vehicle)
    assert resp.status_code == 400, "Should reject empty vehicle_id"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case C: Wrong region route ---")
    # Route "A-12 Express" is not mapped to Zone East
    payload_wrong_route = payload.copy()
    payload_wrong_route["route_id"] = "A-12 Express"
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload_wrong_route)
    assert resp.status_code == 400, "Should reject route not mapped to Zone East"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case D: Wrong region vehicle ---")
    # Vehicle "BUS_XYZ" is not mapped to Zone East
    payload_wrong_vehicle = payload.copy()
    payload_wrong_vehicle["vehicle_id"] = "BUS_XYZ"
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload_wrong_vehicle)
    assert resp.status_code == 400, "Should reject vehicle not mapped to Zone East"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case E: Driver overlap ---")
    # Reset for overlap testing
    seed_test_data()
    resp = client.post("/control/regions", json={"region_name": "Zone East", "description": "East Zone description", "active": True})
    assert resp.status_code == 201
    # Map mappings again
    client.post(f"/control/regions/{region_id}/routes", json={"routes": [{"route_id": "CTA 1023", "route_name": "CTA 1023"}]})
    client.post(f"/control/regions/{region_id}/vehicles", json={"vehicles": ["BUS_001", "BUS_002"]})
    client.post(f"/control/regions/{region_id}/supervisors", json={"supervisors": ["supervisor_2"]})
    
    # Create first assignment (08:00 - 10:00)
    client.post("/supervisor/supervisor_2/assignments", json=payload)
    
    # Create overlapping assignment for same driver (09:00 - 11:00) using a different vehicle
    payload_overlap = payload.copy()
    payload_overlap["planned_start_time"] = "09:00:00"
    payload_overlap["planned_end_time"] = "11:00:00"
    payload_overlap["vehicle_id"] = "BUS_002"
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload_overlap)
    assert resp.status_code == 400, "Should reject driver overlap"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case F: Vehicle overlap ---")
    # Create overlapping assignment for same vehicle (09:00 - 11:00) using a different driver
    db = SessionLocal()
    driver2 = db.query(User).filter(User.user_id == "driver_test_002").first()
    if not driver2:
        db.add(User(user_id="driver_test_002", name="Driver 2", role="Driver", status="active"))
    else:
        driver2.name = "Driver 2"
        driver2.role = "Driver"
        driver2.status = "active"
    db.commit()
    db.close()
    
    payload_overlap_vehicle = payload.copy()
    payload_overlap_vehicle["planned_start_time"] = "09:00:00"
    payload_overlap_vehicle["planned_end_time"] = "11:00:00"
    payload_overlap_vehicle["driver_id"] = "driver_test_002"
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload_overlap_vehicle)
    assert resp.status_code == 400, "Should reject vehicle overlap"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case G: Start completed duty ---")
    seed_test_data()
    resp = client.post("/control/regions", json={"region_name": "Zone East", "description": "East Zone description", "active": True})
    assert resp.status_code == 201
    # Setup mapping
    client.post(f"/control/regions/{region_id}/routes", json={"routes": [{"route_id": "CTA 1023", "route_name": "CTA 1023"}]})
    client.post(f"/control/regions/{region_id}/vehicles", json={"vehicles": ["BUS_001"]})
    client.post(f"/control/regions/{region_id}/supervisors", json={"supervisors": ["supervisor_2"]})
    
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload)
    asgn_id = resp.json()["assignment_id"]
    
    # Start and Complete the assignment
    client.post(f"/driver/assignments/{asgn_id}/start")
    loc_payload_g = {
        "vehicle_id": "BUS_001",
        "driver_id": "driver_test_001",
        "assignment_id": asgn_id,
        "route_id": "CTA 1023",
        "trip_id": "trip_1",
        "timestamp": datetime.datetime.now().isoformat(),
        "lat": 30.045,
        "lon": 31.236,
        "speed": 35.0,
        "bearing": 120.0
    }
    client.post("/vehicle/location", json=loc_payload_g)
    client.post(f"/driver/assignments/{asgn_id}/complete")
    
    # Try starting it again
    resp = client.post(f"/driver/assignments/{asgn_id}/start")
    assert resp.status_code == 400, "Should reject starting a completed assignment"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case H: Complete non-active duty ---")
    resp = client.post("/supervisor/supervisor_2/assignments", json=payload)
    asgn_id_scheduled = resp.json()["assignment_id"]
    
    # Try completing without starting
    resp = client.post(f"/driver/assignments/{asgn_id_scheduled}/complete")
    assert resp.status_code == 400, "Should reject completing a scheduled assignment"
    print("Rejected successfully (400).")

    print("\n--- Running Test Case I: Old simulation compatibility ---")
    # Send payload without assignment_id and trip_id
    old_payload = {
        "vehicle_id": "BUS_001",
        "route_id": "CTA 1023",
        "direction": 0,
        "timestamp": datetime.datetime.now().isoformat(),
        "lat": 30.044,
        "lon": 31.235,
        "speed": 40.0,
        "bearing": 90.0
    }
    resp = client.post("/vehicle/location", json=old_payload)
    assert resp.status_code == 200, f"Old simulation payload failed: {resp.text}"
    print("\n--- Running Test Case J: Full Supervisor Flow & Negative Region Checks ---")
    seed_test_data()
    # 2. Fetch supervisor assigned regions
    resp = client.get("/supervisor/supervisor_2/regions")
    assert resp.status_code == 200
    regions = resp.json()
    assert len(regions) > 0
    first_region_id = regions[0]["region_id"]
    print("Fetched supervisor regions. Selected first:", first_region_id)
    
    # 3. Fetch routes for that region
    resp = client.get(f"/supervisor/supervisor_2/routes?region_id={first_region_id}")
    assert resp.status_code == 200
    routes = resp.json()
    assert len(routes) > 0
    first_route_id = routes[0]["route_id"]
    
    # 4. Fetch vehicles for that region
    resp = client.get(f"/supervisor/supervisor_2/vehicles?region_id={first_region_id}")
    assert resp.status_code == 200
    vehicles = resp.json()
    assert len(vehicles) > 0
    first_vehicle_id = vehicles[0]
    
    # 5. Create assignment successfully
    test_payload = {
        "region_id": first_region_id,
        "driver_id": "driver_test_001",
        "vehicle_id": first_vehicle_id,
        "route_id": first_route_id,
        "service_date": datetime.date.today().isoformat(),
        "planned_start_time": "08:00:00",
        "planned_end_time": "10:00:00",
        "notes": "Test case J creation"
    }
    resp = client.post("/supervisor/supervisor_2/assignments", json=test_payload)
    assert resp.status_code == 201, f"Failed creating assignment in Test Case J: {resp.text}"
    print("Positive Test Case J Passed! Assignment created successfully.")

    # 6. Negative test: Try creating assignment with a region not assigned to supervisor
    invalid_payload = test_payload.copy()
    invalid_payload["region_id"] = "Invalid_Region_XYZ"
    resp = client.post("/supervisor/supervisor_2/assignments", json=invalid_payload)
    assert resp.status_code == 400
    
    # Let's also test when supervisor is not assigned to the region of the route:
    db = SessionLocal()
    try:
        # Create region Zone_West
        if not db.query(Region).filter(Region.region_id == "Zone_West").first():
            db.add(Region(region_id="Zone_West", region_name="Zone West", active=True))
        # Map Route 99 to Zone_West
        if not db.query(RegionRoute).filter(RegionRoute.route_id == "Route 99").first():
            db.add(RegionRoute(region_id="Zone_West", route_id="Route 99", route_name="Route 99", mode="Bus"))
        db.commit()
    finally:
        db.close()
        
    invalid_sup_payload = test_payload.copy()
    invalid_sup_payload["region_id"] = "Zone_West"
    invalid_sup_payload["route_id"] = "Route 99"
    resp = client.post("/supervisor/supervisor_2/assignments", json=invalid_sup_payload)
    assert resp.status_code == 400
    print("Negative Test Case J Passed! Correctly rejected supervisor assigning in unmapped region.")

    # 7. Route mode validation test
    print("\n--- Running Test Case K: Route mode validation ---")
    resp = client.post(f"/control/regions/{first_region_id}/routes", json={
        "routes": [
            {"route_id": "Route Metro 1", "route_name": "Cairo Metro Line 1", "mode": "Metro"}
        ]
    })
    assert resp.status_code == 400, f"Expected 400 for Metro route assignment, got {resp.status_code}: {resp.text}"
    print("Test Case K Passed! Non-bus route mapping was correctly rejected.")

    print("\n--- Running Test Case L: Proper GTFS Bus Route Management ---")
    db_clean = SessionLocal()
    try:
        db_clean.query(DriverAssignment).delete()
        db_clean.commit()
    finally:
        db_clean.close()

    # 1. Verify that GTFS bus routes are imported
    resp = client.get("/control-center/bus-routes")
    assert resp.status_code == 200, f"Failed: {resp.text}"
    bus_routes = resp.json()
    assert len(bus_routes) > 0, "No bus routes found"
    print("Found active bus routes:", [r["route_id"] for r in bus_routes])

    bus_route_ids = [r["route_id"] for r in bus_routes]
    assert "Route 8" in bus_route_ids, "Route 8 should be present"
    assert "CTA 1023" in bus_route_ids, "CTA 1023 should be present"

    # 2. Create region with routes
    test_reg_name = "Zone North"
    resp = client.post("/control/regions", json={
        "region_name": test_reg_name,
        "description": "North operational area",
        "active": True,
        "route_ids": ["Route 8", "CTA 1023"]
    })
    assert resp.status_code == 201, f"Failed: {resp.text}"
    region_north = resp.json()
    reg_north_id = region_north["region_id"]
    print("Region Zone North created with routes mapped:", reg_north_id)

    # 3. Check region detail endpoint
    resp = client.get(f"/control-center/regions/{reg_north_id}")
    assert resp.status_code == 200, f"Failed: {resp.text}"
    reg_detail = resp.json()
    assert "Route 8" in reg_detail["route_ids"]
    assert "CTA 1023" in reg_detail["route_ids"]
    print("Region detail routes checked successfully.")

    # 4. Sync region routes (deactivate CTA 1023, add Route 15)
    resp = client.put(f"/control/regions/{reg_north_id}", json={
        "region_name": test_reg_name,
        "description": "Updated North area",
        "active": True,
        "route_ids": ["Route 8", "Route 15"]
    })
    assert resp.status_code == 200, f"Failed: {resp.text}"

    resp = client.get(f"/control-center/regions/{reg_north_id}")
    reg_detail_updated = resp.json()
    assert "Route 8" in reg_detail_updated["route_ids"]
    assert "Route 15" in reg_detail_updated["route_ids"]
    assert "CTA 1023" not in reg_detail_updated["route_ids"]
    print("Region routes sync updated successfully.")

    # 5. Get mapped region routes
    resp = client.get(f"/regions/{reg_north_id}/routes?supervisor_id=supervisor_2")
    assert resp.status_code == 200, f"Failed: {resp.text}"
    region_routes = resp.json()
    reg_routes_ids = [r["route_id"] for r in region_routes]
    assert "Route 8" in reg_routes_ids
    assert "Route 15" in reg_routes_ids
    assert "CTA 1023" not in reg_routes_ids
    print("GET /regions/{region_id}/routes returned mapped routes successfully.")

    # 6. Map supervisor_2 to Zone North for validation tests
    client.post(f"/control/regions/{reg_north_id}/supervisors", json={"supervisors": ["supervisor_2"]})
    client.post(f"/control/regions/{reg_north_id}/vehicles", json={"vehicles": ["BUS_001"]})

    # 7. Assignment validation checks
    valid_payload = {
        "region_id": reg_north_id,
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "Route 8",
        "service_date": datetime.date.today().isoformat(),
        "planned_start_time": "08:00:00",
        "planned_end_time": "10:00:00"
    }
    resp = client.post("/supervisor/supervisor_2/assignments", json=valid_payload)
    assert resp.status_code == 201, f"Failed to create valid assignment: {resp.text}"
    print("Valid assignment creation passed.")

    invalid_route_payload = valid_payload.copy()
    invalid_route_payload["route_id"] = "CTA 1023"
    resp = client.post("/supervisor/supervisor_2/assignments", json=invalid_route_payload)
    assert resp.status_code == 400, "Should reject unmapped route"

    db = SessionLocal()
    try:
        from models.route import Route as DBRoute
        if not db.query(DBRoute).filter(DBRoute.route_id == "Route Metro 2").first():
            db.add(DBRoute(route_id="Route Metro 2", route_name="Cairo Metro Line 2"))
        db.commit()
    finally:
        db.close()

    invalid_bus_payload = valid_payload.copy()
    invalid_bus_payload["route_id"] = "Route Metro 2"
    resp = client.post("/supervisor/supervisor_2/assignments", json=invalid_bus_payload)
    assert resp.status_code == 400, "Should reject non-bus route"
    print("Negative assignment validations passed.")

    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
