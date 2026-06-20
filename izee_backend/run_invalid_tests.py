import json, requests, os

BASE_URL = 'http://127.0.0.1:8000/trip-plan'

cases = {
    'A': {
        "origin": {"lat": 40.7128, "lon": -74.0060},
        "destination": {"lat": 30.0444, "lon": 31.2357},
        "departure_time": "2026-06-18T08:00:00",
        "max_transfers": 2,
        "use_walking": True
    },
    'B': {
        "origin": {"lat": 30.0500, "lon": 31.2000},  # inside area but likely no transit connections
        "destination": {"lat": 30.0600, "lon": 31.2100},
        "departure_time": "2026-06-18T08:00:00",
        "max_transfers": 2,
        "use_walking": True
    },
    'C': {
        "origin": {"lat": 30.0444, "lon": 31.2357},
        "departure_time": "2026-06-18T08:00:00"
    },
    'D': {
        "origin": {"lat": "abc", "lon": 31.2357},
        "destination": {"lat": 30.0610, "lon": 31.3370},
        "departure_time": "2026-06-18T08:00:00"
    },
    'E': {
        "origin": {"lat": 30.0444, "lon": 31.2357},
        "destination": {"lat": 30.0610, "lon": 31.3370},
        "departure_time": "not-a-date",
        "max_transfers": 2,
        "use_walking": True
    }
}

output_dir = os.path.join(os.path.dirname(__file__), 'invalid_test_responses')
os.makedirs(output_dir, exist_ok=True)

session = requests.Session()

for label, payload in cases.items():
    try:
        resp = session.post(BASE_URL, json=payload, timeout=30)
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = resp.text
        result = {
            "status_code": resp.status_code,
            "response": resp_json
        }
        out_path = os.path.join(output_dir, f"case_{label}_response.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Case {label}: status {resp.status_code}, saved to {out_path}")
    except Exception as e:
        print(f"Case {label}: request failed: {e}")

# Final sanity check: send a valid request (same as test 7 minimal) to ensure backend still up
valid_payload = {
    "origin": {"lat": 30.0439, "lon": 31.2357},
    "destination": {"lat": 30.1633, "lon": 31.3231},
    "departure_time": "2026-06-18T08:00:00",
    "max_transfers": 2,
    "use_walking": True
}
try:
    resp = session.post(BASE_URL, json=valid_payload, timeout=30)
    print("Sanity check response status:", resp.status_code)
except Exception as e:
    print("Sanity check failed:", e)
