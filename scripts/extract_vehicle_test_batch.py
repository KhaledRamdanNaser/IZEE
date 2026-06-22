import json
from collections import defaultdict

# Added 'r' before the string to handle Windows backslashes properly
INPUT_FILE = r"C:\Users\mohamed\IZEE\data_salah\converted\all_observations.jsonl"
OUTPUT_FILE = "tests/data/single_vehicle_test.jsonl"

TARGET_COUNT = 300


# ---------------------------------------
# PASS 1: find vehicle observation counts
# ---------------------------------------

vehicle_counts = defaultdict(int)

print("Scanning vehicles...")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        obs = json.loads(line)
        vehicle_counts[obs["vehicle_id"]] += 1


# pick vehicle with most observations
best_vehicle = max(
    vehicle_counts,
    key=vehicle_counts.get
)

print(
    "Selected vehicle:",
    best_vehicle,
    "observations:",
    vehicle_counts[best_vehicle]
)


# ---------------------------------------
# PASS 2: extract timeline
# ---------------------------------------

selected = []

print(f"Extracting up to {TARGET_COUNT} observations for vehicle {best_vehicle}...")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        obs = json.loads(line)

        if obs["vehicle_id"] == best_vehicle:
            selected.append(obs)

        if len(selected) >= TARGET_COUNT:
            break


# ensure chronological order
selected.sort(
    key=lambda x: x["timestamp"]
)


with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for obs in selected:
        f.write(json.dumps(obs) + "\n")


print(
    f"Saved {len(selected)} observations to {OUTPUT_FILE}"
)