import argparse
import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GTFS_DIR = PROJECT_ROOT / "gtfs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "local_replay_data"
DEFAULT_ROUTE_ID = "CTA_M_112"
DEFAULT_DIRECTION = 0
DEFAULT_FILE_NAME = "day_1_monday_observations.jsonl"


def read_csv_by_path(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_route_stops(route_id: str, direction: int, limit: int = 4) -> list[dict]:
    trips = read_csv_by_path(GTFS_DIR / "trips.txt")
    stop_times = read_csv_by_path(GTFS_DIR / "stop_times.txt")
    stops = {
        row["stop_id"]: row
        for row in read_csv_by_path(GTFS_DIR / "stops.txt")
    }

    trip = next(
        (
            row for row in trips
            if row["route_id"] == route_id
            and int(row["direction_id"]) == direction
        ),
        None,
    )
    if not trip:
        raise RuntimeError(f"No GTFS trip found for route={route_id}, direction={direction}")

    rows = [
        row for row in stop_times
        if row["trip_id"] == trip["trip_id"]
    ]
    rows.sort(key=lambda row: int(row["stop_sequence"]))

    route_stops = []
    for row in rows[:limit]:
        stop = stops[row["stop_id"]]
        route_stops.append({
            "trip_id": trip["trip_id"],
            "route_id": route_id,
            "direction": direction,
            "stop_id": row["stop_id"],
            "stop_sequence": int(row["stop_sequence"]),
            "lat": float(stop["stop_lat"]),
            "lon": float(stop["stop_lon"]),
        })

    if len(route_stops) < 3:
        raise RuntimeError("Need at least 3 GTFS stops to generate the pipeline test")

    return route_stops


def interpolate(start: dict, end: dict, ratio: float) -> tuple[float, float]:
    lat = start["lat"] + ((end["lat"] - start["lat"]) * ratio)
    lon = start["lon"] + ((end["lon"] - start["lon"]) * ratio)
    return lat, lon


def bearing_degrees(start: dict, end: dict) -> float:
    lat1 = math.radians(start["lat"])
    lat2 = math.radians(end["lat"])
    delta_lon = math.radians(end["lon"] - start["lon"])

    y = math.sin(delta_lon) * math.cos(lat2)
    x = (
        math.cos(lat1) * math.sin(lat2)
        - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
    )
    bearing = math.degrees(math.atan2(y, x))
    return round((bearing + 360) % 360, 2)


def make_observation(
    *,
    observation_id: str,
    vehicle_id: str,
    route_id: str,
    direction: int,
    timestamp: datetime,
    lat: float,
    lon: float,
    speed: float,
    bearing: float,
    day_number: int,
    seed: int,
) -> dict:
    return {
        "observation_id": observation_id,
        "vehicle_id": vehicle_id,
        "route_id": route_id,
        "direction": direction,
        "timestamp": timestamp.isoformat(),
        "lat": round(lat, 8),
        "lon": round(lon, 8),
        "speed": speed,
        "bearing": bearing,
        "day_of_week": "Monday",
        "day_number": day_number,
        "time_period": "peak",
        "simulation_seed": seed,
    }


def add_vehicle_trip(
    observations: list[dict],
    *,
    vehicle_id: str,
    route_id: str,
    direction: int,
    stops: list[dict],
    start_time: datetime,
    dwell_seconds: int,
    travel_seconds: int,
    moving_speed: float,
    day_number: int,
    seed: int,
    post_arrival_dwell_seconds: int = 0,
) -> None:
    # Use the second stop as the first observed stop. That creates a real
    # arrival/dwell/departure lifecycle, then a completed segment to stop 3.
    origin = stops[1]
    destination = stops[2]
    next_stop = stops[3] if len(stops) > 3 else None
    bearing = bearing_degrees(origin, destination)
    hold_lat, hold_lon = interpolate(origin, destination, 0.995)

    points = [
        (0, origin["lat"], origin["lon"], 0, bearing),
        (dwell_seconds, origin["lat"], origin["lon"], 0, bearing),
        (dwell_seconds + 15, *interpolate(origin, destination, 0.20), moving_speed, bearing),
        (dwell_seconds + 30, *interpolate(origin, destination, 0.35), moving_speed, bearing),
        (dwell_seconds + max(45, travel_seconds // 2), *interpolate(origin, destination, 0.65), moving_speed, bearing),
        (dwell_seconds + travel_seconds, hold_lat, hold_lon, 0, bearing),
    ]

    if post_arrival_dwell_seconds and next_stop:
        next_bearing = bearing_degrees(destination, next_stop)
        departure_start = dwell_seconds + travel_seconds + post_arrival_dwell_seconds
        points.extend([
            (
                departure_start,
                hold_lat,
                hold_lon,
                0,
                next_bearing,
            ),
            (
                departure_start + 15,
                *interpolate(destination, next_stop, 0.20),
                moving_speed,
                next_bearing,
            ),
            (
                departure_start + 30,
                *interpolate(destination, next_stop, 0.35),
                moving_speed,
                next_bearing,
            ),
            (
                departure_start + 45,
                *interpolate(destination, next_stop, 0.55),
                moving_speed,
                next_bearing,
            ),
        ])

    for index, (offset, lat, lon, speed, obs_bearing) in enumerate(points, start=1):
        observations.append(make_observation(
            observation_id=f"{vehicle_id}_{index:02d}",
            vehicle_id=vehicle_id,
            route_id=route_id,
            direction=direction,
            timestamp=start_time + timedelta(seconds=offset),
            lat=lat,
            lon=lon,
            speed=speed,
            bearing=obs_bearing,
            day_number=day_number,
            seed=seed,
        ))


def generate_observations(route_id: str, direction: int) -> list[dict]:
    stops = load_route_stops(route_id, direction)
    observations = []
    base_time = datetime(2026, 6, 18, 10, 0, 0)

    # Baseline vehicles establish normal segment travel times.
    for idx in range(1, 11):
        add_vehicle_trip(
            observations,
            vehicle_id=f"GTFS_NORMAL_{idx:03d}",
            route_id=route_id,
            direction=direction,
            stops=stops,
            start_time=base_time + timedelta(minutes=idx * 2),
            dwell_seconds=30,
            travel_seconds=90,
            moving_speed=35,
            day_number=1,
            seed=1000 + idx,
        )

    # Three delayed vehicles should later become delay alerts and one route
    # disruption once segment statistics are computed.
    for idx in range(1, 4):
        add_vehicle_trip(
            observations,
            vehicle_id=f"GTFS_DELAY_{idx:03d}",
            route_id=route_id,
            direction=direction,
            stops=stops,
            start_time=base_time + timedelta(minutes=40 + idx * 2),
            dwell_seconds=30,
            travel_seconds=360,
            moving_speed=8,
            day_number=1,
            seed=2000 + idx,
        )

    # One long dwell scenario should become a dwell_issue alert.
    add_vehicle_trip(
        observations,
        vehicle_id="GTFS_DWELL_001",
        route_id=route_id,
        direction=direction,
        stops=stops,
        start_time=base_time + timedelta(minutes=55),
        dwell_seconds=360,
        travel_seconds=90,
        moving_speed=35,
        day_number=1,
        seed=3001,
        post_arrival_dwell_seconds=360,
    )

    observations.sort(key=lambda row: row["timestamp"])
    return observations


def write_jsonl(observations: list[dict], output_dir: Path, file_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / file_name
    with output_path.open("w", encoding="utf-8") as f:
        for observation in observations:
            f.write(json.dumps(observation, separators=(",", ":")) + "\n")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-id", default=DEFAULT_ROUTE_ID)
    parser.add_argument("--direction", type=int, default=DEFAULT_DIRECTION)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--file-name", default=DEFAULT_FILE_NAME)
    args = parser.parse_args()

    observations = generate_observations(args.route_id, args.direction)
    output_path = write_jsonl(observations, Path(args.output_dir), args.file_name)

    print(f"Generated {len(observations)} observations")
    print(f"Route: {args.route_id}, direction: {args.direction}")
    print(f"Output: {output_path}")
    print()
    print("First observation:")
    print(json.dumps(observations[0], indent=2))


if __name__ == "__main__":
    main()
