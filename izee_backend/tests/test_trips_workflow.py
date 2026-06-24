import urllib.request
import json
import datetime
import sys
import os

# Insert backend root directory to path so imports work cleanly
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, method="GET", body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            resp_body = res.read().decode("utf-8")
            return res.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(resp_body)
        except Exception:
            return e.code, {"detail": resp_body}
    except Exception as e:
        print(f"Request to {url} failed: {e}")
        return 500, {"detail": str(e)}

def cleanup_database():
    try:
        from database.connection import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        
        # Cleanup driver_assignments referencing test regions
        db.execute(text("""
            DELETE FROM driver_assignments 
            WHERE region_id IN ('zone_east', 'zone_west', 'zone_north', 'Zone_East', 'Zone_West', 'Zone_North')
        """))
        db.execute(text("""
            DELETE FROM driver_route_assignments 
            WHERE region_id IN ('zone_east', 'zone_west', 'zone_north', 'Zone_East', 'Zone_West', 'Zone_North')
        """))
        
        # Cleanup test assignments by driver
        db.execute(text("""
            DELETE FROM driver_assignments 
            WHERE driver_id IN ('driver_test_001', 'driver_test_002')
        """))
        db.execute(text("""
            DELETE FROM driver_route_assignments 
            WHERE driver_id IN ('driver_test_001', 'driver_test_002')
        """))
        
        # Cleanup test assignments by vehicle
        db.execute(text("""
            DELETE FROM driver_assignments 
            WHERE vehicle_id IN ('BUS_001', 'BUS_002', 'V-001')
        """))
        db.execute(text("""
            DELETE FROM driver_route_assignments 
            WHERE vehicle_id IN ('BUS_001', 'BUS_002', 'V-001')
        """))
        
        # Cleanup driver mappings for test drivers
        db.execute(text("""
            DELETE FROM region_driver_mappings 
            WHERE driver_id IN ('driver_test_001', 'driver_test_002')
        """))
        
        # Cleanup ONLY the test regions and their mappings so the tests run cleanly
        for rid in ["zone_east", "zone_west", "zone_north", "Zone_East", "Zone_West", "Zone_North"]:
            db.execute(text("DELETE FROM supervisor_regions WHERE region_id = :rid"), {"rid": rid})
            db.execute(text("DELETE FROM region_routes WHERE region_id = :rid"), {"rid": rid})
            db.execute(text("DELETE FROM region_vehicles WHERE region_id = :rid"), {"rid": rid})
            db.execute(text("DELETE FROM region_route_mappings WHERE region_id = :rid"), {"rid": rid})
            db.execute(text("DELETE FROM region_driver_mappings WHERE region_id = :rid"), {"rid": rid})
            db.execute(text("DELETE FROM regions WHERE region_id = :rid"), {"rid": rid})
            
        db.execute(text("DELETE FROM regions WHERE region_name IN ('Zone North', 'Zone East Test')"))
            
        db.commit()
        db.close()
        print("Pre-existing test assignments and test regions cleaned up via raw SQL.")
    except Exception as e:
        print(f"Database cleanup warning: {e}")

def run_tests():
    print("=== STARTING WORKFLOW TESTS ===")
    
    # Check if backend is alive
    status, res = make_request("/")
    if status != 200:
        print("Backend server is not running or unreachable. Please start it first.")
        sys.exit(1)
    print("Backend server is active.")
    
    cleanup_database()

    today_date = datetime.date.today().isoformat()
    
    # Ensure Zone East exists
    status, regions = make_request("/control/regions")
    has_east = any(r["region_id"] == "zone_east" for r in regions)
    if not has_east:
        print("Creating region: zone_east...")
        status, reg = make_request("/control/regions", "POST", {
            "region_id": "zone_east",
            "region_name": "Zone East Test",
            "description": "Zone East Area",
            "active": True
        })
        assert status in (200, 201), f"Region creation failed: {reg}"
    
    # Assign route CTA 1023 to Zone East
    print("Assigning route CTA 1023 to Zone East...")
    status, out = make_request("/control/regions/zone_east/routes", "POST", {
        "routes": [{"route_id": "CTA 1023", "route_name": "CTA 1023", "mode": "Bus"}]
    })
    assert status == 200, f"Route assignment failed: {out}"

    # Assign vehicle BUS_001 to Zone East
    print("Assigning vehicle BUS_001 to Zone East...")
    status, out = make_request("/control/regions/zone_east/vehicles", "POST", {
        "vehicles": ["BUS_001"]
    })
    assert status == 200, f"Vehicle assignment failed: {out}"

    # Assign supervisor supervisor_2 to Zone East
    print("Assigning supervisor supervisor_2 to Zone East...")
    status, out = make_request("/control/regions/zone_east/supervisors", "POST", {
        "supervisors": ["supervisor_2"]
    })
    assert status == 200, f"Supervisor assignment failed: {out}"

    # Assign drivers to Zone East
    print("Assigning drivers to Zone East...")
    status, out = make_request("/control/regions/zone_east/drivers", "POST", {
        "drivers": ["driver_test_001", "driver_test_002"]
    })
    assert status == 200, f"Drivers assignment failed: {out}"

    # Verify supervisor regions mapping
    print("Verifying supervisor_2 region assignments...")
    status, regions = make_request("/supervisor/supervisor_2/regions")
    assert status == 200
    assert any(r["region_id"] == "zone_east" for r in regions), "supervisor_2 should be mapped to zone_east"

    # --- TEST B: Missing vehicle ---
    print("\nTEST B: Missing vehicle...")
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_east",
        "driver_id": "driver_test_001",
        "route_id": "CTA 1023",
        "service_date": today_date,
        "planned_start_time": "08:00",
        "planned_end_time": "10:00",
    })
    assert status == 400, f"Expected 400, got {status}: {err}"
    assert "vehicle_id" in err["detail"].lower()
    print("TEST B Passed.")

    # --- TEST C: Wrong region route ---
    print("\nTEST C: Wrong region route...")
    # Attempting to assign Route 22 (which belongs to zone_west) to zone_east
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_east",
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "Route 22",
        "service_date": today_date,
        "planned_start_time": "08:00",
        "planned_end_time": "10:00",
    })
    assert status == 400, f"Expected 400, got {status}: {err}"
    assert "route" in err["detail"].lower()
    print("TEST C Passed.")

    # --- TEST D: Wrong region vehicle ---
    print("\nTEST D: Wrong region vehicle...")
    # Attempting to assign vehicle V-001 (which belongs to zone_west) to zone_east
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_east",
        "driver_id": "driver_test_001",
        "vehicle_id": "V-001",
        "route_id": "CTA 1023",
        "service_date": today_date,
        "planned_start_time": "08:00",
        "planned_end_time": "10:00",
    })
    assert status == 400, f"Expected 400, got {status}: {err}"
    assert "vehicle" in err["detail"].lower()
    print("TEST D Passed.")

    # --- TEST A: Happy path - Part 1: Supervisor assigns ---
    print("\nTEST A (Happy Path): Supervisor Ahmed Hassan creates duty assignment...")
    status, assignment = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_east",
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "CTA 1023",
        "service_date": today_date,
        "planned_start_time": "08:00",
        "planned_end_time": "10:00",
        "trip_id": None
    })
    assert status == 200 or status == 201, f"Happy path assignment failed: {assignment}"
    assignment_id = assignment["assignment_id"]
    trip_id = assignment["trip_id"]
    assert assignment_id is not None
    assert trip_id is not None
    assert assignment["status"] == "scheduled"
    print(f"Assignment created. assignment_id={assignment_id}, trip_id={trip_id}")

    # --- TEST E: Driver overlap ---
    print("\nTEST E: Driver overlap check...")
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_east",
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "CTA 1023",
        "service_date": today_date,
        "planned_start_time": "09:00",
        "planned_end_time": "11:00",
    })
    assert status == 400, f"Expected 400, got {status}: {err}"
    assert "driver has an overlapping duty" in err["detail"].lower()
    print("TEST E Passed.")

    # --- TEST F: Vehicle overlap ---
    print("\nTEST F: Vehicle overlap check...")
    # Use different driver, same vehicle, overlapping times
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_east",
        "driver_id": "driver_test_002",
        "vehicle_id": "BUS_001",
        "route_id": "CTA 1023",
        "service_date": today_date,
        "planned_start_time": "09:00",
        "planned_end_time": "11:00",
    })
    assert status == 400, f"Expected 400, got {status}: {err}"
    assert "vehicle has an overlapping duty" in err["detail"].lower()
    print("TEST F Passed.")

    # --- TEST A: Happy path - Part 2: Driver sees duty ---
    print("\nTEST A (Happy Path): Driver checks My Trips/duties...")
    status, res = make_request("/driver/driver_test_001/duties")
    assert status == 200
    duties = res["assigned_trips"]
    assert any(d["assignment_id"] == assignment_id for d in duties), "Assignment should show up in driver duties"
    active_duty = next(d for d in duties if d["assignment_id"] == assignment_id)
    assert active_duty["status"] == "scheduled"
    assert active_duty["vehicle_id"] == "BUS_001"
    assert active_duty["route_id"] == "CTA 1023"
    assert active_duty["trip_id"] == trip_id
    print("Driver sees duty successfully.")

    # --- TEST H: Complete non-active duty ---
    print("\nTEST H: Complete non-active duty check...")
    status, err = make_request(f"/driver/assignments/{assignment_id}/complete", "POST")
    assert status == 400, f"Expected 400, got {status}: {err}"
    print("TEST H Passed.")

    # --- TEST A: Happy path - Part 3: Driver starts trip ---
    print("\nTEST A (Happy Path): Driver starts trip...")
    status, res = make_request(f"/driver/assignments/{assignment_id}/start", "POST")
    assert status == 200, f"Start assignment failed: {res}"
    
    # Check status is now active
    status, res = make_request("/driver/driver_test_001/duties")
    d = next(d for d in res["assigned_trips"] if d["assignment_id"] == assignment_id)
    assert d["status"] == "active"
    print("Driver started trip successfully.")

    # --- TEST A: Happy path - Part 4: Driver sends location ---
    print("\nTEST A (Happy Path): Driver sends vehicle location payload...")
    status, res = make_request("/vehicle/location", "POST", {
        "vehicle_id": "BUS_001",
        "driver_id": "driver_test_001",
        "assignment_id": assignment_id,
        "route_id": "CTA 1023",
        "trip_id": trip_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "location": {"lat": 30.0444, "lon": 31.2357},
        "speed": 12.5,
        "bearing": 90.0,
    })
    assert status == 200, f"Location ingestion failed: {res}"
    print("Location ingested successfully.")

    # --- TEST I: Old simulation compatibility ---
    print("\nTEST I: Old simulation AVL/location payload compatibility...")
    status, res = make_request("/vehicle/location", "POST", {
        "vehicle_id": "BUS_001",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "lat": 30.05,
        "lon": 31.25,
        "speed": 8.0,
        "bearing": 180.0,
    })
    assert status == 200 or status == 201, f"Old simulation location compatibility failed: {res}"
    print("TEST I Passed.")

    # --- TEST A: Happy path - Part 5: Driver completes trip ---
    print("\nTEST A (Happy Path): Driver completes trip...")
    status, res = make_request(f"/driver/assignments/{assignment_id}/complete", "POST")
    assert status == 200, f"Complete assignment failed: {res}"

    # Check that duty is no longer in duties/active list
    status, res = make_request("/driver/driver_test_001/duties")
    duties = res["assigned_trips"]
    assert not any(d["assignment_id"] == assignment_id for d in duties), "Completed assignment should not show in scheduled/active duties list"

    # Check that it appears in Trip History
    status, res = make_request("/driver/driver_test_001/trip-history")
    assert status == 200
    history = res["history"]
    assert any(h["assignment_id"] == assignment_id for h in history), "Completed assignment must show in Trip History"
    hist_entry = next(h for h in history if h["assignment_id"] == assignment_id)
    assert hist_entry["status"] == "completed"
    print("Driver completed trip and verified in History.")

    # --- TEST G: Start completed duty ---
    print("\nTEST G: Start completed duty check...")
    status, err = make_request(f"/driver/assignments/{assignment_id}/start", "POST")
    assert status == 400, f"Expected 400, got {status}: {err}"
    print("TEST G Passed.")

    # --- TEST J: Unmap Vehicle mapping and verify ---
    print("\nTEST J: Vehicle unmapping behavior...")
    # First, verify BUS_001 is mapped to zone_east
    status, vehicles = make_request("/control/regions/zone_east/vehicles")
    vehicle_ids = [v["vehicle_id"] for v in vehicles]
    assert "BUS_001" in vehicle_ids, f"BUS_001 should be in {vehicle_ids}"
    
    # Unmap BUS_001 by mapping only vehicle 'BUS_002' instead
    status, out = make_request("/control/regions/zone_east/vehicles", "POST", {
        "vehicles": ["BUS_002"]
    })
    assert status == 200, f"Vehicle mapping update failed: {out}"
    
    # Verify BUS_001 is no longer returned as active region vehicle
    status, vehicles = make_request("/control/regions/zone_east/vehicles")
    vehicle_ids = [v["vehicle_id"] for v in vehicles]
    assert "BUS_001" not in vehicle_ids, f"BUS_001 should have been unmapped, got {vehicle_ids}"
    assert "BUS_002" in vehicle_ids, f"BUS_002 should be mapped, got {vehicle_ids}"
    
    # Restore BUS_001 for other tests
    make_request("/control/regions/zone_east/vehicles", "POST", {"vehicles": ["BUS_001", "BUS_002"]})
    print("TEST J Passed.")

    # --- TEST K: Route mode validation check ---
    print("\nTEST K: Route mode validation (non-bus routes rejected)...")
    # Try mapping a Metro / BRT route to supervisor region
    status, err = make_request("/control/regions/zone_east/routes", "POST", {
        "routes": [
            {"route_id": "Route Metro 1", "route_name": "Cairo Metro Line 1", "mode": "Metro"}
        ]
    })
    assert status == 400, f"Expected 400 for Metro route mapping, got {status}: {err}"
    print("TEST K Passed.")

    # --- TEST L: Proper GTFS Bus Route Management ---
    print("\nTEST L: Proper GTFS Bus Route Management...")
    # 1. Fetch assignable bus routes
    status, bus_routes = make_request("/control-center/bus-routes")
    assert status == 200, f"Failed: {bus_routes}"
    assert len(bus_routes) > 0, "No bus routes found"
    
    bus_route_ids = [r["route_id"] for r in bus_routes]
    assert "Route 8" in bus_route_ids
    assert "CTA 1023" in bus_route_ids
    
    # 2. Create region with routes
    status, region_north = make_request("/control/regions", "POST", {
        "region_id": "zone_north",
        "region_name": "Zone North",
        "description": "North operational area",
        "active": True,
        "route_ids": ["Route 8", "CTA 1023"]
    })
    assert status in (200, 201), f"Failed: {region_north}"
    
    # 3. Check region detail endpoint
    status, reg_detail = make_request("/control-center/regions/zone_north")
    assert status == 200, f"Failed: {reg_detail}"
    assert "Route 8" in reg_detail["route_ids"]
    assert "CTA 1023" in reg_detail["route_ids"]
    
    # 4. Sync region routes (deactivate CTA 1023, add Route 15)
    status, reg_updated = make_request("/control/regions/zone_north", "PUT", {
        "region_name": "Zone North",
        "description": "Updated North area",
        "active": True,
        "route_ids": ["Route 8", "Route 15"]
    })
    assert status == 200, f"Failed: {reg_updated}"
    
    status, reg_detail_updated = make_request("/control-center/regions/zone_north")
    assert status == 200
    assert "Route 8" in reg_detail_updated["route_ids"]
    assert "Route 15" in reg_detail_updated["route_ids"]
    assert "CTA 1023" not in reg_detail_updated["route_ids"]
    
    # Unassign drivers from Zone East first
    make_request("/control/regions/zone_east/drivers", "POST", {"drivers": []})

    # 6. Map supervisor_2 to Zone North for validation tests
    make_request("/control/regions/zone_north/supervisors", "POST", {"supervisors": ["supervisor_2"]})
    make_request("/control/regions/zone_north/vehicles", "POST", {"vehicles": ["BUS_001"]})
    make_request("/control/regions/zone_north/drivers", "POST", {"drivers": ["driver_test_001", "driver_test_002"]})
    
    # 5. Get mapped region routes
    status, region_routes = make_request("/regions/zone_north/routes?supervisor_id=supervisor_2")
    assert status == 200, f"Failed: {region_routes}"
    reg_routes_ids = [r["route_id"] for r in region_routes]
    assert "Route 8" in reg_routes_ids
    assert "Route 15" in reg_routes_ids
    assert "CTA 1023" not in reg_routes_ids
    
    # 7. Assignment validation checks
    valid_payload = {
        "region_id": "zone_north",
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "Route 8",
        "service_date": datetime.date.today().isoformat(),
        "planned_start_time": "08:00:00",
        "planned_end_time": "10:00:00"
    }
    status, asg = make_request("/supervisor/supervisor_2/assignments", "POST", valid_payload)
    assert status == 200 or status == 201, f"Failed to create valid assignment: {asg}"
    
    # Try creating assignment with unmapped route CTA 1023 (was removed during PUT sync)
    invalid_route_payload = valid_payload.copy()
    invalid_route_payload["route_id"] = "CTA 1023"
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", invalid_route_payload)
    assert status == 400, f"Expected 400, got {status}: {err}"
    
    # Try creating assignment with non-bus route (Metro)
    invalid_bus_payload = valid_payload.copy()
    invalid_bus_payload["route_id"] = "Route Metro 1"
    status, err = make_request("/supervisor/supervisor_2/assignments", "POST", invalid_bus_payload)
    assert status == 400, f"Expected 400, got {status}: {err}"
    
    print("TEST L Passed.")

    # --- TEST M: Incident Reporting, isolation, transmission & replacement vehicle ---
    print("\nTEST M: Incident reporting, isolation, transmission & replacement vehicle...")
    
    # 1. Create a scheduled assignment for BUS_001
    today_date = datetime.date.today().isoformat()
    status, asg = make_request("/supervisor/supervisor_2/assignments", "POST", {
        "region_id": "zone_north",
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_001",
        "route_id": "Route 8",
        "service_date": today_date,
        "planned_start_time": "12:00:00",
        "planned_end_time": "14:00:00"
    })
    assert status in (200, 201), f"Failed to create scheduled assignment: {asg}"
    asg_id = asg["assignment_id"]

    # Start driver assignment so it is ACTIVE (required for location reports)
    status, start_res = make_request(f"/driver/assignments/{asg_id}/start", "POST")
    assert status == 200, f"Failed to start assignment: {start_res}"
    
    # 2. Report breakdown incident for BUS_001
    status, inc = make_request("/incidents", "POST", {
        "category": "Vehicle Breakdown",
        "severity": "critical",
        "status": "new",
        "vehicle_id": "BUS_001",
        "route_id": "Route 8",
        "driver_name": "driver_test_001",
        "lat": 30.0444,
        "lon": 31.2357,
        "location_label": "Nasr City",
        "details": "Engine smoke, need backup vehicle.",
        "source": "passenger_app"
    })
    assert status in (200, 201), f"Failed to report incident: {inc}"
    inc_id = inc["incident_id"]
    
    # 3. Verify it is visible to Supervisor but NOT Control Center
    status, sup_incidents = make_request("/incidents?scope=supervisor")
    assert status == 200
    assert any(i["incident_id"] == inc_id for i in sup_incidents["incidents"]), "Incident should be visible to supervisor"
    
    status, cc_incidents = make_request("/incidents?scope=control_center")
    assert status == 200
    assert not any(i["incident_id"] == inc_id for i in cc_incidents["incidents"]), "Incident should NOT be visible to control center before transmission"
    
    # 4. Supervisor takes action: resolves breakdown, deploys replacement vehicle BUS_002, transmits to CC
    status, action_res = make_request(f"/incidents/{inc_id}/action", "POST", {
        "status": "resolved",
        "transmitted_to_control": True,
        "replacement_vehicle_id": "BUS_002"
    })
    assert status == 200, f"Failed to update incident action: {action_res}"
    
    # 5. Verify the assignment's vehicle was updated to BUS_002
    status, duties = make_request("/driver/driver_test_001/duties")
    assert status == 200
    asg_entry = next((d for d in duties["assigned_trips"] if d["assignment_id"] == asg_id), None)
    assert asg_entry is not None, "Driver assignment should still exist"
    assert asg_entry["vehicle_id"] == "BUS_002", f"Expected vehicle to be updated to BUS_002, got {asg_entry['vehicle_id']}"
    
    # 7. Create a delay incident to test the supervisor action and speed monitoring
    status, delay_inc = make_request("/incidents", "POST", {
        "category": "Delay",
        "severity": "warning",
        "status": "new",
        "vehicle_id": "BUS_002",
        "route_id": "Route 8",
        "details": "Passenger reporting delay due to traffic",
        "source": "passenger_app"
    })
    assert status == 200
    delay_inc_id = delay_inc["incident_id"]

    # Retrieve live state to verify speed before action
    status, loc_res = make_request("/driver/location", "POST", {
        "assignment_id": asg_id,
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_002",
        "lat": 30.05,
        "lon": 31.25,
        "speed": 10.0,
        "bearing": 90.0,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    assert status == 200

    # Supervisor triggers Speed Up Driver action
    status, action_res = make_request(f"/incidents/{delay_inc_id}/action", "POST", {
        "speed_up": True
    })
    assert status == 200, f"Failed to trigger Speed Up Driver action: {action_res}"

    # Verify a ControlMessage was created for the driver
    status, messages = make_request("/messages")
    assert status == 200
    driver_msgs = [m for m in messages["messages"] if m["recipient_type"] == "driver" and m["recipient_id"] == "driver_test_001"]
    assert len(driver_msgs) > 0, "ControlMessage to speed up should be sent to the driver"
    assert "reported as delayed" in driver_msgs[0]["body"]

    # Driver sends next location update with same speed (no acceleration)
    status, loc_res_no_accel = make_request("/driver/location", "POST", {
        "assignment_id": asg_id,
        "driver_id": "driver_test_001",
        "vehicle_id": "BUS_002",
        "lat": 30.06,
        "lon": 31.26,
        "speed": 10.0,
        "bearing": 90.0,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    assert status == 200

    # Verify incident was transmitted to Control Center automatically
    status, cc_incidents_chk = make_request("/incidents?scope=control_center")
    assert status == 200
    assert any(i["incident_id"] == delay_inc_id for i in cc_incidents_chk["incidents"]), "Incident should be transmitted to CC when no acceleration happens"

    # Verify Control Center and Supervisor messages were created
    status, messages_after = make_request("/messages")
    assert status == 200
    cc_alert_msgs = [m for m in messages_after["messages"] if m["recipient_type"] == "control_center"]
    assert len(cc_alert_msgs) > 0, "Alert message to CC should be sent"
    assert "did not accelerate" in cc_alert_msgs[0]["body"]

    sv_alert_msgs = [m for m in messages_after["messages"] if m["recipient_type"] == "supervisor"]
    assert len(sv_alert_msgs) > 0, "Alert message to supervisor should be sent"
    assert sv_alert_msgs[0]["recipient_id"] == "supervisor_2"

    print("TEST M Passed.")

    # --- TEST N: Service Checks ---
    print("\nTEST N: Service Checks...")
    status, svc_res = make_request("/service-checks", "POST", {
        "vehicle_id": "BUS_002",
        "rating": 4,
        "checks": {
            "Vehicle Cleanliness": True,
            "Driver Behavior": True
        },
        "notes": "Good clean ride",
        "recommend_driver_training": False,
        "recommend_vehicle_maintenance": False,
        "commend_excellent_service": True,
        "source": "supervisor_app"
    })
    assert status == 201, f"Failed to create service check: {svc_res}"
    svc_id = svc_res["incident_id"]
    assert svc_id is not None

    status, list_res = make_request("/service-checks")
    assert status == 200
    assert any(c["incident_id"] == svc_id for c in list_res["service_checks"]), "Service check should be in service-checks list"
    
    # Verify it maps correct route_id from the active assignment (BUS_002 is assigned to Route 8)
    matched_svc = next(c for c in list_res["service_checks"] if c["incident_id"] == svc_id)
    assert matched_svc["route_id"] == "Route 8", f"Expected Route 8, got {matched_svc['route_id']}"
    assert matched_svc["raw_payload"]["rating"] == 4
    assert matched_svc["raw_payload"]["checks"]["Vehicle Cleanliness"] is True
    print("TEST N Passed.")

    print("\nALL WORKFLOW API TESTS PASSED SUCCESSFULLY!")
    cleanup_database()

def test_workflow():
    run_tests()

if __name__ == "__main__":
    run_tests()
