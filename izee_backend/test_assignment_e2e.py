"""
End-to-end test for the Supervisor Assignment creation flow.
Run from repo_review_izee directory: python test_assignment_e2e.py
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import date, timedelta

BASE = "http://127.0.0.1:8000"
SUPERVISOR_ID = "supervisor_2"  # matches login: SUP-2024-089

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"

def get(path):
    try:
        r = urllib.request.urlopen(BASE + path, timeout=8)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return None, str(e)

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        r = urllib.request.urlopen(req, timeout=8)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return None, str(e)

errors = []

def check(label, cond, actual=""):
    if cond:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}  (got: {actual})")
        errors.append(label)

print()
print("=" * 60)
print(f"  ASSIGNMENT E2E TEST  supervisor={SUPERVISOR_ID}")
print("=" * 60)

# ── 1. Supervisor region ──────────────────────────────────────
print("\n[1] GET /supervisor/{id}/region")
status, data = get(f"/supervisor/{SUPERVISOR_ID}/region")
print(f"    status={status}  data={data}")
check("status 200", status == 200, status)
region_id = data.get("region_id") if isinstance(data, dict) else None
check("region_id present", region_id is not None, data)
check("region_id == Zone_East", region_id == "Zone_East", region_id)

# ── 2. Routes for region ──────────────────────────────────────
print(f"\n[2] GET /supervisor/{SUPERVISOR_ID}/routes?region_id={region_id}")
status, routes = get(f"/supervisor/{SUPERVISOR_ID}/routes?region_id={region_id}")
print(f"    status={status}  routes={routes}")
check("routes status 200", status == 200, status)
route_ids = [r["route_id"] for r in routes] if isinstance(routes, list) else []
check("Route 8 in routes", "Route 8" in route_ids, route_ids)
check("CTA 1023 in routes", "CTA 1023" in route_ids, route_ids)

# ── 3. Vehicles for region ────────────────────────────────────
print(f"\n[3] GET /supervisor/{SUPERVISOR_ID}/vehicles?region_id={region_id}")
status, vehicles = get(f"/supervisor/{SUPERVISOR_ID}/vehicles?region_id={region_id}")
print(f"    status={status}  vehicles={vehicles}")
check("vehicles status 200", status == 200, status)
vehicle_ids = [
    v["vehicle_id"] if isinstance(v, dict) else str(v)
    for v in (vehicles if isinstance(vehicles, list) else [])
]
check("V-001 in vehicles", "V-001" in vehicle_ids, vehicle_ids)
check("BUS_001 in vehicles", "BUS_001" in vehicle_ids, vehicle_ids)

# ── 4. Drivers ────────────────────────────────────────────────
print(f"\n[4] GET /supervisor/{SUPERVISOR_ID}/drivers")
status, drivers_resp = get(f"/supervisor/{SUPERVISOR_ID}/drivers")
print(f"    status={status}  drivers={drivers_resp}")
check("drivers status 200", status == 200, status)
# Real backend wraps in {status, drivers: [...]}
if isinstance(drivers_resp, dict) and "drivers" in drivers_resp:
    drivers_list = drivers_resp["drivers"]
elif isinstance(drivers_resp, list):
    drivers_list = drivers_resp
else:
    drivers_list = []
driver_ids = [d["driver_id"] for d in drivers_list if isinstance(d, dict)]
check("driver_test_001 available", "driver_test_001" in driver_ids, driver_ids)

# ── 5. Create assignment ──────────────────────────────────────
service_date = (date.today() + timedelta(days=3)).isoformat()
payload = {
    "region_id":           region_id or "Zone_East",
    "supervisor_id":       SUPERVISOR_ID,
    "driver_id":           "driver_test_001",
    "vehicle_id":          "V-001",
    "route_id":            "Route 8",
    "trip_id":             f"TEST_TRIP_{service_date}",
    "service_date":        service_date,
    "planned_start_time":  "08:00:00",
    "planned_end_time":    "10:00:00",
    "status":              "scheduled",
    "notes":               "E2E test assignment",
}
print(f"\n[5] POST /supervisor/{SUPERVISOR_ID}/assignments")
print(f"    payload = {json.dumps(payload, indent=2)}")
status, result = post(f"/supervisor/{SUPERVISOR_ID}/assignments", payload)
print(f"    status={status}  result={result}")
check("create status 200 or 201", status in (200, 201), status)
if status in (200, 201):
    assignment_id = result.get("assignment_id")
    check("assignment_id returned", assignment_id is not None, result)
    check("region_id == Zone_East in result", result.get("region_id") == "Zone_East", result.get("region_id"))
    check("route_id == Route 8 in result", result.get("route_id") == "Route 8", result.get("route_id"))
    check("vehicle_id == V-001 in result", result.get("vehicle_id") == "V-001", result.get("vehicle_id"))

# ── 6. List assignments ───────────────────────────────────────
print(f"\n[6] GET /supervisor/{SUPERVISOR_ID}/assignments")
status, assignments = get(f"/supervisor/{SUPERVISOR_ID}/assignments")
print(f"    status={status}  count={len(assignments) if isinstance(assignments, list) else '?'}")
check("list status 200", status == 200, status)

# ── Summary ───────────────────────────────────────────────────
print()
print("=" * 60)
if errors:
    print(f"  RESULT: {FAIL}  {len(errors)} check(s) failed:")
    for e in errors:
        print(f"    - {e}")
    sys.exit(1)
else:
    print(f"  RESULT: {PASS}  All checks passed!")
print("=" * 60)
print()
