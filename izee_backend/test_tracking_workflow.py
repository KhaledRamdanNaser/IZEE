import datetime

from fastapi.testclient import TestClient

from database.connection import SessionLocal
from main import app
from models.transit_observation import TransitObservation
from models.trips_workflow import (
    DriverAssignment,
    Region,
    RegionDriverMapping,
    RegionRoute,
    RegionRouteMapping,
    RegionVehicle,
    SupervisorRegion,
    User,
    OperationalRoute,
)
from models.vehicle_live_state import VehicleLiveState


client = TestClient(app)


def seed_tracking_data():
    db = SessionLocal()
    try:
        db.query(TransitObservation).delete()
        db.query(VehicleLiveState).delete()
        db.query(DriverAssignment).delete()
        db.query(RegionDriverMapping).delete()
        db.query(RegionRouteMapping).delete()
        db.query(RegionVehicle).delete()
        db.query(RegionRoute).delete()
        db.query(SupervisorRegion).delete()
        db.query(Region).delete()
        db.query(User).delete()

        db.add(Region(region_id="Zone_East", region_name="Zone East", active=True))
        db.add(SupervisorRegion(supervisor_id="supervisor_2", region_id="Zone_East"))
        db.add(User(user_id="supervisor_2", name="Supervisor", role="Supervisor", status="active"))
        db.add(User(user_id="driver_1", name="Driver 1", role="Driver", status="active"))
        db.add(User(user_id="driver_2", name="Driver 2", role="Driver", status="active"))
        db.add(RegionDriverMapping(region_id="Zone_East", driver_id="driver_1", active=True))
        db.add(RegionDriverMapping(region_id="Zone_East", driver_id="driver_2", active=True))
        op_route = db.query(OperationalRoute).filter(OperationalRoute.route_id == "Route 8").first()
        if op_route is None:
            db.add(OperationalRoute(route_id="Route 8", route_short_name="Route 8", mode="bus", is_active=True))
        else:
            op_route.mode = "bus"
            op_route.is_active = True
        db.add(RegionRoute(region_id="Zone_East", route_id="Route 8", route_name="Route 8", mode="Bus"))
        db.add(RegionRouteMapping(region_id="Zone_East", route_id="Route 8", active=True))
        db.add(RegionVehicle(region_id="Zone_East", vehicle_id="BUS_001"))
        db.add(RegionVehicle(region_id="Zone_East", vehicle_id="BUS_002"))
        db.add(
            DriverAssignment(
                assignment_id="ASGN_ACTIVE",
                supervisor_id="supervisor_2",
                region_id="Zone_East",
                driver_id="driver_1",
                vehicle_id="BUS_001",
                route_id="Route 8",
                route_name="Route 8",
                trip_id="TRIP_ACTIVE",
                service_date="2026-06-19",
                planned_start_time="08:00:00",
                planned_end_time="10:00:00",
                status="active",
            )
        )
        db.add(
            DriverAssignment(
                assignment_id="ASGN_SCHEDULED",
                supervisor_id="supervisor_2",
                region_id="Zone_East",
                driver_id="driver_2",
                vehicle_id="BUS_002",
                route_id="Route 8",
                route_name="Route 8",
                trip_id="TRIP_SCHEDULED",
                service_date="2026-06-19",
                planned_start_time="10:00:00",
                planned_end_time="12:00:00",
                status="scheduled",
            )
        )
        db.commit()
    finally:
        db.close()


def location_payload(**overrides):
    payload = {
        "assignment_id": "ASGN_ACTIVE",
        "trip_id": "TRIP_ACTIVE",
        "driver_id": "driver_1",
        "vehicle_id": "BUS_001",
        "route_id": "Route 8",
        "lat": 30.123,
        "lng": 31.456,
        "speed": 35,
        "heading": 120,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


def run_tests():
    seed_tracking_data()

    resp = client.post("/driver/location", json=location_payload())
    assert resp.status_code == 200, resp.text

    resp = client.post(
        "/driver/location",
        json=location_payload(
            assignment_id="ASGN_SCHEDULED",
            trip_id="TRIP_SCHEDULED",
            driver_id="driver_2",
            vehicle_id="BUS_002",
        ),
    )
    assert resp.status_code == 400, resp.text

    resp = client.post("/driver/location", json=location_payload(driver_id="driver_2"))
    assert resp.status_code == 403, resp.text

    resp = client.post(
        "/driver/location",
        json=location_payload(lat=30.555, lng=31.777, timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    assert resp.status_code == 200, resp.text

    db = SessionLocal()
    try:
        state = db.query(VehicleLiveState).filter(VehicleLiveState.vehicle_id == "BUS_001").first()
        assert state is not None
        assert state.matched_lat == 30.555
        assert state.matched_lon == 31.777
    finally:
        db.close()

    resp = client.get("/passenger/routes/Route 8/vehicles")
    assert resp.status_code == 200, resp.text
    vehicles = resp.json()
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "BUS_001"
    assert vehicles[0]["status"] == "active"

    db = SessionLocal()
    try:
        assignment = db.query(DriverAssignment).filter(DriverAssignment.assignment_id == "ASGN_ACTIVE").first()
        assignment.status = "completed"
        db.commit()
    finally:
        db.close()

    resp = client.get("/passenger/routes/Route 8/vehicles")
    assert resp.status_code == 200, resp.text
    assert resp.json()[0]["location_status"] == "unavailable"

    db = SessionLocal()
    try:
        assignment = db.query(DriverAssignment).filter(DriverAssignment.assignment_id == "ASGN_ACTIVE").first()
        assignment.status = "active"
        state = db.query(VehicleLiveState).filter(VehicleLiveState.vehicle_id == "BUS_001").first()
        state.timestamp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=90)).isoformat()
        db.commit()
    finally:
        db.close()

    resp = client.get("/passenger/routes/Route 8/vehicles")
    assert resp.status_code == 200, resp.text
    assert resp.json()[0]["location_status"] == "stale"

    db = SessionLocal()
    try:
        state = db.query(VehicleLiveState).filter(VehicleLiveState.vehicle_id == "BUS_001").first()
        state.timestamp = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)).isoformat()
        db.commit()
    finally:
        db.close()

    resp = client.get("/passenger/routes/Route 8/vehicles")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    print("Tracking workflow tests passed.")


if __name__ == "__main__":
    run_tests()
