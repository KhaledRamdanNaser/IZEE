import uuid
import time
import random
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


def interpolate(p1, p2, steps=8):
    points = []
    for i in range(steps):
        t = i / steps
        lat = p1[0] + t * (p2[0] - p1[0])
        lon = p1[1] + t * (p2[1] - p1[1])
        points.append((lat, lon))
    return points


def _speed_for_distance(distance_m, segment_length_m=500,
                        hour=8, prev_speed=None):

    # STEP 1: Road ceiling from segment length
    # Based on: World Bank Cairo Traffic Study 2014
    if segment_length_m > 2000:
        # Highway / Ring Road / elevated bridge
        free_flow = random.uniform(75, 100)
    elif segment_length_m > 1200:
        # Major arterial (Ramses, Salah Salem, Corniche)
        free_flow = random.uniform(55, 80)
    elif segment_length_m > 600:
        # Urban main road
        free_flow = random.uniform(35, 60)
    elif segment_length_m > 300:
        # Dense urban street
        free_flow = random.uniform(20, 45)
    else:
        # Very short / narrow segment
        free_flow = random.uniform(10, 30)

    # STEP 2: Traffic congestion factor by time of day
    # Source: World Bank study — peak speeds ~40-65% of free flow
    if hour in [7, 8, 9]:
        # Morning peak — worst congestion
        factor = random.uniform(0.30, 0.50)
    elif hour in [16, 17, 18, 19]:
        # Evening peak — heavy congestion
        factor = random.uniform(0.35, 0.55)
    elif hour in [12, 13, 14]:
        # Midday — moderate
        factor = random.uniform(0.55, 0.70)
    elif hour in [10, 11, 15]:
        # Shoulder hours — lighter traffic
        factor = random.uniform(0.60, 0.80)
    elif hour in [6, 20, 21]:
        # Early morning / evening — light
        factor = random.uniform(0.70, 0.88)
    else:
        # Night (22:00 - 05:00) — near free flow
        factor = random.uniform(0.85, 1.00)

    # STEP 3: Per-observation random noise
    # Simulates traffic lights, sudden slowdowns, driver behavior
    noise = random.gauss(0, 3.5)

    # Base cruise speed for this observation
    cruise = (free_flow * factor) + noise
    cruise = max(3.0, cruise)

    # STEP 4: Deceleration zones near stop
    if distance_m <= 30:
        # At stop
        target = 0.0

    elif distance_m <= 70:
        # Hard braking zone
        target = random.uniform(0.5, 5.0)

    elif distance_m <= 150:
        # Active deceleration
        ratio = (distance_m - 70) / 80  # 0→1
        target = ratio * cruise * 0.35

    elif distance_m <= 300:
        # Approaching — partial speed
        ratio = (distance_m - 150) / 150  # 0→1
        target = cruise * (0.35 + ratio * 0.45)

    else:
        # Full cruise
        target = cruise

    # STEP 5: Smooth transition — Cairo buses change speed fast
    # Allow up to 10 km/h change per observation (aggressive driving)
    if prev_speed is not None:
        max_change = 10.0
        if target > prev_speed + max_change:
            target = prev_speed + max_change
        elif target < prev_speed - max_change:
            target = prev_speed - max_change

    # Final safety clamp
    return round(max(0.0, min(target, 105.0)), 1)


route = load_route_reference("CTA_M_112")
stops = route["stops"]  # all stops

path = []
for i in range(len(stops) - 1):
    p1 = (stops[i]["lat"], stops[i]["lon"])
    p2 = (stops[i + 1]["lat"], stops[i + 1]["lon"])
    path.extend(interpolate(p1, p2, steps=8))


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
    prev_speed = None
    for i, (lat, lon) in enumerate(path):
        min_dist = float("inf")
        for stop in stops:
            d = haversine_distance(lat, lon, stop["lat"], stop["lon"])
            if d < min_dist:
                min_dist = d
        distance = min_dist

        segment_index = i // 8
        if segment_index < len(stops) - 1:
            s1 = stops[segment_index]
            s2 = stops[segment_index + 1]
            segment_length_m = haversine_distance(s1["lat"], s1["lon"], s2["lat"], s2["lon"])
        else:
            segment_length_m = 500

        speed = _speed_for_distance(
            distance_m=distance,
            segment_length_m=segment_length_m,
            hour=datetime.now().hour,
            prev_speed=prev_speed
        )
        prev_speed = speed

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


def simulate_trip(vehicle_id, hour):
    observations = []
    prev_speed = None

    for i in range(len(stops) - 1):
        p1 = (stops[i]["lat"], stops[i]["lon"])
        p2 = (stops[i + 1]["lat"], stops[i + 1]["lon"])
        next_lat = stops[i + 1]["lat"]
        next_lon = stops[i + 1]["lon"]

        segment_length_m = haversine_distance(p1[0], p1[1], p2[0], p2[1])

        for lat, lon in interpolate(p1, p2, steps=8):
            dist = haversine_distance(lat, lon, next_lat, next_lon)
            speed = _speed_for_distance(
                distance_m=dist,
                segment_length_m=segment_length_m,
                hour=hour,
                prev_speed=prev_speed
            )
            observations.append(create_observation(
                vehicle_id=vehicle_id,
                lat=lat,
                lon=lon,
                speed=speed
            ))
            prev_speed = speed

    last = stops[-1]
    observations.append(create_observation(
        vehicle_id=vehicle_id,
        lat=last["lat"],
        lon=last["lon"],
        speed=0.0
    ))

    return observations


if __name__ == "__main__":
    for obs in stream_observations():
        print(obs)
