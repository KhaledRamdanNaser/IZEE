import json, requests

def fetch(payload):
    url = 'http://127.0.0.1:8000/trip-plan'
    resp = requests.post(url, json=payload)
    print(json.dumps(resp.json(), indent=2))

# Normal walking transfer
payload1 = {
    "origin": {"lat": 30.0439, "lon": 31.2357},
    "destination": {"lat": 30.0681, "lon": 31.3329},
    "departure_time": "2026-06-18T08:00:00",
    "max_transfers": 2,
    "use_walking": True
}
fetch(payload1)

# BRT feeder transfer
payload2 = {
    "origin": {"lat": 30.058985, "lon": 31.244515},
    "destination": {"lat": 30.1633208, "lon": 31.3231549},
    "departure_time": "2026-06-18T08:00:00",
    "max_transfers": 2,
    "use_walking": True
}
fetch(payload2)

# LRT feeder transfer
payload3 = {
    "origin": {"lat": 30.058985, "lon": 31.244515},
    "destination": {"lat": 30.0638, "lon": 31.2521},
    "departure_time": "2026-06-18T08:00:00",
    "max_transfers": 2,
    "use_walking": True
}
fetch(payload3)

# Emergency access attempt
payload4 = {
    "origin": {"lat": 30.0439, "lon": 31.2357},
    "destination": {"lat": 30.0775, "lon": 31.3500},
    "departure_time": "2026-06-18T08:00:00",
    "max_transfers": 2,
    "use_walking": True
}
fetch(payload4)
