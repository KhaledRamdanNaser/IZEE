import json, requests, os, sys
url = 'http://127.0.0.1:8000/trip-plan'
payload = {
    "origin": {"lat": 30.0439, "lon": 31.2357},
    "destination": {"lat": 30.1633, "lon": 31.3231},
    "departure_time": "2026-06-18T08:00:00",
    "max_transfers": 3,
    "use_walking": True
}
headers = {'Content-Type': 'application/json'}
try:
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    print('Status:', resp.status_code)
    print('Response JSON:')
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print('Error:', e)
    sys.exit(1)
