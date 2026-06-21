import json
import time
import requests
import sys

API_URL = "http://127.0.0.1:8000/vehicle/location"

# load scenario file
with open(sys.argv[1], "r") as f:
    scenario = json.load(f)

print(f"\nRUNNING: {scenario['scenario_name']}\n")

observations = scenario["observations"]

for i, obs in enumerate(observations):

    response = requests.post(
        API_URL,
        json=obs
    )

    print(f"[{i+1}/{len(observations)}]")

    try:
        data = response.json()

        print("========== VEHICLE STATE RESULT ==========")

        print("Vehicle:",
            data.get("vehicle_id"))

        print("Movement State:",
            data.get("movement_state"))

        print("Matched Segment:",
            data.get("segment_id"))

        print("Segment Progress:",
            data.get("segment_progress"))

        print("Route Progress:",
            data.get("progress"))

        print("Current Stop:",
            data.get("current_stop_id"))

        print("Next Stop:",
            data.get("next_stop_id"))

        print("Distance To Next Stop:",
            data.get("distance_to_next_stop"))

        print("Events:",
            data.get("events"))

        print("==========================================")

    except Exception:
        print("FAILED RESPONSE")

    print("-" * 40)

    time.sleep(1)