import math


def haversine_meters(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def build_walking_transfers(stops, max_walk_meters=500, walking_speed_mps=1.3):
    transfers = {}

    stops = stops.copy()

    for i in range(len(stops)):
        stop_a = stops.iloc[i]
        stop_a_id = str(stop_a["stop_id"])

        if stop_a_id not in transfers:
            transfers[stop_a_id] = []

        for j in range(len(stops)):
            if i == j:
                continue

            stop_b = stops.iloc[j]
            stop_b_id = str(stop_b["stop_id"])

            distance = haversine_meters(
                stop_a["stop_lat"],
                stop_a["stop_lon"],
                stop_b["stop_lat"],
                stop_b["stop_lon"]
            )

            if distance <= max_walk_meters:
                walking_time = int(distance / walking_speed_mps)

                transfers[stop_a_id].append({
                    "to": stop_b_id,
                    "mode": "walk",
                    "distance_meters": round(distance, 2),
                    "walking_time": walking_time
                })

    return transfers


def is_metro_stop(stop):
    stop_id = str(stop.get("stop_id", "")).upper()
    stop_name = str(stop.get("stop_name", "")).upper()

    return "_METRO" in stop_id or " METRO" in stop_name or stop_name.endswith("METRO")


def build_metro_access_transfers(
    stops,
    min_walk_meters=500,
    max_walk_meters=800,
    walking_speed_mps=1.3
):
    transfers = {}
    stops = stops.copy()
    stop_records = [row for _, row in stops.iterrows()]
    metro_stops = [stop for stop in stop_records if is_metro_stop(stop)]
    road_stops = [stop for stop in stop_records if not is_metro_stop(stop)]

    for metro_stop in metro_stops:
        metro_stop_id = str(metro_stop["stop_id"])

        for road_stop in road_stops:
            road_stop_id = str(road_stop["stop_id"])
            distance = haversine_meters(
                metro_stop["stop_lat"],
                metro_stop["stop_lon"],
                road_stop["stop_lat"],
                road_stop["stop_lon"]
            )

            if min_walk_meters < distance <= max_walk_meters:
                walking_time = int(distance / walking_speed_mps)
                edge = {
                    "mode": "walk",
                    "distance_meters": round(distance, 2),
                    "walking_time": walking_time
                }

                transfers.setdefault(metro_stop_id, []).append({
                    **edge,
                    "to": road_stop_id,
                })
                transfers.setdefault(road_stop_id, []).append({
                    **edge,
                    "to": metro_stop_id,
                })

    return transfers
