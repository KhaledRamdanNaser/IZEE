import math


def haversine_meters(lat1, lon1, lat2, lon2):
    radius_meters = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius_meters * c


def find_candidate_stops(
    lat,
    lon,
    stop_details,
    max_distance_meters=1000,
    limit=10,
    walking_speed_mps=1.3
):
    candidates = []

    for stop_id, stop in stop_details.items():
        if "lat" not in stop or "lon" not in stop:
            continue

        distance = haversine_meters(
            lat,
            lon,
            stop["lat"],
            stop["lon"]
        )

        if (
            max_distance_meters is not None
            and distance > max_distance_meters
        ):
            continue

        candidates.append({
            "stop_id": str(stop_id),
            "distance_meters": round(distance, 2),
            "walking_time": int(distance / walking_speed_mps),
            "stop": stop
        })

    candidates.sort(key=lambda candidate: candidate["distance_meters"])

    return candidates[:limit]


def find_nearest_stops(*args, **kwargs):
    return find_candidate_stops(*args, **kwargs)
