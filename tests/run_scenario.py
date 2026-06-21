import json
import time
import requests
import sys

API_URL = "http://127.0.0.1:8000/vehicle/location"

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

        print("========== VEHICLE STATE ==========")

        print("Movement State:",
              data.get("movement_state"))

        print("Segment:",
              data.get("segment_id"))

        print("Current Stop:",
              data.get("current_stop_id"))

        print("Next Stop:",
              data.get("next_stop_id"))

        print("Distance:",
              data.get("distance_to_next_stop"))

        print("========== EVENT ENGINE ==========")

        events = data.get("events", [])

        print("Event Count:",
              len(events) if events else 0)

        if events:

            for index, event in enumerate(events):

                print(f"\nEVENT {index + 1}")

                print("Type:",
                      event.get("event_type"))

                print("Stop:",
                      event.get("stop_id"))

                print("From:",
                      event.get("from_stop_id"))

                print("To:",
                      event.get("to_stop_id"))

                print("Segment:",
                      event.get("segment_id"))

                print("Metrics:",
                      event.get("metrics"))

        print("==================================")

    except Exception as e:

        print("FAILED RESPONSE")
        print(e)

    print("-" * 40)

    time.sleep(1)