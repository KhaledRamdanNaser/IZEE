import requests

try:
    print("Testing /driver/route-info...")
    url = "http://localhost:8000/driver/route-info"
    params = {
        "vehicle_id": "driver_test_001",
        "route_id": "A-12 Express",
        "driver_id": "driver_test_001"
    }
    res = requests.get(url, params=params)
    print("Status Code:", res.status_code)
    print("Response:", res.text)
except Exception as e:
    print(e)

