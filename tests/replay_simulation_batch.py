import json
import time
import requests
import sys


API_URL = "http://127.0.0.1:8000/simulation/observation"


with open(sys.argv[1], "r") as f:

    observations = [
        json.loads(line)
        for line in f
        if line.strip()
    ]


print(
    f"\nREPLAYING {len(observations)} OBSERVATIONS\n"
)


success = 0
failed = 0


for i, obs in enumerate(observations):

    response = requests.post(
        API_URL,
        json=obs
    )

    print(
        f"[{i+1}/{len(observations)}]"
    )

    if response.status_code != 200:

        failed += 1

        print(
            "FAILED:",
            response.status_code,
            response.text
        )

        print("-" * 40)

        continue


    try:

        data = response.json()

        success += 1


        print(
            "Vehicle:",
            data.get("vehicle_id")
        )

        print(
            "Segment:",
            data.get("segment_id")
        )

        print(
            "Segment Progress:",
            data.get("segment_progress")
        )

        print(
            "Movement:",
            data.get("movement_state")
        )

        print(
            "Speed:",
            data.get("speed")
        )

        print(
            "Events:",
            data.get("events")
        )


    except Exception as e:

        failed += 1

        print(
            "BAD RESPONSE:",
            e
        )


    print("-" * 40)


    # optional
    time.sleep(0.05)



print("\nDONE")
print("SUCCESS:", success)
print("FAILED:", failed)