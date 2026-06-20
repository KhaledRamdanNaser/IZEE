import uuid
import time
from datetime import datetime, UTC
from reference.loader import load_route_reference
from vehicle_state.matcher import haversine_distance
def create_observation(
    vehicle_id,
    lat,
    lon,
    speed=0,
    source="simulated",
    simulation_flag=True,
    trust_level="medium"
):
    return {
        "observation_id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "location": {
            "lat": lat, 
            "lon": lon
        },
        "speed": speed,
        "bearing": None,
        "source": source,
        "simulation_flag": simulation_flag,
        "trust_level": trust_level,
        "raw_payload": None,
        "ingested_at": datetime.now(UTC).isoformat()
    }

def interpolate(p1, p2, steps=5):
    points = []
    for i in range(steps):
        t = i / steps
        lat = p1[0] + t * (p2[0] - p1[0])
        lon = p1[1] + t * (p2[1] - p1[1])
        points.append((lat, lon))
    return points

route = load_route_reference("CTA_M_112")

path = []

stops = route["stops"][:10]  # keep only first 10 for testing

for i in range(len(stops) - 1):
    p1 = (stops[i]["lat"], stops[i]["lon"])
    p2 = (stops[i + 1]["lat"], stops[i + 1]["lon"])

    segment_points = interpolate(p1, p2, steps=5)
    path.extend(segment_points)


def generate_observations():
    observations = []

    for lat, lon in path:
        obs = create_observation(
            vehicle_id="bus_1",
            lat=lat,
            lon=lon,
            speed=20
        )
        observations.append(obs)

    return observations

def stream_observations():
    for i, (lat, lon) in enumerate(path):

        # find closest stop
        min_dist = float("inf")

        for stop in stops:
            d = haversine_distance(lat, lon, stop["lat"], stop["lon"])
            if d < min_dist:
                min_dist = d

        distance = min_dist

        # simulate realistic speed
        if distance <20:
            speed=0

        elif distance < 100:
            speed = 2
        else:
            speed = 20

        # last point → full stop
        if i == len(path) - 1:
            speed = 0

        obs = create_observation(
            vehicle_id="bus_1",
            lat=lat,
            lon=lon,
            speed=speed
        )

        yield obs
        time.sleep(2)

if __name__ == "__main__":
    for obs in stream_observations():
        print(obs)