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
    resp.raise_for_status()
    out_path = os.path.join(os.path.dirname(__file__), 'test7_response.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(resp.json(), f, ensure_ascii=False, indent=2)
    print('Saved response to', out_path)
except Exception as e:
    print('Error:', e)
    sys.exit(1)
