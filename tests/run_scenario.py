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

        print("STATE:",
              data.get("movement_state"))

        print("EVENTS:",
              data.get("events"))

    except Exception:
        print("FAILED RESPONSE")

    print("-" * 40)

    time.sleep(1)