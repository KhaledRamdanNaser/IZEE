access_egress.py{
    from routing.nearest_stop_search import find_candidate_stops


def build_access_candidates(
    origin,
    stop_details,
    max_distance_meters=1000,
    limit=10,
    walking_speed_mps=1.3
):
    return find_candidate_stops(
        lat=origin["lat"],
        lon=origin["lon"],
        stop_details=stop_details,
        max_distance_meters=max_distance_meters,
        limit=limit,
        walking_speed_mps=walking_speed_mps
    )


def build_egress_candidates(
    destination,
    stop_details,
    max_distance_meters=700,
    limit=10,
    walking_speed_mps=1.3,
    max_extra_distance_meters=250
):
    candidates = find_candidate_stops(
        lat=destination["lat"],
        lon=destination["lon"],
        stop_details=stop_details,
        max_distance_meters=max_distance_meters,
        limit=limit,
        walking_speed_mps=walking_speed_mps
    )

    if not candidates:
        return []

    closest_distance = candidates[0]["distance_meters"]
    max_allowed_distance = closest_distance + max_extra_distance_meters

    return [
        candidate
        for candidate in candidates
        if candidate["distance_meters"] <= max_allowed_distance
    ][:limit]

}

eta_provider.py{
    import json
import os


_estimate_store_cache = None
_estimate_store_path = None
_estimate_store_mtime = None


def build_segment_id(route_id, direction_id, from_stop_id, to_stop_id):
    direction = "any" if direction_id is None else str(direction_id)
    return f"{route_id}:{direction}:{from_stop_id}:{to_stop_id}"


def build_segment_request(route_id, direction_id, from_stop_id, to_stop_id):
    return {
        "segment_id": build_segment_id(
            route_id,
            direction_id,
            from_stop_id,
            to_stop_id
        ),
        "route_id": str(route_id),
        "direction_id": direction_id,
        "from_stop_id": str(from_stop_id),
        "to_stop_id": str(to_stop_id)
    }


def collect_segment_requests(indexes):
    requests_by_id = {}

    for trip_times in indexes["stop_times_by_trip"].values():
        for previous_stop, next_stop in zip(trip_times, trip_times[1:]):
            request = build_segment_request(
                route_id=previous_stop["route_id"],
                direction_id=previous_stop.get("direction_id"),
                from_stop_id=previous_stop["stop_id"],
                to_stop_id=next_stop["stop_id"]
            )
            requests_by_id[request["segment_id"]] = request

    return list(requests_by_id.values())


def normalize_estimate(estimate):
    if estimate is None:
        return None

    normalized = dict(estimate)

    if "predicted_travel_time" in normalized:
        normalized["predicted_travel_time"] = int(
            float(normalized["predicted_travel_time"])
        )

    if "predicted_delay" in normalized:
        normalized["predicted_delay"] = int(float(normalized["predicted_delay"]))

    if "confidence" in normalized:
        normalized["confidence"] = str(normalized["confidence"]).lower()

    return normalized


def load_mock_segment_estimates():
    global _estimate_store_cache, _estimate_store_path, _estimate_store_mtime

    path = os.getenv("ETA_SEGMENT_ESTIMATES_PATH")

    if not path or not os.path.exists(path):
        _estimate_store_cache = {}
        _estimate_store_path = path
        _estimate_store_mtime = None
        return {}

    mtime = os.path.getmtime(path)

    if (
        _estimate_store_cache is not None
        and _estimate_store_path == path
        and _estimate_store_mtime == mtime
    ):
        return _estimate_store_cache

    with open(path, "r", encoding="utf-8") as estimates_file:
        payload = json.load(estimates_file)

    if isinstance(payload, list):
        _estimate_store_cache = {
            str(item["segment_id"]): normalize_estimate(item)
            for item in payload
            if "segment_id" in item
        }
        _estimate_store_path = path
        _estimate_store_mtime = mtime
        return _estimate_store_cache

    if isinstance(payload, dict):
        estimates = payload.get("estimates", payload)

        if isinstance(estimates, list):
            _estimate_store_cache = {
                str(item["segment_id"]): normalize_estimate(item)
                for item in estimates
                if "segment_id" in item
            }
            _estimate_store_path = path
            _estimate_store_mtime = mtime
            return _estimate_store_cache

        _estimate_store_cache = {
            str(segment_id): normalize_estimate(estimate)
            for segment_id, estimate in estimates.items()
        }
        _estimate_store_path = path
        _estimate_store_mtime = mtime
        return _estimate_store_cache

    _estimate_store_cache = {}
    _estimate_store_path = path
    _estimate_store_mtime = mtime
    return {}


def get_segment_estimates(segment_requests, departure_time_seconds):
    """
    Adapter boundary for the ETA component.

    The ETA team can replace this function with a database/API call that accepts
    SegmentEstimate requests and returns predictions keyed by segment_id.
    """

    mock_estimates = load_mock_segment_estimates()

    if not mock_estimates:
        return {}

    requested_ids = {
        request["segment_id"]
        for request in segment_requests
    }

    return {
        segment_id: estimate
        for segment_id, estimate in mock_estimates.items()
        if segment_id in requested_ids
    }

}

fare_calculator.py{
    DEFAULT_CURRENCY = "EGP"

STATIC_FARES_BY_MODE = {
    "bus": 15,
    "minibus": 20,
    "microbus": 12,
    "metro": 15,
    "lrt": 20,  
    "brt": 15,
    "monorail": 25,
}


def calculate_leg_fare(leg):
    mode = leg.get("mode")

    if mode == "walk":
        return 0

    return STATIC_FARES_BY_MODE.get(mode, STATIC_FARES_BY_MODE["bus"])


def calculate_path_fare(path):
    leg_fares = []

    for leg in path:
        fare = calculate_leg_fare(leg)
        leg_fares.append({
            "mode": leg.get("mode"),
            "from_stop_id": leg.get("from_stop_id"),
            "to_stop_id": leg.get("to_stop_id"),
            "route_id": leg.get("route_id"),
            "fare": fare,
            "currency": DEFAULT_CURRENCY
        })

    return {
        "total_fare": sum(item["fare"] for item in leg_fares),
        "currency": DEFAULT_CURRENCY,
        "leg_fares": leg_fares
    }

}

frequency_expander.py{
    import pandas as pd


def time_to_seconds(t):
    h, m, s = map(int, str(t).split(":"))
    return h * 3600 + m * 60 + s


def seconds_to_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def expand_frequencies(trips, stop_times, frequencies):
    """
    Converts frequency-based GTFS trips into exact virtual trips.

    Example:
    trip T1 runs 06:00-07:00 every 600 sec
    -> T1__freq__21600, T1__freq__22200, T1__freq__22800, ...
    """

    if frequencies is None or len(frequencies) == 0:
        return trips, stop_times

    new_trips = []
    new_stop_times = []

    trips_by_id = {
        str(row["trip_id"]): row
        for row in trips.to_dict("records")
    }

    stop_times_by_trip = {
        str(trip_id): group.sort_values("stop_sequence").to_dict("records")
        for trip_id, group in stop_times.groupby("trip_id")
    }

    for _, freq in frequencies.iterrows():
        base_trip_id = str(freq["trip_id"])

        if base_trip_id not in trips_by_id:
            continue

        if base_trip_id not in stop_times_by_trip:
            continue

        start = time_to_seconds(freq["start_time"])
        end = time_to_seconds(freq["end_time"])

        if pd.isna(freq["headway_secs"]):
            continue

        headway = int(freq["headway_secs"])

        if headway <= 0:
            continue

        base_trip = trips_by_id[base_trip_id]
        base_stop_times = stop_times_by_trip[base_trip_id]

        first_departure = time_to_seconds(
            base_stop_times[0]["departure_time"]
        )

        current = start

        while current < end:
            offset = current - first_departure
            virtual_trip_id = f"{base_trip_id}__freq__{current}"

            trip_copy = dict(base_trip)
            trip_copy["trip_id"] = virtual_trip_id
            new_trips.append(trip_copy)

            for st in base_stop_times:
                st_copy = dict(st)
                st_copy["trip_id"] = virtual_trip_id

                arr = time_to_seconds(st["arrival_time"]) + offset
                dep = time_to_seconds(st["departure_time"]) + offset

                st_copy["arrival_time"] = seconds_to_time(arr)
                st_copy["departure_time"] = seconds_to_time(dep)

                new_stop_times.append(st_copy)

            current += headway

    frequency_trip_ids = set(frequencies["trip_id"].astype(str))

    base_trips = trips[
        ~trips["trip_id"].astype(str).isin(frequency_trip_ids)
    ].copy()

    base_stop_times = stop_times[
        ~stop_times["trip_id"].astype(str).isin(frequency_trip_ids)
    ].copy()

    expanded_trips = pd.concat(
        [base_trips, pd.DataFrame(new_trips, columns=trips.columns)],
        ignore_index=True
    )

    expanded_stop_times = pd.concat(
        [base_stop_times, pd.DataFrame(new_stop_times, columns=stop_times.columns)],
        ignore_index=True
    )

    return expanded_trips, expanded_stop_times

}

generate_transfers_to_db.py{
    from routing.gtfs_loader import load_multiple_gtfs
from routing.transfer_builder import build_metro_access_transfers, build_walking_transfers
from database.connection import SessionLocal, Base, engine
from models.walking_transfer import WalkingTransfer

GTFS_PATHS = [
    "C:\\Users\\omaro\\Desktop\\semeser 8\\link (7)",
    "C:\\Users\\omaro\\Desktop\\semeser 8\\Metro-GTFS-master\\Metro-GTFS-master",
]

Base.metadata.create_all(bind=engine)

stops, stop_times, trips, routes, calendar, frequencies, shapes = load_multiple_gtfs(GTFS_PATHS)

normal_transfers = build_walking_transfers(
    stops,
    max_walk_meters=1500,
    walking_speed_mps=1.3
)

metro_access_transfers = build_metro_access_transfers(
    stops,
    min_walk_meters=500,
    max_walk_meters=800,
    walking_speed_mps=1.3
)

emergency_transfers = build_walking_transfers(
    stops,
    max_walk_meters=3000,
    walking_speed_mps=1.3
)

db = SessionLocal()

try:
    # remove old transfers before regenerating
    db.query(WalkingTransfer).delete()

    count = 0
    seen_normal_pairs = set()

    # Save normal stop-to-stop transfers used during normal routing.
    for from_stop_id, edges in normal_transfers.items():
        for edge in edges:
            key = (str(from_stop_id), str(edge["to"]), "normal_transfer")
            seen_normal_pairs.add(key)

            transfer = WalkingTransfer(
                from_stop_id=key[0],
                to_stop_id=key[1],
                walk_type=key[2],
                distance_meters=float(edge["distance_meters"]),
                walking_time=int(edge["walking_time"])
            )

            db.add(transfer)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"Saved {count} transfers...")

    # This is now mostly covered by the 1500m normal walking radius, but keep it
    # harmless in case the metro-specific logic changes later.
    for from_stop_id, edges in metro_access_transfers.items():
        for edge in edges:
            key = (str(from_stop_id), str(edge["to"]), "normal_transfer")

            if key in seen_normal_pairs:
                continue

            seen_normal_pairs.add(key)

            transfer = WalkingTransfer(
                from_stop_id=key[0],
                to_stop_id=key[1],
                walk_type=key[2],
                distance_meters=float(edge["distance_meters"]),
                walking_time=int(edge["walking_time"])
            )

            db.add(transfer)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"Saved {count} transfers...")

    # Save longer fallback access transfers separately from normal routing.
    for from_stop_id, edges in emergency_transfers.items():
        for edge in edges:
            if float(edge["distance_meters"]) <= 1500:
                continue

            transfer = WalkingTransfer(
                from_stop_id=str(from_stop_id),
                to_stop_id=str(edge["to"]),
                walk_type="emergency_access",
                distance_meters=float(edge["distance_meters"]),
                walking_time=int(edge["walking_time"])
            )

            db.add(transfer)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"Saved {count} transfers...")

    db.commit()
    print(f"Done. Saved {count} walking transfers.")

except Exception as e:
    db.rollback()
    print("Error:", e)

finally:
    db.close()

}

graph_builder.py{
    import pandas as pd


def time_to_seconds(t):
    h, m, s = map(int, str(t).split(":"))
    return h * 3600 + m * 60 + s


def build_graph_from_gtfs(stop_times, trips):
    graph = {}

    # Step 1: attach route_id and direction_id to each stop_time row
    stop_times = stop_times.merge(
        trips[["trip_id", "route_id", "direction_id"]],
        on="trip_id",
        how="left"
    )

    # Step 2: sort stops inside each trip
    stop_times = stop_times.sort_values(
        by=["trip_id", "stop_sequence"]
    )

    # Step 3: loop through every consecutive pair of rows
    for i in range(len(stop_times) - 1):
        curr = stop_times.iloc[i]
        nxt = stop_times.iloc[i + 1]

        # Step 4: only connect stops from the same trip
        if curr["trip_id"] != nxt["trip_id"]:
            continue

        curr_stop = str(curr["stop_id"]) 
        next_stop = str(nxt["stop_id"])

        # Step 5: convert GTFS times into seconds
        departure_time = time_to_seconds(curr["departure_time"])
        arrival_time = time_to_seconds(nxt["arrival_time"])

        travel_time = arrival_time - departure_time

        # Step 6: skip broken time data
        if travel_time < 0:
            continue

        # Step 7: make sure both stops exist in the graph
        if curr_stop not in graph:
            graph[curr_stop] = []

        if next_stop not in graph:
            graph[next_stop] = []

        # Step 8: add forward ride edge
        graph[curr_stop].append({
            "to": next_stop,
            "mode": "ride",
            "trip_id": str(curr["trip_id"]),
            "route_id": str(curr["route_id"]),
            "direction_id": None if pd.isna(curr["direction_id"]) else int(curr["direction_id"]),
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "travel_time": travel_time
        })

    return graph
}

gtfs_loader.py{
    import pandas as pd


def load_gtfs(folder_path):
    stops = pd.read_csv(f"{folder_path}/stops.txt")
    stop_times = pd.read_csv(f"{folder_path}/stop_times.txt")
    trips = pd.read_csv(f"{folder_path}/trips.txt")
    routes = pd.read_csv(f"{folder_path}/routes.txt")
    calendar = pd.read_csv(f"{folder_path}/calendar.txt")
    frequencies = pd.read_csv(f"{folder_path}/frequencies.txt")
    shapes = pd.read_csv(f"{folder_path}/shapes.txt")

    if "shape_id" not in trips.columns and "shape_id" in shapes.columns:
        shape_ids = set(shapes["shape_id"].astype(str))

        def infer_shape_id(route_id):
            route_id = str(route_id)

            if route_id.startswith("L") and route_id[1:].isdigit():
                metro_shape_id = f"M{route_id[1:]}"

                if metro_shape_id in shape_ids:
                    return metro_shape_id

            return None

        trips["shape_id"] = trips["route_id"].apply(infer_shape_id)

    return stops, stop_times, trips, routes, calendar, frequencies, shapes


def combine_dataframes(dataframes):
    return pd.concat(dataframes, ignore_index=True, sort=False)


def load_multiple_gtfs(folder_paths):
    loaded_feeds = [load_gtfs(folder_path) for folder_path in folder_paths]

    stops = combine_dataframes([feed[0] for feed in loaded_feeds])
    stop_times = combine_dataframes([feed[1] for feed in loaded_feeds])
    trips = combine_dataframes([feed[2] for feed in loaded_feeds])
    routes = combine_dataframes([feed[3] for feed in loaded_feeds])
    calendar = combine_dataframes([feed[4] for feed in loaded_feeds])
    frequencies = combine_dataframes([feed[5] for feed in loaded_feeds])
    shapes = combine_dataframes([feed[6] for feed in loaded_feeds])

    return stops, stop_times, trips, routes, calendar, frequencies, shapes

}

gtfs_validator.py{
    import pandas as pd


def validate_gtfs(stops, routes, trips, stop_times, calendar=None):
    errors = []
    warnings = []

    # -----------------------------
    # 1. Required columns
    # -----------------------------
    required_columns = {
        "stops": ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        "routes": ["route_id"],
        "trips": ["trip_id", "route_id", "service_id"],
        "stop_times": ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
    }

    datasets = {
        "stops": stops,
        "routes": routes,
        "trips": trips,
        "stop_times": stop_times,
    }

    for name, df in datasets.items():
        for col in required_columns[name]:
            if col not in df.columns:
                errors.append(f"{name}.txt missing required column: {col}")

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings
        }

    # -----------------------------
    # 2. stop_times.trip_id exists in trips
    # -----------------------------
    trip_ids = set(trips["trip_id"].astype(str))
    stop_time_trip_ids = set(stop_times["trip_id"].astype(str))

    missing_trip_ids = stop_time_trip_ids - trip_ids

    if missing_trip_ids:
        errors.append(
            f"{len(missing_trip_ids)} trip_id values in stop_times do not exist in trips.txt"
        )

    # -----------------------------
    # 3. stop_times.stop_id exists in stops
    # -----------------------------
    stop_ids = set(stops["stop_id"].astype(str))
    stop_time_stop_ids = set(stop_times["stop_id"].astype(str))

    missing_stop_ids = stop_time_stop_ids - stop_ids

    if missing_stop_ids:
        errors.append(
            f"{len(missing_stop_ids)} stop_id values in stop_times do not exist in stops.txt"
        )

    # -----------------------------
    # 4. trips.route_id exists in routes
    # -----------------------------
    route_ids = set(routes["route_id"].astype(str))
    trip_route_ids = set(trips["route_id"].astype(str))

    missing_route_ids = trip_route_ids - route_ids

    if missing_route_ids:
        errors.append(
            f"{len(missing_route_ids)} route_id values in trips do not exist in routes.txt"
        )

    # -----------------------------
    # 5. trips.service_id exists in calendar
    # -----------------------------
    if calendar is not None and "service_id" in calendar.columns:
        service_ids = set(calendar["service_id"].astype(str))
        trip_service_ids = set(trips["service_id"].astype(str))

        missing_service_ids = trip_service_ids - service_ids

        if missing_service_ids:
            warnings.append(
                f"{len(missing_service_ids)} service_id values in trips do not exist in calendar.txt"
            )
    else:
        warnings.append("calendar.txt not provided or missing service_id column")

    # -----------------------------
    # 6. stop_sequence ordering check
    # -----------------------------
    broken_sequence_trips = []

    for trip_id, group in stop_times.groupby("trip_id"):
        sequences = group["stop_sequence"].tolist()

        if sequences != sorted(sequences):
            broken_sequence_trips.append(str(trip_id))

    if broken_sequence_trips:
        errors.append(
            f"{len(broken_sequence_trips)} trips have unordered stop_sequence"
        )

    # -----------------------------
    # 7. time parse check
    # -----------------------------
    bad_time_rows = []

    def is_valid_gtfs_time(value):
        try:
            parts = str(value).split(":")
            if len(parts) != 3:
                return False

            h, m, s = map(int, parts)

            # GTFS allows hour > 23
            return m >= 0 and m < 60 and s >= 0 and s < 60
        except Exception:
            return False

    for idx, row in stop_times.iterrows():
        if not is_valid_gtfs_time(row["arrival_time"]):
            bad_time_rows.append(idx)

        if not is_valid_gtfs_time(row["departure_time"]):
            bad_time_rows.append(idx)

    if bad_time_rows:
        errors.append(
            f"{len(bad_time_rows)} stop_times rows have invalid arrival/departure time"
        )

    # -----------------------------
    # 8. direction_id check
    # -----------------------------
    if "direction_id" not in trips.columns:
        warnings.append("trips.txt missing direction_id; default to unknown")
    else:
        invalid_direction = trips[
            ~trips["direction_id"].isin([0, 1])
            & trips["direction_id"].notna()
        ]

        if len(invalid_direction) > 0:
            warnings.append(
                f"{len(invalid_direction)} trips have invalid direction_id"
            )

    # -----------------------------
    # 9. route mode inference check
    # -----------------------------
    if "route_type" not in routes.columns:
        warnings.append("routes.txt missing route_type; mode must be inferred manually")

    if "agency_id" not in routes.columns:
        warnings.append("routes.txt missing agency_id; Egypt mode mapping will be weaker")

    # -----------------------------
    # Final report
    # -----------------------------
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "stops": len(stops),
            "routes": len(routes),
            "trips": len(trips),
            "stop_times": len(stop_times),
            "calendar_rows": 0 if calendar is None else len(calendar)
        }
    }
}

informal_boarding.py{
    import math

from routing.nearest_stop_search import haversine_meters


INFORMAL_BOARDING_MODES = {"bus", "microbus", "minibus"}
STRICT_STOP_ONLY_MODES = {"metro", "brt", "lrt", "monorail"}
DEFAULT_WINDOW_POINTS = 80


def latlon_to_local_meters(point, reference):
    lat, lon = point
    ref_lat, ref_lon = reference
    earth_radius_meters = 6371000

    x = math.radians(lon - ref_lon) * earth_radius_meters * math.cos(
        math.radians(ref_lat)
    )
    y = math.radians(lat - ref_lat) * earth_radius_meters

    return x, y


def local_meters_to_latlon(point, reference):
    x, y = point
    ref_lat, ref_lon = reference
    earth_radius_meters = 6371000

    lat = ref_lat + math.degrees(y / earth_radius_meters)
    lon = ref_lon + math.degrees(
        x / (earth_radius_meters * math.cos(math.radians(ref_lat)))
    )

    return [lat, lon]


def project_point_to_segment(point, segment_start, segment_end):
    reference = point
    px, py = latlon_to_local_meters(point, reference)
    ax, ay = latlon_to_local_meters(segment_start, reference)
    bx, by = latlon_to_local_meters(segment_end, reference)

    dx = bx - ax
    dy = by - ay
    length_squared = dx * dx + dy * dy

    if length_squared == 0:
        return list(segment_start)

    t = ((px - ax) * dx + (py - ay) * dy) / length_squared
    t = max(0, min(1, t))

    projected_x = ax + t * dx
    projected_y = ay + t * dy

    return local_meters_to_latlon((projected_x, projected_y), reference)


def distance_point_to_segment_meters(point, segment_start, segment_end):
    projected = project_point_to_segment(point, segment_start, segment_end)
    return haversine_meters(point[0], point[1], projected[0], projected[1]), projected


def extract_shape_window_near_stop(shape, stop_lat, stop_lon, window_points=DEFAULT_WINDOW_POINTS):
    if not shape:
        return []

    stop_point = (stop_lat, stop_lon)
    nearest_index = min(
        range(len(shape)),
        key=lambda index: haversine_meters(
            stop_point[0],
            stop_point[1],
            shape[index][0],
            shape[index][1]
        )
    )

    start = max(0, nearest_index - window_points)
    end = min(len(shape), nearest_index + window_points + 1)

    return shape[start:end]


def find_nearest_shape_segment(point, shape_section):
    if len(shape_section) < 2:
        return None

    best = None

    for index in range(len(shape_section) - 1):
        segment_start = shape_section[index]
        segment_end = shape_section[index + 1]
        distance, projected = distance_point_to_segment_meters(
            point,
            segment_start,
            segment_end
        )

        if best is None or distance < best["distance_meters"]:
            best = {
                "distance_meters": distance,
                "projected_point": projected,
                "segment_start": segment_start,
                "segment_end": segment_end
            }

    return best


def get_first_transit_leg(route):
    for leg in route.get("legs", []):
        mode = str(leg.get("mode", "")).lower()

        if mode and mode != "walk":
            return leg

    return None


def unavailable(reason=None):
    result = {"available": False}

    if reason:
        result["reason"] = reason

    return result


def find_informal_boarding_suggestion(
    origin,
    route,
    shape_points,
    trip_shapes,
    stop_details,
    route_modes,
    walking_speed_mps=1.3,
    window_points=DEFAULT_WINDOW_POINTS,
):
    first_transit_leg = get_first_transit_leg(route)

    if first_transit_leg is None:
        return unavailable("no_transit_leg")

    mode = str(first_transit_leg.get("mode", "")).lower()
    route_id = first_transit_leg.get("route_id")

    if not mode or mode == "unknown":
        mode = route_modes.get(route_id, "unknown")

    if mode in STRICT_STOP_ONLY_MODES:
        return unavailable("strict_stop_mode")

    if mode not in INFORMAL_BOARDING_MODES:
        return unavailable("mode_not_supported")

    trip_id = first_transit_leg.get("trip_id")

    if not trip_id:
        return unavailable("missing_trip_id")

    shape_id = trip_shapes.get(trip_id)

    if not shape_id:
        return unavailable("missing_shape_id")

    shape = shape_points.get(shape_id, [])

    if len(shape) < 2:
        return unavailable("missing_shape_points")

    official_stop_id = str(first_transit_leg.get("from_stop_id"))
    official_stop = (
        first_transit_leg.get("from_stop")
        or stop_details.get(official_stop_id)
    )

    if not official_stop or "lat" not in official_stop or "lon" not in official_stop:
        return unavailable("missing_official_stop_location")

    origin_point = (float(origin["lat"]), float(origin["lon"]))
    official_stop_point = (
        float(official_stop["lat"]),
        float(official_stop["lon"])
    )
    official_distance = haversine_meters(
        origin_point[0],
        origin_point[1],
        official_stop_point[0],
        official_stop_point[1]
    )

    shape_window = extract_shape_window_near_stop(
        shape,
        official_stop_point[0],
        official_stop_point[1],
        window_points=window_points
    )
    nearest_segment = find_nearest_shape_segment(origin_point, shape_window)

    if nearest_segment is None:
        return unavailable("no_nearby_shape_segment")

    corridor_distance = nearest_segment["distance_meters"]
    saving = official_distance - corridor_distance

    if saving <= 0:
        return unavailable("segment_not_closer_than_stop")

    projected = nearest_segment["projected_point"]

    return {
        "available": True,
        "mode": mode,
        "route_id": route_id,
        "route_label": first_transit_leg.get("route_label"),
        "trip_id": trip_id,
        "shape_id": shape_id,
        "official_boarding_stop_id": official_stop_id,
        "official_boarding_stop_name": official_stop.get("name"),
        "official_walk_distance_meters": round(official_distance, 2),
        "suggested_point": {
            "lat": projected[0],
            "lon": projected[1]
        },
        "suggested_walk_distance_meters": round(corridor_distance, 2),
        "walking_time_seconds": int(corridor_distance / walking_speed_mps),
        "distance_saving_meters": round(saving, 2),
        "confidence": "medium",
        "timing_accuracy": "approximate",
        "message": (
            "This route passes closer to your location than the official stop. "
            "Informal boarding may be possible from the suggested corridor point."
        )
    }

}

journey_scorer.py{
    MODE_COSTS = {
    "metro": -300,
    "lrt": -220,
    "brt": -180,
    "bus": 0,
    "minibus": 120,
    "microbus": 180,
}
BACKBONE_MODES = {"metro", "lrt", "brt"}
SURFACE_MODES = {"bus", "minibus", "microbus"}
MODE_SWITCH_PENALTY = 300
BACKBONE_EXIT_PENALTY = 600
EXTRA_FRAGMENTED_LEG_PENALTY = 250


def calculate_path_stats(path):
    transit_leg_count = 0
    walking_time = 0
    waiting_time = 0

    for leg in path:
        if leg["mode"] == "walk":
            walking_time += int(leg.get("walking_time", 0))
        else:
            transit_leg_count += 1
            waiting_time += int(leg.get("waiting_time", 0))

    transfer_count = max(0, transit_leg_count - 1)

    return {
        "transit_leg_count": transit_leg_count,
        "transfer_count": transfer_count,
        "walking_time": walking_time,
        "waiting_time": waiting_time,
    }


def calculate_mode_adjustment(path):
    adjustment = 0
    breakdown = {}

    for leg in path:
        mode = leg.get("mode")

        if mode == "walk":
            continue

        mode_cost = MODE_COSTS.get(mode, 0)
        adjustment += mode_cost
        breakdown[mode] = breakdown.get(mode, 0) + mode_cost

    return adjustment, breakdown


def get_transit_modes(path):
    return [
        leg.get("mode")
        for leg in path
        if leg.get("mode") != "walk"
    ]


def calculate_mode_switch_penalty(path):
    transit_modes = get_transit_modes(path)
    penalty = 0
    breakdown = {
        "mode_switch_count": 0,
        "backbone_exit_count": 0,
        "extra_fragmented_leg_count": max(0, len(transit_modes) - 2),
    }

    for previous_mode, next_mode in zip(transit_modes, transit_modes[1:]):
        if previous_mode == next_mode:
            continue

        penalty += MODE_SWITCH_PENALTY
        breakdown["mode_switch_count"] += 1

        if previous_mode in BACKBONE_MODES and next_mode in SURFACE_MODES:
            penalty += BACKBONE_EXIT_PENALTY
            breakdown["backbone_exit_count"] += 1

    penalty += (
        breakdown["extra_fragmented_leg_count"]
        * EXTRA_FRAGMENTED_LEG_PENALTY
    )

    return penalty, breakdown


def score_journey(
    travel_time: int,
    waiting_time: int,
    walking_time: int,
    transfer_count: int,
    final_walking_time: int = 0,
    mode_adjustment: int = 0,
    mode_switch_penalty: int = 0,
):
    breakdown = {
        "travel_time": travel_time,
        "waiting_penalty": waiting_time * 1.5,
        "walking_penalty": walking_time * 2.0,
        "transfer_penalty": transfer_count * 600,
        "final_walking_penalty": final_walking_time * 2.5,
        "mode_adjustment": mode_adjustment,
        "mode_switch_penalty": mode_switch_penalty,
    }

    return {
        "total_cost": sum(breakdown.values()),
        "breakdown": breakdown,
    }


def score_path(path, total_travel_time, final_walking_time=0):
    transit_leg_count = 0
    walking_time = 0
    waiting_time = 0
    mode_adjustment = 0
    mode_breakdown = {}
    previous_transit_mode = None
    mode_switch_penalty = 0
    mode_switch_count = 0
    backbone_exit_count = 0

    for leg in path:
        mode = leg.get("mode")

        if mode == "walk":
            walking_time += int(leg.get("walking_time", 0))
            continue

        transit_leg_count += 1
        waiting_time += int(leg.get("waiting_time", 0))

        mode_cost = MODE_COSTS.get(mode, 0)
        mode_adjustment += mode_cost
        mode_breakdown[mode] = mode_breakdown.get(mode, 0) + mode_cost

        if previous_transit_mode is not None and previous_transit_mode != mode:
            mode_switch_penalty += MODE_SWITCH_PENALTY
            mode_switch_count += 1

            if previous_transit_mode in BACKBONE_MODES and mode in SURFACE_MODES:
                mode_switch_penalty += BACKBONE_EXIT_PENALTY
                backbone_exit_count += 1

        previous_transit_mode = mode

    transfer_count = max(0, transit_leg_count - 1)
    extra_fragmented_leg_count = max(0, transit_leg_count - 2)
    mode_switch_penalty += (
        extra_fragmented_leg_count
        * EXTRA_FRAGMENTED_LEG_PENALTY
    )
    stats = {
        "transit_leg_count": transit_leg_count,
        "transfer_count": transfer_count,
        "walking_time": walking_time,
        "waiting_time": waiting_time,
    }
    has_transit = stats["transit_leg_count"] > 0
    effective_final_walking_time = final_walking_time if has_transit else 0
    mode_switch_breakdown = {
        "mode_switch_count": mode_switch_count,
        "backbone_exit_count": backbone_exit_count,
        "extra_fragmented_leg_count": extra_fragmented_leg_count,
    }
    score = score_journey(
        travel_time=total_travel_time,
        waiting_time=stats["waiting_time"],
        walking_time=stats["walking_time"],
        transfer_count=stats["transfer_count"],
        final_walking_time=effective_final_walking_time,
        mode_adjustment=mode_adjustment,
        mode_switch_penalty=mode_switch_penalty,
    )

    score["mode_breakdown"] = mode_breakdown
    score["mode_switch_breakdown"] = mode_switch_breakdown
    score["stats"] = stats

    return score

}

mode_mapper.py{
    def infer_route_mode(route):
    agency_id = str(route.get("agency_id", "")).upper()
    route_type = str(route.get("route_type", ""))
    route_long_name = str(route.get("route_long_name", "")).upper()
    route_short_name = str(route.get("route_short_name", "")).upper()

    text = f"{agency_id} {route_long_name} {route_short_name}"

    # Egypt/Cairo agency-specific mapping.
    agency_mode_map = {
        "CTA": "bus",
        "CTA_M": "minibus",
        "MM": "bus",
        "GRN": "bus",
        "P_O_14": "microbus",
        "P_B_8": "microbus",
        "COOP": "microbus",
        "BOX": "microbus",
        "LTRA_M": "minibus",
    }

    if agency_id in agency_mode_map:
        return agency_mode_map[agency_id]

    # Text-based overrides.
    if "BRT" in text:
        return "brt"
    if "LRT" in text:
        return "lrt"
    if "MONORAIL" in text:
        return "monorail"
    if "METRO" in text:
        return "metro"
    if "MICROBUS" in text:
        return "microbus"
    if "MINIBUS" in text:
        return "minibus"

    # GTFS route_type fallback.
    if route_type == "1":
        return "metro"
    if route_type == "0":
        return "lrt"
    if route_type == "3":
        return "bus"

    return "bus"


def build_route_modes(routes):
    route_modes = {}

    for _, route in routes.iterrows():
        route_id = str(route["route_id"])
        route_modes[route_id] = infer_route_mode(route)

    return route_modes

}

nearest_stop_search.py{
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

}

postprocessing.py{
    def merge_adjacent_walk_legs(raw_legs):
    merged_legs = []

    for leg in raw_legs:
        if (
            merged_legs
            and leg["mode"] == "walk"
            and merged_legs[-1]["mode"] == "walk"
        ):
            previous_leg = merged_legs[-1]
            previous_leg["to_stop_id"] = leg["to_stop_id"]
            previous_leg["to_stop"] = leg.get("to_stop")
            previous_leg["arrival_time"] = leg["arrival_time"]
            previous_leg["walking_time"] = (
                int(previous_leg.get("walking_time", 0))
                + int(leg.get("walking_time", 0))
            )
            previous_distance = previous_leg.get("distance_meters") or 0
            current_distance = leg.get("distance_meters") or 0
            previous_leg["distance_meters"] = round(
                float(previous_distance) + float(current_distance),
                2
            )
            previous_leg["waiting_time"] = 0
            previous_leg["route_id"] = None
            previous_leg["trip_id"] = None
            previous_leg["route_label"] = None
            if leg.get("walk_type") and not previous_leg.get("walk_type"):
                previous_leg["walk_type"] = leg.get("walk_type")
            if leg.get("source") and not previous_leg.get("source"):
                previous_leg["source"] = leg.get("source")
            if leg.get("confidence") and not previous_leg.get("confidence"):
                previous_leg["confidence"] = leg.get("confidence")
            continue

        merged_legs.append(dict(leg))

    return merged_legs


def normalize_metro_platform_stop_id(stop_id):
    stop_id = str(stop_id)

    for suffix in ["_METRO_N", "_METRO_S", "_METRO_E", "_METRO_W"]:
        if stop_id.endswith(suffix):
            return stop_id[:-len(suffix)]

    return stop_id


def is_zero_distance_platform_walk(leg):
    if leg["mode"] != "walk":
        return False

    walking_time = int(leg.get("walking_time", 0))
    distance = float(leg.get("distance_meters") or 0)

    if walking_time > 0 or distance > 0:
        return False

    from_stop_id = leg.get("from_stop_id")
    to_stop_id = leg.get("to_stop_id")

    if from_stop_id == to_stop_id:
        return True

    return (
        normalize_metro_platform_stop_id(from_stop_id)
        == normalize_metro_platform_stop_id(to_stop_id)
    )


def remove_tiny_walks(raw_legs, min_walking_time=5):
    cleaned_legs = []

    for index, leg in enumerate(raw_legs):
        if leg["mode"] != "walk":
            cleaned_legs.append(leg)
            continue

        walking_time = int(leg.get("walking_time", 0))
        is_first_or_last = index == 0 or index == len(raw_legs) - 1
        is_same_stop = leg.get("from_stop_id") == leg.get("to_stop_id")

        if (
            is_zero_distance_platform_walk(leg)
            or is_same_stop
            or (walking_time <= min_walking_time and not is_first_or_last)
        ):
            continue

        cleaned_legs.append(leg)

    return cleaned_legs


def simplify_legs(raw_legs):
    legs = merge_adjacent_walk_legs(raw_legs)
    legs = remove_tiny_walks(legs)
    return merge_adjacent_walk_legs(legs)


def simplify_route(raw_result):
    if not raw_result.get("found"):
        return raw_result

    simplified = dict(raw_result)
    simplified["legs"] = simplify_legs(raw_result.get("legs", []))
    return simplified

}

rail_projects_shapefile.py{
    import math
import struct
from pathlib import Path


LRT_SHAPE_SEGMENTS = {
    "LRT_ADLY_10RAMADAN_0": [
        ("ET2", "LRT_ADLY_MANSOUR", "LRT_BADR"),
        ("ET1", "LRT_BADR", "LRT_NEW_OBOUR"),
        ("ET1", "LRT_NEW_OBOUR", "LRT_CITY_CENTER"),
    ],
    "LRT_ADLY_10RAMADAN_1": [
        ("ET1", "LRT_CITY_CENTER", "LRT_NEW_OBOUR"),
        ("ET1", "LRT_NEW_OBOUR", "LRT_BADR"),
        ("ET2", "LRT_BADR", "LRT_ADLY_MANSOUR"),
    ],
    "LRT_ADLY_CAPITAL_0": [
        ("ET2", "LRT_ADLY_MANSOUR", "LRT_ARTS_CULTURE"),
        ("ET2", "LRT_ARTS_CULTURE", "LRT_CENTRAL_CAPITAL"),
    ],
    "LRT_ADLY_CAPITAL_1": [
        ("ET2", "LRT_CENTRAL_CAPITAL", "LRT_ARTS_CULTURE"),
        ("ET2", "LRT_ARTS_CULTURE", "LRT_ADLY_MANSOUR"),
    ],
}


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
    return radius_meters * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cumulative_distances(points):
    distances = [0.0]

    for previous, current in zip(points, points[1:]):
        distances.append(
            distances[-1]
            + haversine_meters(
                previous["lat"],
                previous["lon"],
                current["lat"],
                current["lon"],
            )
        )

    return distances


def read_projection(shapefile_path):
    prj_path = Path(shapefile_path).with_suffix(".prj")

    if not prj_path.exists():
        return None

    return prj_path.read_text(encoding="utf-8", errors="replace").strip()


def read_dbf_records(dbf_path):
    records = []

    with Path(dbf_path).open("rb") as handle:
        header = handle.read(32)
        record_count = struct.unpack("<I", header[4:8])[0]
        record_length = struct.unpack("<H", header[10:12])[0]
        fields = []

        while True:
            field_descriptor = handle.read(32)

            if field_descriptor[0] == 0x0D:
                break

            field_name = (
                field_descriptor[:11]
                .split(b"\x00", 1)[0]
                .decode("ascii", errors="replace")
            )
            field_type = chr(field_descriptor[11])
            field_length = field_descriptor[16]
            decimal_count = field_descriptor[17]
            fields.append({
                "name": field_name,
                "type": field_type,
                "length": field_length,
                "decimal_count": decimal_count,
            })

        for _ in range(record_count):
            raw_record = handle.read(record_length)

            if not raw_record or raw_record[:1] == b"*":
                continue

            position = 1
            record = {}

            for field in fields:
                raw_value = raw_record[position:position + field["length"]]
                position += field["length"]
                record[field["name"]] = raw_value.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

            records.append(record)

    return fields, records


def read_shp_polylines(shp_path):
    polylines = []

    with Path(shp_path).open("rb") as handle:
        header = handle.read(100)
        shape_type = struct.unpack("<i", header[32:36])[0]
        bbox = struct.unpack("<4d", header[36:68])

        while True:
            record_header = handle.read(8)

            if not record_header:
                break

            record_number, record_length_words = struct.unpack(">2i", record_header)
            content = handle.read(record_length_words * 2)

            if len(content) < 44:
                continue

            record_shape_type = struct.unpack("<i", content[:4])[0]

            if record_shape_type != 3:
                continue

            record_bbox = struct.unpack("<4d", content[4:36])
            part_count, point_count = struct.unpack("<2i", content[36:44])
            parts_offset = 44
            points_offset = parts_offset + 4 * part_count
            points = []

            for point_index in range(point_count):
                offset = points_offset + point_index * 16
                lon, lat = struct.unpack("<2d", content[offset:offset + 16])
                points.append({"lat": lat, "lon": lon})

            polylines.append({
                "record_number": record_number,
                "shape_type": record_shape_type,
                "bbox": record_bbox,
                "part_count": part_count,
                "point_count": point_count,
                "points": points,
            })

    return {
        "shape_type": shape_type,
        "bbox": bbox,
        "records": polylines,
    }


def load_rail_project_records(shapefile_path):
    shapefile_path = Path(shapefile_path)
    dbf_path = shapefile_path.with_suffix(".dbf")

    if not shapefile_path.exists() or not dbf_path.exists():
        return None

    fields, dbf_records = read_dbf_records(dbf_path)
    shp_data = read_shp_polylines(shapefile_path)
    records = []

    for attributes, geometry in zip(dbf_records, shp_data["records"]):
        records.append({
            "attributes": attributes,
            "geometry": geometry,
        })

    return {
        "projection": read_projection(shapefile_path),
        "shape_type": shp_data["shape_type"],
        "bbox": shp_data["bbox"],
        "fields": fields,
        "records": records,
    }


def nearest_point_index(points, stop):
    stop_lat = float(stop["stop_lat"])
    stop_lon = float(stop["stop_lon"])
    best_index = None
    best_distance = float("inf")

    for index, point in enumerate(points):
        distance = haversine_meters(
            stop_lat,
            stop_lon,
            point["lat"],
            point["lon"],
        )

        if distance < best_distance:
            best_index = index
            best_distance = distance

    return best_index, best_distance


def extract_segment_points(records, route_id, start_stop, end_stop, max_endpoint_distance_m=600):
    candidates = []

    for record in records:
        attributes = record["attributes"]

        if attributes.get("route_id") != route_id:
            continue

        points = record["geometry"]["points"]
        start_index, start_distance = nearest_point_index(points, start_stop)
        end_index, end_distance = nearest_point_index(points, end_stop)

        if start_index is None or end_index is None:
            continue

        if start_index >= end_index:
            continue

        if start_distance > max_endpoint_distance_m or end_distance > max_endpoint_distance_m:
            continue

        candidates.append({
            "record": record,
            "start_index": start_index,
            "end_index": end_index,
            "start_distance_m": start_distance,
            "end_distance_m": end_distance,
            "score": start_distance + end_distance,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda candidate: candidate["score"])
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    if second and abs(second["score"] - best["score"]) < 1:
        return None

    points = best["record"]["geometry"]["points"][
        best["start_index"]:best["end_index"] + 1
    ]

    return {
        "points": points,
        "record_number": best["record"]["geometry"]["record_number"],
        "source_route_id": route_id,
        "source_route_long": best["record"]["attributes"].get("route_long", ""),
        "source_status": best["record"]["attributes"].get("status", ""),
        "start_distance_m": round(best["start_distance_m"], 2),
        "end_distance_m": round(best["end_distance_m"], 2),
    }


def build_shape_rows_from_rail_projects(shapefile_path, stops_by_id):
    dataset = load_rail_project_records(shapefile_path)

    if dataset is None:
        return None, {
            "used": False,
            "reason": "shapefile_or_dbf_missing",
        }

    lrt_records = [
        record for record in dataset["records"]
        if record["attributes"].get("status") == "ET(LRT)"
    ]
    report = {
        "used": False,
        "source": str(shapefile_path),
        "projection": dataset["projection"],
        "shape_type": dataset["shape_type"],
        "bbox": dataset["bbox"],
        "dbf_columns": dataset["fields"],
        "lrt_record_count": len(lrt_records),
        "lrt_records": [
            {
                "record_number": record["geometry"]["record_number"],
                "route_id": record["attributes"].get("route_id"),
                "route_short_name": record["attributes"].get("route_shor"),
                "route_long_name": (
                    record["attributes"].get("route_long", "")
                    + record["attributes"].get("route_desc", "")
                ).strip(),
                "status": record["attributes"].get("status"),
                "point_count": record["geometry"]["point_count"],
                "part_count": record["geometry"]["part_count"],
            }
            for record in lrt_records
        ],
        "shape_mappings": [],
        "skipped": [],
    }

    shape_rows = []

    for shape_id, segments in LRT_SHAPE_SEGMENTS.items():
        stitched_points = []
        segment_reports = []

        for source_route_id, start_stop_id, end_stop_id in segments:
            segment = extract_segment_points(
                dataset["records"],
                source_route_id,
                stops_by_id[start_stop_id],
                stops_by_id[end_stop_id],
            )

            if segment is None:
                report["skipped"].append({
                    "shape_id": shape_id,
                    "source_route_id": source_route_id,
                    "from_stop_id": start_stop_id,
                    "to_stop_id": end_stop_id,
                    "reason": "missing_or_ambiguous_segment",
                })
                return None, report

            segment_points = segment["points"]

            if stitched_points and segment_points:
                previous = stitched_points[-1]
                current = segment_points[0]
                if haversine_meters(
                    previous["lat"],
                    previous["lon"],
                    current["lat"],
                    current["lon"],
                ) < 5:
                    segment_points = segment_points[1:]

            stitched_points.extend(segment_points)
            segment_reports.append({
                key: value
                for key, value in segment.items()
                if key != "points"
            })

        distances = cumulative_distances(stitched_points)
        report["shape_mappings"].append({
            "shape_id": shape_id,
            "segments": segment_reports,
            "point_count": len(stitched_points),
            "distance_km": round(distances[-1] / 1000, 3) if distances else 0,
        })

        for index, point in enumerate(stitched_points):
            shape_rows.append({
                "shape_id": shape_id,
                "shape_pt_lat": round(point["lat"], 7),
                "shape_pt_lon": round(point["lon"], 7),
                "shape_pt_sequence": index + 1,
                "shape_dist_traveled": round(distances[index] / 1000, 3),
            })

    report["used"] = True
    report["generated_shape_points"] = len(shape_rows)
    return shape_rows, report


}

raptor_index_builder.py{
    import pandas as pd
from routing.mode_mapper import build_route_modes


def time_to_seconds(t):
    h, m, s = map(int, str(t).split(":"))
    return h * 3600 + m * 60 + s


def normalize_direction_id(value):
    if pd.isna(value):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_route_labels(routes):
    generic_route_labels = {"BUS", "MICROBUS", "MINIBUS", "NAN", ""}
    route_labels = {}

    for _, row in routes.iterrows():
        route_id = str(row["route_id"])

        short_name = str(row.get("route_short_name", "")).strip()
        long_name = str(row.get("route_long_name", "")).strip()

        short_upper = short_name.upper()
        long_upper = long_name.upper()

        if short_name and short_upper not in generic_route_labels:
            route_labels[route_id] = short_name
        elif long_name and long_upper not in generic_route_labels:
            route_labels[route_id] = long_name
        else:
            route_labels[route_id] = route_id

    return route_labels


def build_stop_details(stops):
    stop_details = {}

    for _, row in stops.iterrows():
        stop_id = str(row["stop_id"])

        stop_details[stop_id] = {
            "stop_id": stop_id,
            "name": str(row.get("stop_name", "")),
            "lat": float(row["stop_lat"]),
            "lon": float(row["stop_lon"])
        }

    return stop_details


def build_shape_points(shapes):
    shape_points = {}

    for shape_id, group in shapes.groupby("shape_id"):
        points = []

        group = group.sort_values("shape_pt_sequence")

        for _, row in group.iterrows():
            points.append([
                float(row["shape_pt_lat"]),
                float(row["shape_pt_lon"])
            ])

        shape_points[str(shape_id)] = points

    return shape_points


def build_trip_shapes(trips):
    if "shape_id" not in trips.columns:
        return {}

    trip_shapes = {}

    for _, row in trips.iterrows():
        trip_shapes[str(row["trip_id"])] = str(row["shape_id"])

    return trip_shapes


def build_raptor_indexes(stop_times, trips, routes=None, stops=None, shapes=None):
    trips = trips.copy()
    route_modes = build_route_modes(routes) if routes is not None else {}
    route_labels = build_route_labels(routes) if routes is not None else {}
    stop_details = build_stop_details(stops) if stops is not None else {}
    shape_points = build_shape_points(shapes) if shapes is not None else {}
    trip_shapes = build_trip_shapes(trips)

    if "direction_id" not in trips.columns:
        trips["direction_id"] = None

    # Merge route_id + direction_id into stop_times.
    stop_times = stop_times.merge(
        trips[["trip_id", "route_id", "direction_id"]],
        on="trip_id",
        how="left"
    )

    stop_times = stop_times.sort_values(
        by=["trip_id", "stop_sequence"]
    )

    routes_by_stop = {}
    stops_by_route = {}
    trips_by_route = {}
    stop_times_by_trip = {}
    stop_index_by_route = {}
    trip_stop_index = {}

    # 1. stop_times_by_trip
    for row in stop_times.itertuples(index=False):
        trip_id = str(row.trip_id)
        trip_stop_times = stop_times_by_trip.setdefault(trip_id, [])
        trip_stop_times.append({
            "stop_id": str(row.stop_id),
            "arrival_time": time_to_seconds(row.arrival_time),
            "departure_time": time_to_seconds(row.departure_time),
            "stop_sequence": int(row.stop_sequence),
            "route_id": str(row.route_id),
            "direction_id": normalize_direction_id(row.direction_id)
        })

    for trip_id, trip_times in stop_times_by_trip.items():
        trip_stop_index[trip_id] = {
            st["stop_id"]: idx
            for idx, st in enumerate(trip_times)
        }

    # 2. trips_by_route
    for row in trips.itertuples(index=False):
        trips_by_route.setdefault(str(row.route_id), []).append(str(row.trip_id))

    # 3. stops_by_route and routes_by_stop
    route_stop_rows = (
        stop_times[["route_id", "stop_id", "stop_sequence"]]
        .sort_values(["route_id", "stop_sequence"])
        .drop_duplicates(["route_id", "stop_id"])
    )

    route_stop_groups = {}

    for row in route_stop_rows.itertuples(index=False):
        route_stop_groups.setdefault(str(row.route_id), []).append(str(row.stop_id))

    for route_id, route_stops in route_stop_groups.items():
        stops_by_route[route_id] = route_stops

        stop_index_by_route[route_id] = {
            stop_id: idx for idx, stop_id in enumerate(route_stops)
        }

        for stop_id in route_stops:
            routes_by_stop.setdefault(stop_id, set()).add(route_id)

    # Convert sets to lists for JSON compatibility.
    routes_by_stop = {
        stop_id: list(route_ids)
        for stop_id, route_ids in routes_by_stop.items()
    }

    return {
        "routes_by_stop": routes_by_stop,
        "stops_by_route": stops_by_route,
        "trips_by_route": trips_by_route,
        "stop_times_by_trip": stop_times_by_trip,
        "stop_index_by_route": stop_index_by_route,
        "route_modes": route_modes,
        "route_labels": route_labels,
        "stop_details": stop_details,
        "shape_points": shape_points,
        "trip_shapes": trip_shapes,
        "trip_stop_index": trip_stop_index
    }

}

raptor_router.py{
    from routing.eta_provider import build_segment_id
from routing.fare_calculator import calculate_path_fare
from routing.journey_scorer import calculate_path_stats, score_path
from routing.nearest_stop_search import haversine_meters
from routing.postprocessing import simplify_legs
import time


INF = 10**18
WALKING_SPEED_MPS = 1.3
MAX_DIRECT_WALK_METERS = 1000
MAX_LABELS_PER_STOP = 6
MAX_BOARDING_LABELS_PER_ROUTE = 12
MAX_NEW_LABELS_PER_ROUND = 3000
ROUTE_MODE_PRIORITY = {
    "metro": 0,
    "subway": 0,
    "brt": 1,
    "lrt": 2,
    "tram": 2,
    "monorail": 3,
    "bus": 4,
    "minibus": 5,
    "microbus": 6,
}
METRO_TRACE_STOP_MARKERS = (
    "SHB_METRO",
    "SHO_METRO",
    "SAD_METRO",
    "MGR_METRO",
)
METRO_TRACE_STOP_NAMES = (
    "SADAT",
    "MAR GIRGIS",
    "AL-SHOHADAA",
    "SHUBRA EL-KHEIMA",
)
BRT_TRACE_STOP_IDS = (
    "BRT_KHOSOUS",
    "BRT_MARG",
    "BRT_BAHTEEM",
    "BRT_ADLY_MANSOUR",
    "BRT_NAZLET_QALYUB",
    "BRT_POLICE_ACADEMY",
)
TRUNK_BACKTRACK_GUARD_MODES = {
    "metro",
    "brt",
    "lrt",
    "monorail",
}
TRUNK_MODES = {"metro", "brt", "lrt", "monorail"}
SURFACE_MODES = {"bus", "microbus", "minibus"}
MAX_NON_TRUNK_TRANSFERS = 2
LEAST_WALKING_MAX_RECOMMENDED_RATIO = 2.0


def normalize_route_mode(mode):
    return str(mode or "unknown").strip().lower()


def route_scan_priority(route_id, route_modes):
    route_mode = normalize_route_mode(route_modes.get(route_id))
    return ROUTE_MODE_PRIORITY.get(route_mode, 99)


def route_scan_sort_key(route_id, route_modes, route_labels):
    route_mode = normalize_route_mode(route_modes.get(route_id))
    route_label = str(route_labels.get(route_id, route_id))

    return (
        route_scan_priority(route_id, route_modes),
        route_mode,
        route_label,
        str(route_id),
    )


def increment_count(mapping, key, amount=1):
    mapping[key] = mapping.get(key, 0) + amount


def canonical_stop_id_for_signature(stop_id):
    stop_id = str(stop_id)

    for suffix in ("_N2", "_S2", "_N", "_S", "_E", "_W"):
        if "_METRO" in stop_id and stop_id.endswith(suffix):
            return stop_id[:-len(suffix)]

    return stop_id


def label_mode_for_stats(label):
    for leg in reversed(label.get("path") or []):
        mode = normalize_route_mode(leg.get("mode"))

        if mode:
            return mode

    return "access"


def round_stats(label_stats, round_number):
    key = str(round_number)

    if key not in label_stats["rounds"]:
        label_stats["rounds"][key] = {
            "round_number": round_number,
            "labels_created": 0,
            "labels_accepted": 0,
            "labels_rejected_by_dominance": 0,
            "existing_labels_removed_by_dominance": 0,
            "dominance_checks": 0,
            "labels_created_by_mode": {},
            "labels_accepted_by_mode": {},
        }

    return label_stats["rounds"][key]


def get_eta_estimate(
    eta_estimates,
    route_id,
    direction_id,
    from_stop_id,
    to_stop_id
):
    segment_id = build_segment_id(
        route_id,
        direction_id,
        from_stop_id,
        to_stop_id
    )

    if not eta_estimates:
        return segment_id, None

    estimate = eta_estimates.get(segment_id)

    if estimate is not None:
        return segment_id, estimate

    fallback_segment_id = build_segment_id(
        route_id,
        None,
        from_stop_id,
        to_stop_id
    )

    estimate = eta_estimates.get(fallback_segment_id)

    if estimate is None:
        return segment_id, None

    return fallback_segment_id, estimate


def resolve_segment_travel_time(
    eta_estimates,
    route_id,
    direction_id,
    from_stop,
    to_stop
):
    scheduled_travel_time = max(
        0,
        int(to_stop["arrival_time"]) - int(from_stop["departure_time"])
    )
    segment_id, estimate = get_eta_estimate(
        eta_estimates,
        route_id,
        direction_id,
        from_stop["stop_id"],
        to_stop["stop_id"]
    )

    if not estimate:
        return scheduled_travel_time, {
            "segment_id": segment_id,
            "source": "gtfs_schedule",
            "scheduled_travel_time": scheduled_travel_time
        }

    if estimate.get("predicted_travel_time") is not None:
        travel_time = max(0, int(estimate["predicted_travel_time"]))
    else:
        predicted_delay = int(estimate.get("predicted_delay", 0))
        travel_time = max(0, scheduled_travel_time + predicted_delay)

    return travel_time, {
        "segment_id": segment_id,
        "source": "eta_engine",
        "scheduled_travel_time": scheduled_travel_time,
        "predicted_travel_time": travel_time,
        "predicted_delay": estimate.get("predicted_delay"),
        "confidence": estimate.get("confidence"),
        "timestamp": estimate.get("timestamp")
    }


def apply_walking_transfers(
    from_stops,
    arrival_times,
    paths,
    walking_transfers,
    new_marked_stops,
    round_number
):
    for from_stop_id in from_stops:
        if from_stop_id not in arrival_times:
            continue

        from_time = arrival_times[from_stop_id]
        from_path = paths.get(from_stop_id, [])

        for edge in walking_transfers.get(from_stop_id, []):
            to_stop_id = edge["to"]
            walking_time = edge["walking_time"]
            arrival_time = from_time + walking_time

            if arrival_time < arrival_times.get(to_stop_id, INF):
                arrival_times[to_stop_id] = arrival_time
                new_marked_stops.add(to_stop_id)

                leg = {
                    "from_stop_id": from_stop_id,
                    "to_stop_id": to_stop_id,
                    "route_id": None,
                    "trip_id": None,
                    "mode": "walk",
                    "departure_time": from_time,
                    "arrival_time": arrival_time,
                    "waiting_time": 0,
                    "distance_meters": edge.get("distance_meters"),
                    "walking_time": walking_time,
                    "route_label": None,
                    "round": round_number
                }
                paths[to_stop_id] = from_path + [leg]


def find_earliest_trip_on_route(
    route_id,
    trips_by_route,
    stop_times_by_trip,
    trip_stop_index,
    boarding_stop_id,
    earliest_board_time
):
    """
    Find the earliest trip on route_id that can be boarded at boarding_stop_id
    after earliest_board_time.
    """

    best_trip_id = None
    best_trip_times = None
    best_departure_time = INF
    best_board_index = None

    for trip_id in trips_by_route.get(route_id, []):
        idx = trip_stop_index.get(trip_id, {}).get(boarding_stop_id)

        if idx is None:
            continue

        trip_times = stop_times_by_trip.get(trip_id, [])

        if not trip_times:
            continue

        dep = trip_times[idx]["departure_time"]

        if dep >= earliest_board_time and dep < best_departure_time:
            best_trip_id = trip_id
            best_trip_times = trip_times
            best_departure_time = dep
            best_board_index = idx

    return best_trip_id, best_trip_times, best_departure_time, best_board_index


def find_earliest_trips_on_route_by_direction(
    route_id,
    trips_by_route,
    stop_times_by_trip,
    trip_stop_index,
    boarding_stop_id,
    earliest_board_time
):
    best_by_direction = {}

    for trip_id in trips_by_route.get(route_id, []):
        idx = trip_stop_index.get(trip_id, {}).get(boarding_stop_id)

        if idx is None:
            continue

        trip_times = stop_times_by_trip.get(trip_id, [])

        if not trip_times:
            continue

        dep = trip_times[idx]["departure_time"]

        if dep < earliest_board_time:
            continue

        direction_id = trip_times[idx].get("direction_id")
        direction_key = direction_id if direction_id is not None else trip_id
        existing = best_by_direction.get(direction_key)

        if existing is None or dep < existing[2]:
            best_by_direction[direction_key] = (
                trip_id,
                trip_times,
                dep,
                idx,
            )

    return sorted(best_by_direction.values(), key=lambda item: item[2])


def make_label(stop_id, arrival_time, path, departure_time_seconds):
    score = score_path(path, arrival_time - departure_time_seconds)

    return {
        "stop_id": str(stop_id),
        "arrival_time": arrival_time,
        "path": path,
        "score": score,
    }


def label_sequences(label):
    path = label.get("path", [])

    return {
        "mode_sequence": [
            leg.get("mode")
            for leg in path
        ],
        "route_sequence": [
            leg.get("route_label") or leg.get("route_id") or "walk"
            for leg in path
        ],
    }


def label_trace_summary(label, stop_details=None):
    stats = label["score"]["stats"]
    sequences = label_sequences(label)
    stop_id = str(label["stop_id"])
    stop = (stop_details or {}).get(stop_id, {})

    return {
        "stop_id": stop_id,
        "stop_name": stop.get("name"),
        "arrival_time": label["arrival_time"],
        "transfer_count": stats["transfer_count"],
        "total_cost": label["score"]["total_cost"],
        "walking_time": stats["walking_time"],
        "waiting_time": stats["waiting_time"],
        **sequences,
    }


def label_transit_modes(label):
    return [
        mode
        for mode in label_sequences(label)["mode_sequence"]
        if mode != "walk"
    ]


def is_metro_only_label(label):
    transit_modes = label_transit_modes(label)

    return bool(transit_modes) and all(
        mode == "metro"
        for mode in transit_modes
    )


def is_metro_candidate_label(label):
    return "metro" in label_transit_modes(label)


def is_trace_focus_stop(stop_id, stop_details, trace_mode="metro"):
    stop_id = str(stop_id)

    if trace_mode == "brt":
        return stop_id in BRT_TRACE_STOP_IDS or stop_id.startswith("BRT_")

    if trace_mode == "lrt":
        return stop_id.startswith("LRT_")

    if any(marker in stop_id.upper() for marker in METRO_TRACE_STOP_MARKERS):
        return True

    stop_name = str(
        (stop_details or {}).get(stop_id, {}).get("name", "")
    ).upper()

    return (
        any(marker == stop_name for marker in METRO_TRACE_STOP_NAMES)
        and (
            "METRO" in stop_id.upper()
            or "METRO" in stop_name
        )
    )


def should_trace_label(label, trace):
    if not trace:
        return False

    transit_modes = label_transit_modes(label)
    focus_stop = is_trace_focus_stop(
        label["stop_id"],
        trace.get("stop_details", {}),
        trace.get("mode", "metro"),
    )

    if trace.get("mode") == "brt":
        return focus_stop or "brt" in transit_modes

    if trace.get("mode") == "lrt":
        return focus_stop or "lrt" in transit_modes

    return (
        focus_stop
        and (
            not transit_modes
            or "metro" in transit_modes
        )
    )


def create_trace_context(trace_mode, stop_details):
    if trace_mode not in {"metro", "brt", "lrt"}:
        return None

    focus_stops = [
        {
            "stop_id": stop_id,
            "name": stop.get("name"),
        }
        for stop_id, stop in stop_details.items()
        if is_trace_focus_stop(stop_id, stop_details, trace_mode)
    ]

    return {
        "mode": trace_mode,
        "stop_details": stop_details,
        "focus_stops": focus_stops,
        "events": [],
        "summary": {},
        "console_event_count": 0,
        "console_event_limit": 250,
        "console_limit_reported": False,
    }


def print_trace_line(trace, message):
    if trace["console_event_count"] < trace["console_event_limit"]:
        print(message)
        trace["console_event_count"] += 1
    elif not trace["console_limit_reported"]:
        print(
            "[RAPTOR TRACE] console event limit reached; "
            "full trace is available in debug.raptor_trace.events"
        )
        trace["console_limit_reported"] = True


def trace_event(trace, event, label=None, round_number=None, **extra):
    if not trace:
        return

    if label is not None and not should_trace_label(label, trace):
        return

    payload = {
        "round_number": round_number,
        "event": event,
        **extra,
    }

    if label is not None:
        payload.update(label_trace_summary(
            label,
            trace.get("stop_details", {})
        ))

    trace["events"].append(payload)

    stop_id = payload.get("stop_id", "-")
    arrival_time = payload.get("arrival_time", "-")
    transfer_count = payload.get("transfer_count", "-")
    mode_sequence = " -> ".join(payload.get("mode_sequence", []) or [])
    route_sequence = " -> ".join(payload.get("route_sequence", []) or [])

    print_trace_line(
        trace,
        (
            "[RAPTOR TRACE] "
            f"round={round_number} event={event} stop={stop_id} "
            f"arrival={arrival_time} transfers={transfer_count} "
            f"modes={mode_sequence} routes={route_sequence}"
        )
    )


def dominance_diagnostic(candidate_label, existing_label):
    conditions = dominance_conditions(candidate_label, existing_label)

    return {
        "candidate": label_trace_summary(candidate_label),
        "existing": label_trace_summary(existing_label),
        "conditions": conditions,
        "dominated": all(conditions.values()),
    }


def dominance_conditions(candidate_label, existing_label):
    candidate_stats = candidate_label["score"]["stats"]
    existing_stats = existing_label["score"]["stats"]
    arrival_condition = (
        existing_label["arrival_time"] <= candidate_label["arrival_time"]
    )
    cost_condition = (
        existing_label["score"]["total_cost"]
        <= candidate_label["score"]["total_cost"]
    )
    transfer_condition = (
        existing_stats["transfer_count"]
        <= candidate_stats["transfer_count"]
    )
    walking_condition = (
        existing_stats["walking_time"]
        <= candidate_stats["walking_time"]
    )
    strict_better_condition = (
        existing_label["arrival_time"] < candidate_label["arrival_time"]
        or existing_label["score"]["total_cost"]
        < candidate_label["score"]["total_cost"]
        or existing_stats["transfer_count"]
        < candidate_stats["transfer_count"]
        or existing_stats["walking_time"]
        < candidate_stats["walking_time"]
    )

    return {
        "existing_arrival_time_lte_candidate": arrival_condition,
        "existing_total_cost_lte_candidate": cost_condition,
        "existing_transfer_count_lte_candidate": transfer_condition,
        "existing_walking_time_lte_candidate": walking_condition,
        "existing_strictly_better_in_at_least_one_metric": (
            strict_better_condition
        ),
    }


def label_is_dominated(candidate_label, existing_label):
    return all(dominance_conditions(candidate_label, existing_label).values())


def add_label(
    labels_by_stop,
    label,
    max_labels_per_stop=MAX_LABELS_PER_STOP,
    trace=None,
    round_number=None,
    source=None,
    label_stats=None
):
    stop_id = label["stop_id"]
    labels = labels_by_stop.setdefault(stop_id, [])
    stats = None
    label_mode = label_mode_for_stats(label)

    if label_stats is not None:
        stats = round_stats(label_stats, round_number)
        stats["labels_created"] += 1
        increment_count(stats["labels_created_by_mode"], label_mode)

    trace_event(
        trace,
        "created",
        label,
        round_number=round_number,
        source=source,
    )

    for existing_label in labels:
        if stats is not None:
            stats["dominance_checks"] += 1

        if trace:
            diagnostic = dominance_diagnostic(label, existing_label)
            dominated = diagnostic["dominated"]
        else:
            diagnostic = None
            dominated = label_is_dominated(label, existing_label)

        if dominated:
            if stats is not None:
                stats["labels_rejected_by_dominance"] += 1

            if trace:
                trace_event(
                    trace,
                    "rejected_by_dominance",
                    label,
                    round_number=round_number,
                    source=source,
                    dominance=diagnostic,
                )
            return False

    kept_labels = []

    for existing_label in labels:
        if stats is not None:
            stats["dominance_checks"] += 1

        if trace:
            diagnostic = dominance_diagnostic(existing_label, label)
            dominated = diagnostic["dominated"]
        else:
            diagnostic = None
            dominated = label_is_dominated(existing_label, label)

        if dominated:
            if stats is not None:
                stats["existing_labels_removed_by_dominance"] += 1

            if trace:
                trace_event(
                    trace,
                    "removed_existing_by_dominance",
                    existing_label,
                    round_number=round_number,
                    source=source,
                    dominance=diagnostic,
                )
            continue

        kept_labels.append(existing_label)

    labels[:] = kept_labels

    labels.append(label)
    trim_labels_for_stop(
        labels,
        max_labels_per_stop,
        trace=trace,
        round_number=round_number,
    )

    if label in labels:
        if stats is not None:
            stats["labels_accepted"] += 1
            increment_count(stats["labels_accepted_by_mode"], label_mode)

        trace_event(
            trace,
            "accepted",
            label,
            round_number=round_number,
            source=source,
        )

    return label in labels


def trim_labels_for_stop(
    labels,
    max_labels_per_stop,
    trace=None,
    round_number=None
):
    if len(labels) <= max_labels_per_stop:
        labels.sort(
            key=lambda item: (
                item["score"]["total_cost"],
                item["arrival_time"],
            )
        )
        return

    if len(labels) > max_labels_per_stop:
        trace_event(
            trace,
            "label_cap_exceeded_but_preserved",
            labels[0] if labels else None,
            round_number=round_number,
            reason="non_dominated_labels_preserved",
            max_labels_per_stop=max_labels_per_stop,
            label_count=len(labels),
        )

    labels.sort(
        key=lambda item: (
            item["score"]["total_cost"],
            item["arrival_time"],
        )
    )
    return

    keep = []

    def add_best(key_fn):
        if not labels:
            return

        best = min(labels, key=key_fn)

        if best not in keep:
            keep.append(best)

    add_best(lambda item: (
        item["score"]["total_cost"],
        item["arrival_time"],
    ))
    add_best(lambda item: (
        item["arrival_time"],
        item["score"]["total_cost"],
    ))
    add_best(lambda item: (
        item["score"]["stats"]["transfer_count"],
        item["arrival_time"],
        item["score"]["total_cost"],
    ))
    add_best(lambda item: (
        item["score"]["stats"]["walking_time"],
        item["score"]["total_cost"],
        item["arrival_time"],
    ))

    for item in sorted(
        labels,
        key=lambda label: (
            label["score"]["total_cost"],
            label["arrival_time"],
            label["score"]["stats"]["transfer_count"],
        )
    ):
        if item not in keep:
            keep.append(item)

        if len(keep) >= max_labels_per_stop:
            break

    removed_labels = [
        label
        for label in labels
        if label not in keep[:max_labels_per_stop]
    ]
    labels[:] = keep[:max_labels_per_stop]

    for label in removed_labels:
        trace_event(
            trace,
            "trimmed",
            label,
            round_number=round_number,
            reason="max_labels_per_stop",
            max_labels_per_stop=max_labels_per_stop,
        )

    labels.sort(
        key=lambda item: (
            item["score"]["total_cost"],
            item["arrival_time"],
        )
    )


def select_boarding_labels_for_route(
    labels,
    route_stop_index,
    trace=None,
    round_number=None,
    route_id=None,
    route_label=None,
    route_mode=None
):
    best_by_stop = {}

    for label in labels:
        stop_id = label["stop_id"]

        if stop_id not in route_stop_index:
            continue

        existing_label = best_by_stop.get(stop_id)

        if existing_label is None:
            best_by_stop[stop_id] = label
            continue

        if (
            label["score"]["total_cost"],
            label["arrival_time"],
        ) < (
            existing_label["score"]["total_cost"],
            existing_label["arrival_time"],
        ):
            best_by_stop[stop_id] = label

    boarding_labels = list(best_by_stop.values())
    boarding_labels.sort(
        key=lambda label: (
            label["score"]["total_cost"],
            label["arrival_time"],
            route_stop_index[label["stop_id"]],
        )
    )

    selected_labels = boarding_labels[:MAX_BOARDING_LABELS_PER_ROUTE]

    for label in selected_labels:
        trace_event(
            trace,
            "boarding_candidate",
            label,
            round_number=round_number,
            route_id=route_id,
            route_label=route_label,
            route_mode=route_mode,
            route_stop_index=route_stop_index.get(label["stop_id"]),
        )

    for label in boarding_labels[MAX_BOARDING_LABELS_PER_ROUTE:]:
        trace_event(
            trace,
            "boarding_candidate_not_selected",
            label,
            round_number=round_number,
            route_id=route_id,
            route_label=route_label,
            route_mode=route_mode,
            reason="max_boarding_labels_per_route",
            max_boarding_labels_per_route=MAX_BOARDING_LABELS_PER_ROUTE,
        )

    return selected_labels


def apply_walking_transfers_to_labels(
    labels,
    labels_by_stop,
    walking_transfers,
    departure_time_seconds,
    round_number,
    trace=None,
    label_stats=None
):
    new_labels = []

    for label in labels:
        from_stop_id = label["stop_id"]

        for edge in walking_transfers.get(from_stop_id, []):
            to_stop_id = str(edge["to"])
            walking_time = int(edge["walking_time"])
            arrival_time = label["arrival_time"] + walking_time
            leg = {
                "from_stop_id": from_stop_id,
                "to_stop_id": to_stop_id,
                "route_id": None,
                "trip_id": None,
                "mode": "walk",
                "departure_time": label["arrival_time"],
                "arrival_time": arrival_time,
                "waiting_time": 0,
                "distance_meters": edge.get("distance_meters"),
                "walking_time": walking_time,
                "walk_type": edge.get("walk_type"),
                "source": edge.get("source"),
                "confidence": edge.get("confidence"),
                "route_label": None,
                "round": round_number
            }
            new_label = make_label(
                to_stop_id,
                arrival_time,
                label["path"] + [leg],
                departure_time_seconds
            )

            if add_label(
                labels_by_stop,
                new_label,
                trace=trace,
                round_number=round_number,
                source="walking_transfer",
                label_stats=label_stats,
            ):
                new_labels.append(new_label)

    return new_labels


def route_signature(path):
    return tuple(
        (
            leg.get("mode"),
            leg.get("route_id"),
            canonical_stop_id_for_signature(leg.get("from_stop_id")),
            canonical_stop_id_for_signature(leg.get("to_stop_id")),
        )
        for leg in path
    )


def transit_legs(path):
    return [
        leg
        for leg in path
        if normalize_route_mode(leg.get("mode")) != "walk"
    ]


def has_same_route_direction_backtracking(path):
    for previous_leg, current_leg in zip(transit_legs(path), transit_legs(path)[1:]):
        previous_mode = normalize_route_mode(previous_leg.get("mode"))
        current_mode = normalize_route_mode(current_leg.get("mode"))

        if previous_mode != current_mode:
            continue

        if previous_mode not in TRUNK_BACKTRACK_GUARD_MODES:
            continue

        if previous_leg.get("route_id") != current_leg.get("route_id"):
            continue

        if previous_leg.get("to_stop_id") != current_leg.get("from_stop_id"):
            continue

        previous_direction = previous_leg.get("direction_id")
        current_direction = current_leg.get("direction_id")
        direction_changed = (
            previous_direction is not None
            and current_direction is not None
            and previous_direction != current_direction
        )
        trip_changed = (
            previous_leg.get("trip_id") is not None
            and current_leg.get("trip_id") is not None
            and previous_leg.get("trip_id") != current_leg.get("trip_id")
        )

        if direction_changed or trip_changed:
            return True

    return False


def route_diagnostic_summary(route):
    legs = route.get("legs", [])
    stats = route.get("score", {}).get("stats") or calculate_path_stats(legs)
    quality = route_quality_metrics(route)

    return {
        "transfer_count": stats["transfer_count"],
        "total_travel_time": route.get("total_travel_time"),
        "total_walking_time": stats["walking_time"],
        "waiting_time": stats["waiting_time"],
        "generalized_cost": route.get("generalized_cost"),
        "route_sequence": [
            leg.get("route_label") or leg.get("route_id") or "walk"
            for leg in legs
        ],
        "modes_sequence": [
            leg.get("mode")
            for leg in legs
        ],
        "signature": route_signature(legs),
        "same_route_backtracking": has_same_route_direction_backtracking(legs),
        **quality,
        "rejected_by_quality_filter": route.get("rejected_by_quality_filter"),
    }


def transit_modes_for_route(route):
    return [
        normalize_route_mode(leg.get("mode"))
        for leg in route.get("legs", [])
        if normalize_route_mode(leg.get("mode")) != "walk"
    ]


def route_uses_brt_feeder_transfer(route):
    return any(
        leg.get("walk_type") == "brt_feeder_transfer"
        or leg.get("source") == "generated_brt_feeder"
        for leg in route.get("legs", [])
    )


def max_consecutive_surface_transit_legs(route):
    longest = 0
    current = 0

    for mode in transit_modes_for_route(route):
        if mode in SURFACE_MODES:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return longest


def surface_chain_count(route):
    longest = max_consecutive_surface_transit_legs(route)
    return max(0, longest - 1)


def has_brt_after_feeder_transfer(route):
    feeder_seen = False

    for leg in route.get("legs", []):
        mode = normalize_route_mode(leg.get("mode"))
        if (
            leg.get("walk_type") == "brt_feeder_transfer"
            or leg.get("source") == "generated_brt_feeder"
        ):
            feeder_seen = True
            continue

        if feeder_seen and mode == "brt":
            return True

    return False


def route_quality_metrics(route):
    modes = transit_modes_for_route(route)
    has_trunk = any(mode in TRUNK_MODES for mode in modes)
    has_brt = "brt" in modes
    used_brt_feeder = route_uses_brt_feeder_transfer(route)

    return {
        "has_trunk_mode": has_trunk,
        "has_brt": has_brt,
        "used_brt_feeder_transfer": used_brt_feeder,
        "surface_chain_count": surface_chain_count(route),
    }


def route_quality_rejection_reason(route):
    stats = route.get("score", {}).get("stats") or calculate_path_stats(
        route.get("legs", [])
    )
    quality = route_quality_metrics(route)

    if (
        quality["used_brt_feeder_transfer"]
        and not quality["has_brt"]
        and not has_brt_after_feeder_transfer(route)
    ):
        return "used_brt_feeder_transfer_without_boarding_brt"

    if (
        not quality["has_trunk_mode"]
        and stats["transfer_count"] > MAX_NON_TRUNK_TRANSFERS
    ):
        return "non_trunk_route_exceeds_transfer_cap"

    if not quality["has_trunk_mode"] and quality["surface_chain_count"] >= 2:
        return "surface_only_chain_without_trunk"

    return None


def route_quality_penalty(route):
    quality = route_quality_metrics(route)
    stats = route.get("score", {}).get("stats") or calculate_path_stats(
        route.get("legs", [])
    )
    penalty = 0

    if quality["surface_chain_count"]:
        penalty += quality["surface_chain_count"] * 900

    if not quality["has_trunk_mode"] and quality["surface_chain_count"]:
        penalty += 1800

    if not quality["has_trunk_mode"] and stats["transfer_count"] > 1:
        penalty += stats["transfer_count"] * 700

    if quality["used_brt_feeder_transfer"] and not quality["has_brt"]:
        penalty += 5000

    return penalty


def infer_metro_trace_reason(
    trace,
    metro_only_candidates,
    destination_candidates,
    stop_details
):
    if metro_only_candidates:
        return "metro_only_candidate_reached_destination"

    events = trace.get("events", [])
    metro_accepted = [
        event
        for event in events
        if event.get("event") == "accepted"
        and "metro" in (event.get("mode_sequence") or [])
    ]
    metro_rejected = [
        event
        for event in events
        if event.get("event") in (
            "rejected_by_dominance",
            "trimmed",
            "boarding_candidate_not_selected",
        )
        and "metro" in (event.get("mode_sequence") or [])
    ]
    destination_metro_candidates = [
        candidate
        for candidate in destination_candidates
        if is_trace_focus_stop(candidate["stop_id"], stop_details)
    ]

    if metro_rejected:
        last_event = metro_rejected[-1]
        return (
            "metro_label_discarded_by_"
            f"{last_event.get('event')}"
        )

    if metro_accepted and not destination_metro_candidates:
        return "destination_metro_stop_not_present_in_egress_candidates"

    if metro_accepted:
        return (
            "metro_labels_exist_but_no_metro_only_label_reached_a_destination"
        )

    return "no_metro_label_generated_or_boarded"


def build_candidate_result(
    origin_stop_id,
    destination_stop_id,
    departure_time_seconds,
    arrival_time,
    path,
    score
):
    fare = calculate_path_fare(path or [])

    return {
        "found": True,
        "origin_stop_id": origin_stop_id,
        "destination_stop_id": str(destination_stop_id),
        "departure_time": departure_time_seconds,
        "arrival_time": arrival_time,
        "total_travel_time": arrival_time - departure_time_seconds,
        "generalized_cost": score["total_cost"],
        "total_fare": fare["total_fare"],
        "fare_currency": fare["currency"],
        "fare_breakdown": fare["leg_fares"],
        "score": score,
        "legs": path or []
    }


def is_walk_only_route(route):
    legs = route.get("legs", [])

    return (
        len(legs) == 1
        and legs[0].get("mode") == "walk"
        and legs[0].get("from_stop_id") == "origin"
        and legs[0].get("to_stop_id") == "destination"
    )


def classify_route_type(route):
    if is_walk_only_route(route):
        return "walk_only"

    return "transit"


def infer_origin_stop_id(path, fallback_stop_id=None):
    if not path:
        return fallback_stop_id

    first_leg = path[0]

    if first_leg.get("from_stop_id") == "origin":
        return first_leg.get("to_stop_id", fallback_stop_id)

    return first_leg.get("from_stop_id", fallback_stop_id)


def select_route_alternatives(candidates, limit=4):
    unique_candidates = {}

    for candidate in candidates:
        signature = route_signature(candidate["legs"])

        if signature not in unique_candidates:
            unique_candidates[signature] = candidate
            continue

        if candidate["generalized_cost"] < unique_candidates[signature]["generalized_cost"]:
            unique_candidates[signature] = candidate

    candidates = list(unique_candidates.values())

    if not candidates:
        return []

    for candidate in candidates:
        candidate["route_type"] = classify_route_type(candidate)
        candidate["quality"] = route_quality_metrics(candidate)
        candidate["quality_penalty"] = route_quality_penalty(candidate)
        candidate["selection_cost"] = (
            candidate["generalized_cost"] + candidate["quality_penalty"]
        )

    walk_only_routes = [
        route
        for route in candidates
        if route["route_type"] == "walk_only"
    ]
    transit_routes = [
        route
        for route in candidates
        if route["route_type"] != "walk_only"
    ]
    recommended_baseline = min(
        transit_routes,
        key=lambda route: (
            route["selection_cost"],
            route["total_travel_time"],
        ),
        default=None,
    )
    recommended_time = (
        recommended_baseline["total_travel_time"]
        if recommended_baseline is not None
        else None
    )

    def transfer_count(route):
        stats = route.get("score", {}).get("stats")

        if stats is not None:
            return stats["transfer_count"]

        return calculate_path_stats(route["legs"])["transfer_count"]

    def passes_least_walking_guard(route):
        quality = route.get("quality") or route_quality_metrics(route)

        if (
            not quality["has_trunk_mode"]
            and transfer_count(route) > MAX_NON_TRUNK_TRANSFERS
        ):
            return False

        if not quality["has_trunk_mode"] and quality["surface_chain_count"] >= 2:
            return False

        if (
            recommended_time
            and route["total_travel_time"]
            > recommended_time * LEAST_WALKING_MAX_RECOMMENDED_RATIO
        ):
            return False

        return True

    least_walking_routes = [
        route
        for route in candidates
        if passes_least_walking_guard(route)
    ]
    brt_lrt_routes = [
        route
        for route in transit_routes
        if route.get("quality", {}).get("has_brt")
        and any(leg.get("mode") == "lrt" for leg in route.get("legs", []))
    ]

    profiles = [
        (
            "Recommended route",
            "recommended",
            transit_routes,
            lambda route: (
                route["selection_cost"],
                route["total_travel_time"],
            )
        ),
        (
            "Fastest transit",
            "fastest transit",
            transit_routes,
            lambda route: (
                route["total_travel_time"],
                route["generalized_cost"],
            )
        ),
        (
            "Fewest transfers",
            "fewest transfers",
            transit_routes,
            lambda route: (
                transfer_count(route),
                route["score"]["breakdown"].get("mode_switch_penalty", 0),
                route["total_travel_time"],
                route["selection_cost"],
            )
        ),
        (
            "BRT + LRT connection",
            "brt + lrt",
            brt_lrt_routes,
            lambda route: (
                route["selection_cost"],
                route["total_travel_time"],
            )
        ),
        (
            "Least walking",
            "least walking",
            least_walking_routes,
            lambda route: (
                route["score"]["stats"]["walking_time"],
                route["selection_cost"],
                route["total_travel_time"],
            )
        ),
    ]

    selected = []
    selected_by_signature = {}
    selected_signatures = set()

    for label, badge, route_pool, key_fn in profiles:
        if not route_pool:
            continue

        best_candidate = sorted(route_pool, key=key_fn)[0]
        signature = route_signature(best_candidate["legs"])

        if signature in selected_signatures:
            existing = selected_by_signature[signature]

            if badge not in existing["badges"]:
                existing["badges"].append(badge)

            continue

        alternative = dict(best_candidate)
        alternative["alternative_label"] = label
        alternative["badges"] = [badge]
        selected.append(alternative)
        selected_by_signature[signature] = alternative
        selected_signatures.add(signature)

        if len(selected) >= limit:
            break

    if walk_only_routes:
        walk_only_route = min(
            walk_only_routes,
            key=lambda route: (
                route["total_travel_time"],
                route["generalized_cost"],
            )
        )
        signature = route_signature(walk_only_route["legs"])

        if signature in selected_by_signature:
            existing = selected_by_signature[signature]

            if "walk only" not in existing["badges"]:
                existing["badges"].append("walk only")

            return selected

        alternative = dict(walk_only_route)
        alternative["alternative_label"] = "Walk only"
        alternative["badges"] = ["walk only"]
        selected.append(alternative)

    return selected


def simple_raptor(
    indexes,
    departure_time_seconds,
    max_transfers=2,
    walking_transfers=None,
    origin_candidates=None,
    destination_candidates=None,
    final_origin=None,
    final_destination=None,
    origin_stop_id=None,
    destination_stop_id=None,
    eta_estimates=None,
    trace_mode=None,
    collect_diagnostics=True
):
    diagnostics = {
        "stage_timings_seconds": {},
        "round_cap_analysis": {
            "rounds": [],
        },
        "label_stats": {
            "rounds": {},
        },
    }
    stage_start = time.perf_counter()
    routes_by_stop = indexes["routes_by_stop"]
    stops_by_route = indexes["stops_by_route"]
    trips_by_route = indexes["trips_by_route"]
    stop_times_by_trip = indexes["stop_times_by_trip"]
    trip_stop_index = indexes["trip_stop_index"]
    stop_index_by_route = indexes["stop_index_by_route"]
    route_modes = indexes.get("route_modes", {})
    route_labels = indexes.get("route_labels", {})
    stop_details = indexes.get("stop_details", {})
    trace = create_trace_context(trace_mode, stop_details)
    label_stats = diagnostics["label_stats"] if collect_diagnostics else None
    if walking_transfers is None:
        walking_transfers = {}
    if eta_estimates is None:
        eta_estimates = {}
    diagnostics["stage_timings_seconds"]["setup"] = round(
        time.perf_counter() - stage_start,
        4
    )

    stage_start = time.perf_counter()
    rounds = max_transfers + 1
    labels_by_stop = {}

    if origin_candidates is None:
        if origin_stop_id is None:
            raise ValueError("origin_stop_id is required when origin_candidates is not provided")

        origin_candidates = [{
            "stop_id": origin_stop_id,
            "walking_time": 0,
            "distance_meters": 0,
            "stop": None
        }]

    if destination_candidates is None:
        if destination_stop_id is None:
            raise ValueError("destination_stop_id is required when destination_candidates is not provided")

        destination_candidates = [{
            "stop_id": destination_stop_id,
            "walking_time": 0,
            "distance_meters": 0,
            "stop": None
        }]

    marked_labels = []

    for candidate in origin_candidates:
        stop_id = str(candidate["stop_id"])
        walking_time = int(candidate.get("walking_time", 0))
        arrival_time = departure_time_seconds + walking_time

        if walking_time > 0 and final_origin is not None:
            initial_path = [{
                "from_stop_id": "origin",
                "to_stop_id": stop_id,
                "from_stop": {
                    "stop_id": "origin",
                    "name": "Origin",
                    "lat": final_origin["lat"],
                    "lon": final_origin["lon"]
                },
                "to_stop": candidate.get("stop"),
                "route_id": None,
                "trip_id": None,
                "mode": "walk",
                "departure_time": departure_time_seconds,
                "arrival_time": arrival_time,
                "waiting_time": 0,
                "distance_meters": candidate.get("distance_meters"),
                "walking_time": walking_time,
                "route_label": None,
                "round": 0
            }]
        else:
            initial_path = []

        label = make_label(
            stop_id,
            arrival_time,
            initial_path,
            departure_time_seconds
        )

        if add_label(
            labels_by_stop,
            label,
            trace=trace,
            round_number=0,
            source="origin_access",
            label_stats=label_stats,
        ):
            marked_labels.append(label)

    marked_labels.extend(apply_walking_transfers_to_labels(
        labels=marked_labels,
        labels_by_stop=labels_by_stop,
        walking_transfers=walking_transfers,
        departure_time_seconds=departure_time_seconds,
        round_number=0,
        trace=trace,
        label_stats=label_stats,
    ))
    diagnostics["stage_timings_seconds"]["initial_access_labels"] = round(
        time.perf_counter() - stage_start,
        4
    )

    stage_start = time.perf_counter()
    for round_number in range(rounds):
        if not marked_labels:
            break

        new_marked_labels = []
        routes_to_scan = set()
        round_marked_labels = list(marked_labels)

        # Find routes serving currently reachable stops.
        for label in round_marked_labels:
            for route_id in routes_by_stop.get(label["stop_id"], []):
                routes_to_scan.add(route_id)

        sorted_routes_to_scan = sorted(
            routes_to_scan,
            key=lambda route_id: route_scan_sort_key(
                route_id,
                route_modes,
                route_labels,
            )
        )
        round_cap_reached = False
        round_analysis = {
            "round_number": round_number,
            "total_candidate_routes": len(sorted_routes_to_scan),
            "total_routes_scanned": 0,
            "routes_skipped_due_cap": 0,
            "metro_routes_scanned": 0,
            "metro_routes_skipped": 0,
            "labels_generated_by_mode": {},
            "routes_scanned_by_mode": {},
            "routes_skipped_by_mode": {},
            "route_scan_order": [],
            "cap_reached": False,
            "cap_route": None,
            "max_new_labels_per_round": MAX_NEW_LABELS_PER_ROUND,
        } if collect_diagnostics else None

        # Scan each route.
        for route_index, route_id in enumerate(sorted_routes_to_scan):
            route_stop_index = stop_index_by_route.get(route_id, {})
            route_label = route_labels.get(route_id, route_id)
            route_mode = normalize_route_mode(route_modes.get(route_id, "unknown"))
            route_priority = route_scan_priority(route_id, route_modes)
            route_generated_labels = 0
            if round_analysis is not None:
                round_analysis["total_routes_scanned"] += 1
                increment_count(round_analysis["routes_scanned_by_mode"], route_mode)

            if round_analysis is not None and route_mode == "metro":
                round_analysis["metro_routes_scanned"] += 1

            if round_analysis is not None:
                round_analysis["route_scan_order"].append({
                    "scan_order": route_index + 1,
                    "route_id": route_id,
                    "route_label": route_label,
                    "route_mode": route_mode,
                    "scan_priority": route_priority,
                })

            reachable_boarding_labels = select_boarding_labels_for_route(
                round_marked_labels,
                route_stop_index,
                trace=trace,
                round_number=round_number,
                route_id=route_id,
                route_label=route_label,
                route_mode=route_mode,
            )

            if trace and (
                route_mode == trace.get("mode")
                or (
                    trace.get("mode") == "metro"
                    and route_label in ("M1", "M2", "M3")
                )
            ):
                trace["events"].append({
                    "round_number": round_number,
                    "event": "route_scanned",
                    "route_id": route_id,
                    "route_label": route_label,
                    "route_mode": route_mode,
                    "scan_priority": route_priority,
                    "scan_order": route_index + 1,
                    "boarding_label_count": len(reachable_boarding_labels),
                })
                print_trace_line(
                    trace,
                    (
                        "[RAPTOR TRACE] "
                        f"round={round_number} event=route_scanned "
                        f"order={route_index + 1} priority={route_priority} "
                        f"route={route_label} mode={route_mode} "
                        f"boarding_labels={len(reachable_boarding_labels)}"
                    )
                )

            # Find reachable boarding stops on this route.
            for boarding_label in reachable_boarding_labels:
                boarding_stop_id = boarding_label["stop_id"]
                earliest_board_time = boarding_label["arrival_time"]

                trip_options = find_earliest_trips_on_route_by_direction(
                    route_id=route_id,
                    trips_by_route=trips_by_route,
                    stop_times_by_trip=stop_times_by_trip,
                    trip_stop_index=trip_stop_index,
                    boarding_stop_id=boarding_stop_id,
                    earliest_board_time=earliest_board_time
                )

                if not trip_options:
                    continue

                for trip_id, trip_times, departure_time, board_index in trip_options:
                    adjusted_time_at_previous_stop = departure_time
                    eta_segments = []
                    previous_stop = trip_times[board_index]

                    for st in trip_times[board_index + 1:]:
                        stop_id = st["stop_id"]
                        segment_travel_time, eta_segment = resolve_segment_travel_time(
                            eta_estimates=eta_estimates,
                            route_id=route_id,
                            direction_id=previous_stop.get("direction_id"),
                            from_stop=previous_stop,
                            to_stop=st
                        )
                        if eta_segment["source"] == "eta_engine":
                            eta_segments = eta_segments + [eta_segment]
                        arrival_time = adjusted_time_at_previous_stop + segment_travel_time

                        leg = {
                            "from_stop_id": boarding_stop_id,
                            "to_stop_id": stop_id,
                            "route_id": route_id,
                            "trip_id": trip_id,
                            "mode": route_modes.get(route_id, "unknown"),
                            "route_label": route_labels.get(route_id, route_id),
                            "departure_time": departure_time,
                            "arrival_time": arrival_time,
                            "waiting_time": departure_time - earliest_board_time,
                            "eta_adjusted": bool(eta_segments),
                            "eta_segments": eta_segments,
                            "round": round_number,
                            "direction_id": previous_stop.get("direction_id"),
                        }
                        new_label = make_label(
                            stop_id,
                            arrival_time,
                            boarding_label["path"] + [leg],
                            departure_time_seconds
                        )

                        if add_label(
                            labels_by_stop,
                            new_label,
                            trace=trace,
                            round_number=round_number,
                            source="route_scan",
                            label_stats=label_stats,
                        ):
                            new_marked_labels.append(new_label)
                            route_generated_labels += 1
                            if round_analysis is not None:
                                increment_count(
                                    round_analysis["labels_generated_by_mode"],
                                    route_mode,
                                )

                            if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                                round_cap_reached = True
                                break

                        dwell_time = max(
                            0,
                            int(st["departure_time"]) - int(st["arrival_time"])
                        )
                        adjusted_time_at_previous_stop = arrival_time + dwell_time
                        previous_stop = st

                    if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                        round_cap_reached = True
                        break

                if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                    round_cap_reached = True
                    break

            if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                round_cap_reached = True
                if round_analysis is not None and route_generated_labels:
                    route_order_entry = round_analysis["route_scan_order"][-1]
                    route_order_entry["generated_labels"] = route_generated_labels

                skipped_routes = sorted_routes_to_scan[route_index + 1:]
                if round_analysis is not None:
                    round_analysis["cap_reached"] = True
                    round_analysis["cap_route"] = {
                        "route_id": route_id,
                        "route_label": route_label,
                        "route_mode": route_mode,
                        "scan_order": route_index + 1,
                        "scan_priority": route_priority,
                        "new_label_count": len(new_marked_labels),
                    }
                    round_analysis["routes_skipped_due_cap"] = len(skipped_routes)

                    for skipped_route_id in skipped_routes:
                        skipped_route_mode = normalize_route_mode(
                            route_modes.get(skipped_route_id, "unknown")
                        )
                        increment_count(
                            round_analysis["routes_skipped_by_mode"],
                            skipped_route_mode,
                        )

                        if skipped_route_mode == "metro":
                            round_analysis["metro_routes_skipped"] += 1

                if trace:
                    trace["events"].append({
                        "round_number": round_number,
                        "event": "round_cap_reached",
                        "route_id": route_id,
                        "route_label": route_label,
                        "route_mode": route_mode,
                        "scan_priority": route_priority,
                        "scan_order": route_index + 1,
                        "new_label_count": len(new_marked_labels),
                        "max_new_labels_per_round": MAX_NEW_LABELS_PER_ROUND,
                    })

                    for skipped_route_id in skipped_routes:
                        skipped_scan_order = (
                            sorted_routes_to_scan.index(skipped_route_id) + 1
                        )
                        skipped_route_label = route_labels.get(
                            skipped_route_id,
                            skipped_route_id,
                        )
                        skipped_route_mode = normalize_route_mode(
                            route_modes.get(skipped_route_id, "unknown")
                        )
                        skipped_route_priority = route_scan_priority(
                            skipped_route_id,
                            route_modes,
                        )

                        if (
                            skipped_route_mode == trace.get("mode")
                            or (
                                trace.get("mode") == "metro"
                                and skipped_route_label in ("M1", "M2", "M3")
                            )
                        ):
                            trace["events"].append({
                                "round_number": round_number,
                                "event": "route_skipped_due_round_cap",
                                "route_id": skipped_route_id,
                                "route_label": skipped_route_label,
                                "route_mode": skipped_route_mode,
                                "scan_priority": skipped_route_priority,
                                "scan_order": skipped_scan_order,
                                "new_label_count": len(new_marked_labels),
                                "max_new_labels_per_round": MAX_NEW_LABELS_PER_ROUND,
                            })
                break

            if round_analysis is not None and route_generated_labels:
                route_order_entry = round_analysis["route_scan_order"][-1]
                route_order_entry["generated_labels"] = route_generated_labels

        if round_analysis is not None:
            diagnostics["round_cap_analysis"]["rounds"].append(round_analysis)

        new_marked_labels.extend(apply_walking_transfers_to_labels(
            labels=new_marked_labels,
            labels_by_stop=labels_by_stop,
            walking_transfers=walking_transfers,
            departure_time_seconds=departure_time_seconds,
            round_number=round_number,
            trace=trace,
            label_stats=label_stats,
        ))
        marked_labels = new_marked_labels
        if label_stats is not None:
            surviving_labels = sum(
                len(stop_labels)
                for stop_labels in labels_by_stop.values()
            )
            round_stats(
                label_stats,
                round_number,
            )["labels_surviving"] = surviving_labels
    round_cap_rounds = diagnostics["round_cap_analysis"]["rounds"]
    round_cap_summary = {
        "total_routes_scanned": 0,
        "routes_skipped_due_cap": 0,
        "metro_routes_scanned": 0,
        "metro_routes_skipped": 0,
        "labels_generated_by_mode": {},
        "routes_scanned_by_mode": {},
        "routes_skipped_by_mode": {},
    }

    for round_analysis in round_cap_rounds:
        round_cap_summary["total_routes_scanned"] += round_analysis[
            "total_routes_scanned"
        ]
        round_cap_summary["routes_skipped_due_cap"] += round_analysis[
            "routes_skipped_due_cap"
        ]
        round_cap_summary["metro_routes_scanned"] += round_analysis[
            "metro_routes_scanned"
        ]
        round_cap_summary["metro_routes_skipped"] += round_analysis[
            "metro_routes_skipped"
        ]

        for mode, count in round_analysis["labels_generated_by_mode"].items():
            increment_count(
                round_cap_summary["labels_generated_by_mode"],
                mode,
                count,
            )

        for mode, count in round_analysis["routes_scanned_by_mode"].items():
            increment_count(
                round_cap_summary["routes_scanned_by_mode"],
                mode,
                count,
            )

        for mode, count in round_analysis["routes_skipped_by_mode"].items():
            increment_count(
                round_cap_summary["routes_skipped_by_mode"],
                mode,
                count,
            )

    diagnostics["round_cap_analysis"]["summary"] = round_cap_summary
    label_rounds = sorted(
        diagnostics["label_stats"]["rounds"].values(),
        key=lambda item: (
            item["round_number"] is None,
            item["round_number"] if item["round_number"] is not None else -1,
        )
    )
    diagnostics["label_stats"]["rounds"] = label_rounds
    diagnostics["label_stats"]["summary"] = {
        "labels_created": sum(
            item["labels_created"]
            for item in label_rounds
        ),
        "labels_accepted": sum(
            item["labels_accepted"]
            for item in label_rounds
        ),
        "labels_rejected_by_dominance": sum(
            item["labels_rejected_by_dominance"]
            for item in label_rounds
        ),
        "existing_labels_removed_by_dominance": sum(
            item["existing_labels_removed_by_dominance"]
            for item in label_rounds
        ),
        "dominance_checks": sum(
            item["dominance_checks"]
            for item in label_rounds
        ),
    }
    diagnostics["stage_timings_seconds"]["raptor_rounds"] = round(
        time.perf_counter() - stage_start,
        4
    )

    stage_start = time.perf_counter()
    candidate_results = []

    if final_origin is not None and final_destination is not None:
        direct_distance = haversine_meters(
            final_origin["lat"],
            final_origin["lon"],
            final_destination["lat"],
            final_destination["lon"]
        )

        if direct_distance <= MAX_DIRECT_WALK_METERS:
            direct_walking_time = int(direct_distance / WALKING_SPEED_MPS)
            direct_path = [{
                "from_stop_id": "origin",
                "to_stop_id": "destination",
                "from_stop": {
                    "stop_id": "origin",
                    "name": "Origin",
                    "lat": final_origin["lat"],
                    "lon": final_origin["lon"]
                },
                "to_stop": {
                    "stop_id": "destination",
                    "name": "Destination",
                    "lat": final_destination["lat"],
                    "lon": final_destination["lon"]
                },
                "route_id": None,
                "trip_id": None,
                "mode": "walk",
                "departure_time": departure_time_seconds,
                "arrival_time": departure_time_seconds + direct_walking_time,
                "waiting_time": 0,
                "distance_meters": round(direct_distance, 2),
                "walking_time": direct_walking_time,
                "route_label": None,
                "round": None
            }]
            direct_score = score_path(
                direct_path,
                direct_walking_time,
                final_walking_time=direct_walking_time
            )

            candidate_results.append(build_candidate_result(
                origin_stop_id=infer_origin_stop_id(direct_path, origin_stop_id),
                destination_stop_id="destination",
                departure_time_seconds=departure_time_seconds,
                arrival_time=departure_time_seconds + direct_walking_time,
                path=direct_path,
                score=direct_score
            ))

    for candidate in destination_candidates:
        stop_id = str(candidate["stop_id"])

        if stop_id not in labels_by_stop:
            continue

        egress_walking_time = int(candidate.get("walking_time", 0))

        for destination_label in labels_by_stop[stop_id]:
            final_arrival_time = destination_label["arrival_time"] + egress_walking_time
            candidate_path = list(destination_label["path"])

            if egress_walking_time > 0 and final_destination is not None:
                candidate_path.append({
                    "from_stop_id": stop_id,
                    "to_stop_id": "destination",
                    "from_stop": candidate.get("stop"),
                    "to_stop": {
                        "stop_id": "destination",
                        "name": "Destination",
                        "lat": final_destination["lat"],
                        "lon": final_destination["lon"]
                    },
                    "route_id": None,
                    "trip_id": None,
                    "mode": "walk",
                    "departure_time": destination_label["arrival_time"],
                    "arrival_time": final_arrival_time,
                    "waiting_time": 0,
                    "distance_meters": candidate.get("distance_meters"),
                    "walking_time": egress_walking_time,
                    "route_label": None,
                    "round": None
                })

            total_travel_time = final_arrival_time - departure_time_seconds
            candidate_path = simplify_legs(candidate_path)
            score = score_path(
                candidate_path,
                total_travel_time,
                final_walking_time=egress_walking_time
            )
            generalized_cost = score["total_cost"]

            candidate_results.append(build_candidate_result(
                origin_stop_id=infer_origin_stop_id(candidate_path, origin_stop_id),
                destination_stop_id=candidate["stop_id"],
                departure_time_seconds=departure_time_seconds,
                arrival_time=final_arrival_time,
                path=candidate_path,
                score=score
            ))
    diagnostics["stage_timings_seconds"]["candidate_reconstruction"] = round(
        time.perf_counter() - stage_start,
        4
    )
    diagnostics["candidate_count"] = len(candidate_results)
    diagnostics["candidates"] = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
    ]
    brt_candidates_before_quality_filter = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "brt" for leg in candidate.get("legs", []))
    ]
    rejected_backtracking_candidates = [
        candidate
        for candidate in candidate_results
        if has_same_route_direction_backtracking(candidate.get("legs", []))
    ]
    candidate_results = [
        candidate
        for candidate in candidate_results
        if not has_same_route_direction_backtracking(candidate.get("legs", []))
    ]
    quality_rejected_candidates = []
    quality_kept_candidates = []

    for candidate in candidate_results:
        rejection_reason = route_quality_rejection_reason(candidate)
        candidate["quality"] = route_quality_metrics(candidate)
        candidate["quality_penalty"] = route_quality_penalty(candidate)

        if rejection_reason:
            rejected_candidate = dict(candidate)
            rejected_candidate["rejected_by_quality_filter"] = rejection_reason
            quality_rejected_candidates.append(rejected_candidate)
            continue

        candidate["rejected_by_quality_filter"] = None
        quality_kept_candidates.append(candidate)

    quality_filter_fallback_used = False
    if quality_kept_candidates:
        candidate_results = quality_kept_candidates
    elif quality_rejected_candidates:
        quality_filter_fallback_used = True
        candidate_results = [
            {
                **candidate,
                "rejected_by_quality_filter": None,
                "quality_filter_fallback": True,
            }
            for candidate in quality_rejected_candidates
        ]

    diagnostics["quality_guard"] = {
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
        "same_route_backtracking_rejected_routes": [
            route_diagnostic_summary(candidate)
            for candidate in rejected_backtracking_candidates
        ],
        "route_quality_rejected": len(quality_rejected_candidates),
        "route_quality_rejected_routes": [
            route_diagnostic_summary(candidate)
            for candidate in quality_rejected_candidates
        ],
        "quality_filter_fallback_used": quality_filter_fallback_used,
        "brt_alternatives_before_quality_filter": len(
            brt_candidates_before_quality_filter
        ),
        "brt_alternatives_after_quality_filter": sum(
            1
            for candidate in candidate_results
            if any(leg.get("mode") == "brt" for leg in candidate.get("legs", []))
        ),
        "candidate_count_after_quality_guard": len(candidate_results),
    }

    stage_start = time.perf_counter()
    alternatives = select_route_alternatives(candidate_results)
    diagnostics["stage_timings_seconds"]["alternative_generation"] = round(
        time.perf_counter() - stage_start,
        4
    )
    diagnostics["selected_alternatives"] = [
        {
            **route_diagnostic_summary(alternative),
            "alternative_label": alternative.get("alternative_label"),
            "badges": alternative.get("badges", []),
        }
        for alternative in alternatives
    ]
    brt_candidate_summaries = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "brt" for leg in candidate.get("legs", []))
    ]
    diagnostics["metro_only_candidates"] = [
        summary
        for summary in diagnostics["candidates"]
        if any(mode == "metro" for mode in summary["modes_sequence"])
        and all(
            mode in ("walk", "metro")
            for mode in summary["modes_sequence"]
        )
    ]
    brt_destination_stop_ids = {
        str(candidate["stop_id"])
        for candidate in destination_candidates
    }
    brt_labels_at_destination = [
        label
        for stop_id, labels in labels_by_stop.items()
        if str(stop_id) in brt_destination_stop_ids
        for label in labels
        if "brt" in label_transit_modes(label)
    ]
    brt_feeder_labels = [
        label
        for labels in labels_by_stop.values()
        for label in labels
        if str(label.get("stop_id", "")).startswith("BRT_")
        and any(
            leg.get("walk_type") == "brt_feeder_transfer"
            for leg in label.get("path", [])
        )
    ]
    brt_rounds = [
        round_item
        for round_item in diagnostics.get("label_stats", {}).get("rounds", [])
    ]
    diagnostics["brt_debug"] = {
        "brt_phase1_exists_in_route_modes": route_modes.get("BRT_PHASE1") == "brt",
        "brt_stop_count": sum(
            1
            for stop_id in stop_details
            if str(stop_id).startswith("BRT_")
        ),
        "brt_khosous_routes": routes_by_stop.get("BRT_KHOSOUS", []),
        "brt_marg_routes": routes_by_stop.get("BRT_MARG", []),
        "brt_phase1_scan_count": sum(
            1
            for round_analysis in diagnostics["round_cap_analysis"]["rounds"]
            for route_entry in round_analysis.get("route_scan_order", [])
            if route_entry.get("route_id") == "BRT_PHASE1"
        ),
        "brt_labels_created": sum(
            round_item.get("labels_created_by_mode", {}).get("brt", 0)
            for round_item in brt_rounds
        ),
        "brt_labels_accepted": sum(
            round_item.get("labels_accepted_by_mode", {}).get("brt", 0)
            for round_item in brt_rounds
        ),
        "brt_destination_label_count": len(brt_labels_at_destination),
        "brt_stops_reached_by_feeder_transfer": sorted({
            str(label.get("stop_id"))
            for label in brt_feeder_labels
        }),
        "brt_alternatives_before_filtering": len(
            brt_candidates_before_quality_filter
        ),
        "brt_alternatives_after_quality_filter": len(brt_candidate_summaries),
        "brt_alternatives_after_filtering": sum(
            1
            for alternative in alternatives
            if any(leg.get("mode") == "brt" for leg in alternative.get("legs", []))
        ),
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
    }
    if diagnostics["brt_debug"]["brt_alternatives_after_filtering"] == 0:
        if diagnostics["brt_debug"]["brt_alternatives_before_filtering"] > 0:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = (
                "brt_alternative_filtered_or_not_selected"
            )
        elif diagnostics["brt_debug"]["brt_labels_accepted"] == 0:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = (
                "brt_labels_not_accepted_or_dominated"
            )
        elif diagnostics["brt_debug"]["brt_phase1_scan_count"] == 0:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = "brt_not_scanned"
        else:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = (
                "brt_slower_than_selected_alternatives"
            )
    lrt_destination_stop_ids = {
        str(candidate["stop_id"])
        for candidate in destination_candidates
    }
    lrt_labels_at_destination = [
        label
        for stop_id, labels in labels_by_stop.items()
        if str(stop_id) in lrt_destination_stop_ids
        for label in labels
        if "lrt" in label_transit_modes(label)
    ]
    lrt_feeder_labels = [
        label
        for labels in labels_by_stop.values()
        for label in labels
        if str(label.get("stop_id", "")).startswith("LRT_")
        and any(
            leg.get("walk_type") == "lrt_feeder_transfer"
            for leg in label.get("path", [])
        )
    ]
    lrt_candidates_before_quality_filter = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "lrt" for leg in candidate.get("legs", []))
    ]
    diagnostics["lrt_debug"] = {
        "lrt_enabled_in_route_modes": any(
            mode == "lrt"
            for mode in route_modes.values()
        ),
        "lrt_stop_count": sum(
            1
            for stop_id in stop_details
            if str(stop_id).startswith("LRT_")
        ),
        "lrt_route_ids": sorted([
            route_id
            for route_id, mode in route_modes.items()
            if mode == "lrt"
        ]),
        "lrt_routes_scanned": sum(
            1
            for round_analysis in diagnostics["round_cap_analysis"]["rounds"]
            for route_entry in round_analysis.get("route_scan_order", [])
            if route_entry.get("route_mode") == "lrt"
        ),
        "lrt_labels_created": sum(
            round_item.get("labels_created_by_mode", {}).get("lrt", 0)
            for round_item in brt_rounds
        ),
        "lrt_labels_accepted": sum(
            round_item.get("labels_accepted_by_mode", {}).get("lrt", 0)
            for round_item in brt_rounds
        ),
        "lrt_destination_label_count": len(lrt_labels_at_destination),
        "lrt_stops_reached_by_feeder_transfer": sorted({
            str(label.get("stop_id"))
            for label in lrt_feeder_labels
        }),
        "lrt_alternatives_before_filtering": len(lrt_candidates_before_quality_filter),
        "lrt_alternatives_after_filtering": sum(
            1
            for alternative in alternatives
            if any(leg.get("mode") == "lrt" for leg in alternative.get("legs", []))
        ),
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
    }
    if diagnostics["lrt_debug"]["lrt_alternatives_after_filtering"] == 0:
        if diagnostics["lrt_debug"]["lrt_alternatives_before_filtering"] > 0:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = (
                "lrt_alternative_filtered_or_not_selected"
            )
        elif diagnostics["lrt_debug"]["lrt_labels_accepted"] == 0:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = (
                "lrt_labels_not_accepted_or_dominated"
            )
        elif diagnostics["lrt_debug"]["lrt_routes_scanned"] == 0:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = "lrt_not_scanned"
        else:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = (
                "lrt_slower_than_selected_alternatives"
            )
    if trace:
        trace_summary = {
            "event_count": len(trace["events"]),
            "focus_stops": trace["focus_stops"],
        }

        if trace.get("mode") == "brt":
            trace_summary.update({
                "brt_phase1_exists_in_route_modes": diagnostics["brt_debug"][
                    "brt_phase1_exists_in_route_modes"
                ],
                "brt_stop_count": diagnostics["brt_debug"]["brt_stop_count"],
                "brt_phase1_scan_count": diagnostics["brt_debug"][
                    "brt_phase1_scan_count"
                ],
                "brt_labels_created": diagnostics["brt_debug"][
                    "brt_labels_created"
                ],
                "brt_labels_accepted": diagnostics["brt_debug"][
                    "brt_labels_accepted"
                ],
                "brt_destination_label_count": diagnostics["brt_debug"][
                    "brt_destination_label_count"
                ],
                "same_route_backtracking_rejected": diagnostics["brt_debug"][
                    "same_route_backtracking_rejected"
                ],
                "brt_stops_reached_by_feeder_transfer": diagnostics["brt_debug"][
                    "brt_stops_reached_by_feeder_transfer"
                ],
                "brt_alternatives_before_filtering": diagnostics["brt_debug"][
                    "brt_alternatives_before_filtering"
                ],
                "brt_alternatives_after_filtering": diagnostics["brt_debug"][
                    "brt_alternatives_after_filtering"
                ],
            })
        elif trace.get("mode") == "lrt":
            trace_summary.update({
                "lrt_enabled_in_route_modes": diagnostics["lrt_debug"][
                    "lrt_enabled_in_route_modes"
                ],
                "lrt_stop_count": diagnostics["lrt_debug"]["lrt_stop_count"],
                "lrt_route_ids": diagnostics["lrt_debug"]["lrt_route_ids"],
                "lrt_routes_scanned": diagnostics["lrt_debug"]["lrt_routes_scanned"],
                "lrt_labels_created": diagnostics["lrt_debug"]["lrt_labels_created"],
                "lrt_labels_accepted": diagnostics["lrt_debug"]["lrt_labels_accepted"],
                "lrt_destination_label_count": diagnostics["lrt_debug"][
                    "lrt_destination_label_count"
                ],
                "lrt_stops_reached_by_feeder_transfer": diagnostics["lrt_debug"][
                    "lrt_stops_reached_by_feeder_transfer"
                ],
                "lrt_alternatives_before_filtering": diagnostics["lrt_debug"][
                    "lrt_alternatives_before_filtering"
                ],
                "lrt_alternatives_after_filtering": diagnostics["lrt_debug"][
                    "lrt_alternatives_after_filtering"
                ],
            })
        else:
            trace_summary.update({
                "metro_only_candidate_count": len(diagnostics["metro_only_candidates"]),
                "metro_candidate_event_count": sum(
                1
                for event in trace["events"]
                if "metro" in (event.get("mode_sequence") or [])
                ),
                "closest_reason": infer_metro_trace_reason(
                    trace,
                    diagnostics["metro_only_candidates"],
                    destination_candidates,
                    stop_details,
                ),
            })

        trace["summary"] = trace_summary
        diagnostics["raptor_trace"] = {
            "mode": trace["mode"],
            "summary": trace["summary"],
            "events": trace["events"],
        }

    if not alternatives:
        return {
            "found": False,
            "message": "No route found",
            "routing_diagnostics": diagnostics,
        }

    best_route = alternatives[0]
    best_route["alternatives"] = alternatives
    best_route["routing_diagnostics"] = diagnostics

    return best_route

}

station_aliases.py{
    MOBILITY_CAIRO_MAPS_EN_URL = "https://www.mobilitycairo.com/en/travel-information/maps"
MOBILITY_CAIRO_MAPS_AR_URL = "https://www.mobilitycairo.com/ar/travel-information/maps"


OFFICIAL_STATION_AREA_MAPS = [
    {
        "station_name_en": "Adly Mansour",
        "station_name_ar": "عدلي منصور",
        "aliases": ["around adly mansour", "محطة عدلي منصور", "المحيطة عدلي منصور"],
    },
    {
        "station_name_en": "El Haykestep",
        "station_name_ar": "الهايكستب",
        "aliases": ["haykstep", "haykestep", "around haykstep", "محطة الهايكستب"],
    },
    {
        "station_name_en": "Omar Ibn El Khattab",
        "station_name_ar": "عمر بن الخطاب",
        "aliases": ["omar ibn el khatab", "around omar ibn el khatab", "محطة عمر بن الخطاب"],
    },
    {
        "station_name_en": "Qubaa",
        "station_name_ar": "قباء",
        "aliases": ["qubaa", "around qubaa", "محطة قباء"],
    },
    {
        "station_name_en": "Hesham Barakat",
        "station_name_ar": "هشام بركات",
        "aliases": ["hisham barakat", "around hisham barakat", "محطة هشام بركات"],
    },
    {
        "station_name_en": "El Nozha",
        "station_name_ar": "النزهة",
        "aliases": ["nozha", "around el nozha", "محطة النزهة"],
    },
    {
        "station_name_en": "El Shams Club",
        "station_name_ar": "نادي الشمس",
        "aliases": ["shams club", "around el shams club", "محطة نادي الشمس"],
    },
    {
        "station_name_en": "Alf Maskan",
        "station_name_ar": "ألف مسكن",
        "aliases": ["alf masken", "around alf maskan", "محطة ألف مسكن"],
    },
    {
        "station_name_en": "Heliopolis",
        "station_name_ar": "هليوبوليس",
        "aliases": ["around heliopolis", "محطة هليوبوليس"],
    },
    {
        "station_name_en": "Haroun",
        "station_name_ar": "هارون",
        "aliases": ["around haroun", "محطة هارون"],
    },
    {
        "station_name_en": "El Ahram",
        "station_name_ar": "الأهرام",
        "aliases": ["al ahram", "around al ahram", "around el ahram", "محطة الأهرام"],
    },
    {
        "station_name_en": "Kolleyet El Banat",
        "station_name_ar": "كلية البنات",
        "aliases": ["kolleyet el banat", "koleyat el banat", "محطة كلية البنات"],
    },
    {
        "station_name_en": "Stadium",
        "station_name_ar": "الإستاد",
        "aliases": ["stadium", "around stadium", "محطة الإستاد"],
    },
    {
        "station_name_en": "Fair Zone",
        "station_name_ar": "أرض المعارض",
        "aliases": ["cairo fair", "fair zone", "around fair zone", "محطة أرض المعارض"],
    },
    {
        "station_name_en": "Abassiya",
        "station_name_ar": "العباسية",
        "aliases": ["abbasia", "abassiya", "around abbasia", "محطة العباسية"],
    },
    {
        "station_name_en": "Abdou Pasha",
        "station_name_ar": "عبده باشا",
        "aliases": ["abdo pasha", "abdou pasha", "around abdou pasha", "محطة عبده باشا"],
    },
    {
        "station_name_en": "El Geish",
        "station_name_ar": "الجيش",
        "aliases": ["el giesh", "around el geish", "محطة الجيش"],
    },
    {
        "station_name_en": "Bab El Shaariya",
        "station_name_ar": "باب الشعرية",
        "aliases": ["bab el shariaa", "bab el shaariya", "محطة باب الشعرية"],
    },
    {
        "station_name_en": "Attaba",
        "station_name_ar": "العتبة",
        "aliases": ["attaba", "around attaba", "محطة العتبة"],
    },
    {
        "station_name_en": "Nasser",
        "station_name_ar": "ناصر",
        "aliases": ["nasser", "محطة ناصر"],
    },
    {
        "station_name_en": "Maspero",
        "station_name_ar": "ماسبيرو",
        "aliases": ["maspero", "محطة ماسبيرو"],
    },
    {
        "station_name_en": "Safaa Hegazy",
        "station_name_ar": "صفاء حجازي",
        "aliases": ["safaa hegazy", "محطة صفاء حجازي"],
    },
    {
        "station_name_en": "Kit-Kat",
        "station_name_ar": "الكيت كات",
        "aliases": ["kitkat", "kit-kat", "kit kat", "محطة الكيت كات"],
    },
]


def normalize_station_text(value):
    return str(value or "").strip().casefold()


def station_area_records():
    records = []

    for item in OFFICIAL_STATION_AREA_MAPS:
        aliases = [
            item["station_name_en"],
            item["station_name_ar"],
            *item.get("aliases", []),
        ]
        records.append({
            "station_name_en": item["station_name_en"],
            "station_name_ar": item["station_name_ar"],
            "aliases": aliases,
            "nearby_landmarks": item.get("nearby_landmarks", []),
            "source_urls": [
                MOBILITY_CAIRO_MAPS_EN_URL,
                MOBILITY_CAIRO_MAPS_AR_URL,
            ],
            "confidence": "official_station_area_map",
            "usage": "metadata_only",
        })

    return records


STATION_AREA_RECORDS = station_area_records()


def station_area_metadata_for_stop(stop_name):
    normalized_stop_name = normalize_station_text(stop_name)

    if not normalized_stop_name:
        return None

    for record in STATION_AREA_RECORDS:
        normalized_aliases = [
            normalize_station_text(alias)
            for alias in record["aliases"]
        ]

        if any(alias and alias in normalized_stop_name for alias in normalized_aliases):
            return record

        if any(normalized_stop_name and normalized_stop_name in alias for alias in normalized_aliases):
            return record

    return None


}

transfer_builder.py{
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

}

trip_plan_builder.py{
    import datetime
import uuid

from routing.fare_calculator import calculate_leg_fare, calculate_path_fare
from routing.informal_boarding import find_informal_boarding_suggestion
from routing.journey_scorer import calculate_path_stats
from routing.postprocessing import simplify_route
from routing.walking_geometry import get_osrm_walking_geometry


MAX_GEOMETRY_POINTS = 300
METRO_PLATFORM_SUFFIXES = [
    "_METRO_N2",
    "_METRO_S2",
    "_METRO_N",
    "_METRO_S",
    "_METRO_E",
    "_METRO_W",
]


def seconds_to_hhmmss(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def squared_distance(point, stop):
    return (
        (point[0] - stop["lat"]) ** 2
        + (point[1] - stop["lon"]) ** 2
    )


def nearest_shape_index(points, stop):
    best_index = None
    best_distance = None

    for idx, point in enumerate(points):
        distance = squared_distance(point, stop)

        if best_distance is None or distance < best_distance:
            best_index = idx
            best_distance = distance

    return best_index


def decimate_geometry(points, max_points=MAX_GEOMETRY_POINTS):
    if len(points) <= max_points:
        return points

    step = (len(points) - 1) / (max_points - 1)
    decimated = []

    for i in range(max_points):
        decimated.append(points[round(i * step)])

    return decimated


def build_straight_geometry(from_stop, to_stop):
    geometry = []

    if "lat" in from_stop and "lon" in from_stop:
        geometry.append([from_stop["lat"], from_stop["lon"]])

    if "lat" in to_stop and "lon" in to_stop:
        geometry.append([to_stop["lat"], to_stop["lon"]])

    return geometry


def normalize_metro_station_id(stop_id):
    stop_id = str(stop_id)

    for suffix in METRO_PLATFORM_SUFFIXES:
        if stop_id.endswith(suffix):
            return stop_id[:-len(suffix)]

    return stop_id


def is_metro_platform_stop(stop_id):
    stop_id = str(stop_id)
    return any(stop_id.endswith(suffix) for suffix in METRO_PLATFORM_SUFFIXES)


def build_display_stop(stop):
    stop_id = str(stop.get("stop_id", ""))

    if not is_metro_platform_stop(stop_id):
        return stop

    display_stop = dict(stop)
    display_stop["platform_stop_id"] = stop_id
    display_stop["stop_id"] = normalize_metro_station_id(stop_id)
    display_stop["station_id"] = display_stop["stop_id"]
    display_stop["station_type"] = "metro"

    return display_stop


def route_transit_modes(legs):
    modes = []

    for leg in legs:
        mode = leg.get("mode")

        if not mode or mode == "walk":
            continue

        if mode not in modes:
            modes.append(mode)

    return modes


def format_mode_label(mode):
    labels = {
        "brt": "BRT",
        "lrt": "LRT",
        "metro": "Metro",
        "bus": "Bus",
        "microbus": "Microbus",
        "minibus": "Minibus",
        "monorail": "Monorail",
    }

    return labels.get(mode, str(mode).title())


def build_leg_geometry(leg, from_stop, to_stop, indexes, use_street_geometry=False):
    fallback_geometry = build_straight_geometry(from_stop, to_stop)

    if leg["mode"] == "walk":
        if use_street_geometry:
            street_geometry = get_osrm_walking_geometry(from_stop, to_stop)

            if street_geometry and len(street_geometry) >= 2:
                return decimate_geometry(street_geometry), "street_route"

        return fallback_geometry, "straight_line"

    if not indexes:
        return fallback_geometry, "straight_line"

    trip_id = leg.get("trip_id")
    shape_id = indexes.get("trip_shapes", {}).get(trip_id)

    if not shape_id:
        return fallback_geometry, "straight_line"

    shape = indexes.get("shape_points", {}).get(shape_id, [])

    if len(shape) < 2:
        return fallback_geometry, "straight_line"

    if not all(key in from_stop for key in ["lat", "lon"]):
        return fallback_geometry, "straight_line"

    if not all(key in to_stop for key in ["lat", "lon"]):
        return fallback_geometry, "straight_line"

    from_idx = nearest_shape_index(shape, from_stop)
    to_idx = nearest_shape_index(shape, to_stop)

    if from_idx is None or to_idx is None:
        return fallback_geometry, "straight_line"

    if from_idx <= to_idx:
        geometry = shape[from_idx:to_idx + 1]
    else:
        geometry = list(reversed(shape[to_idx:from_idx + 1]))

    if len(geometry) < 2:
        return fallback_geometry, "straight_line"

    return decimate_geometry(geometry), "gtfs_shape"


def format_route(
    raw_result,
    indexes=None,
    debug=False,
    use_street_geometry=False,
    origin=None
):
    raw_result = simplify_route(raw_result)
    stop_details = indexes.get("stop_details", {}) if indexes else {}

    legs = []
    path_stats = calculate_path_stats(raw_result["legs"])
    path_fare = calculate_path_fare(raw_result["legs"])

    for leg in raw_result["legs"]:
        mode = leg["mode"]
        from_stop_id = leg["from_stop_id"]
        to_stop_id = leg["to_stop_id"]
        from_stop = leg.get("from_stop") or stop_details.get(from_stop_id, {"stop_id": from_stop_id})
        to_stop = leg.get("to_stop") or stop_details.get(to_stop_id, {"stop_id": to_stop_id})
        geometry, geometry_source = build_leg_geometry(
            leg,
            from_stop,
            to_stop,
            indexes,
            use_street_geometry=use_street_geometry
        )

        formatted_leg = {
            "mode": mode,
            "from_stop_id": from_stop_id,
            "to_stop_id": to_stop_id,
            "from_stop": build_display_stop(from_stop),
            "to_stop": build_display_stop(to_stop),
            "departure_time": seconds_to_hhmmss(leg["departure_time"]),
            "arrival_time": seconds_to_hhmmss(leg["arrival_time"]),
            "travel_time": leg["arrival_time"] - leg["departure_time"],
            "waiting_time": leg.get("waiting_time", 0),
            "route_id": leg.get("route_id"),
            "trip_id": leg.get("trip_id"),
            "route_label": leg.get("route_label") or leg.get("route_id"),
            "fare": calculate_leg_fare(leg),
            "fare_currency": "EGP",
            "geometry": geometry,
            "geometry_source": geometry_source,
            "eta_adjusted": leg.get("eta_adjusted", False)
        }

        if leg.get("eta_segments"):
            formatted_leg["eta_segments"] = leg["eta_segments"]

        if mode == "walk":
            formatted_leg["walking_time"] = leg.get("walking_time", 0)
            formatted_leg["distance_meters"] = leg.get("distance_meters")
            if debug:
                formatted_leg["walk_type"] = leg.get("walk_type")
                formatted_leg["source"] = leg.get("source")
                formatted_leg["confidence"] = leg.get("confidence")

        legs.append(formatted_leg)

    transit_modes = route_transit_modes(legs)

    route_output = {
        "fare": path_fare,
        "trip_id": None,
        "route_id": None,
        "route_type": raw_result.get("route_type", "transit"),
        "label": raw_result.get("alternative_label", "Recommended route"),
        "badges": raw_result.get("badges", []),
        "transit_modes": transit_modes,
        "mode_summary": " + ".join(
            format_mode_label(mode)
            for mode in transit_modes
        ),
        "total_travel_time": raw_result["total_travel_time"],
        "total_fare": path_fare["total_fare"],
        "fare_currency": path_fare["currency"],
        "generalized_cost": raw_result.get("generalized_cost"),
        "estimated_arrival_time": seconds_to_hhmmss(raw_result["arrival_time"]),
        "confidence": "medium",
        "transfer_count": path_stats["transfer_count"],
        "total_walking_time": path_stats["walking_time"],
        "total_waiting_time": path_stats["waiting_time"],
        "legs": legs
    }

    if raw_result.get("fallback_used"):
        route_output["fallback_used"] = True
        route_output["fallback_type"] = raw_result.get("fallback_type")
        route_output["fallback_reason"] = raw_result.get("fallback_reason")

    if origin and indexes:
        route_output["informal_boarding_suggestion"] = (
            find_informal_boarding_suggestion(
                origin=origin,
                route=route_output,
                shape_points=indexes.get("shape_points", {}),
                trip_shapes=indexes.get("trip_shapes", {}),
                stop_details=stop_details,
                route_modes=indexes.get("route_modes", {})
            )
        )
    else:
        route_output["informal_boarding_suggestion"] = {"available": False}

    if debug:
        route_output["debug_score"] = raw_result.get("score")
        route_output["debug_quality"] = raw_result.get("quality", {})
        route_output["quality_penalty"] = raw_result.get("quality_penalty", 0)
        route_output["rejected_by_quality_filter"] = raw_result.get(
            "rejected_by_quality_filter"
        )

    return route_output


def build_trip_plan(
    raw_result,
    indexes=None,
    debug=False,
    use_street_geometry=False,
    origin=None,
    street_geometry_scope="none"
):
    request_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"

    if not raw_result.get("found"):
        return {
            "request_id": request_id,
            "routes": [],
            "message": raw_result.get("message", "No feasible route found"),
            "timestamp": timestamp
        }

    alternatives = raw_result.get("alternatives") or [raw_result]
    routes = []

    for index, alternative in enumerate(alternatives):
        route_uses_street_geometry = (
            use_street_geometry
            and (
                street_geometry_scope == "all"
                or (
                    street_geometry_scope == "recommended"
                    and index == 0
                )
            )
        )
        routes.append(format_route(
            alternative,
            indexes=indexes,
            debug=debug,
            use_street_geometry=route_uses_street_geometry,
            origin=origin
        ))

    response = {
        "request_id": request_id,
        "routes": routes,
        "timestamp": timestamp
    }

    if raw_result.get("fallback_used"):
        response["fallback_used"] = True
        response["fallback_type"] = raw_result.get("fallback_type")
        response["fallback_reason"] = raw_result.get("fallback_reason")

    return response

}

walking_geometry.py{
    import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from routing.nearest_stop_search import haversine_meters

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OSRM_PROFILES = [
    profile.strip()
    for profile in os.getenv("OSRM_PROFILES", "foot,walking,driving").split(",")
    if profile.strip()
]
OSRM_TIMEOUT_SECONDS = float(os.getenv("OSRM_TIMEOUT_SECONDS", "2"))
MAX_WALKING_DETOUR_RATIO = float(os.getenv("MAX_WALKING_DETOUR_RATIO", "1.8"))
SHORT_WALK_DIRECT_METERS = float(os.getenv("SHORT_WALK_DIRECT_METERS", "700"))
_geometry_cache = {}


def decode_polyline(polyline, precision=5):
    coordinates = []
    index = 0
    lat = 0
    lon = 0
    factor = 10 ** precision

    while index < len(polyline):
        result = 1
        shift = 0

        while True:
            byte = ord(polyline[index]) - 63 - 1
            index += 1
            result += byte << shift
            shift += 5

            if byte < 0x1F:
                break

        lat += ~(result >> 1) if result & 1 else result >> 1
        result = 1
        shift = 0

        while True:
            byte = ord(polyline[index]) - 63 - 1
            index += 1
            result += byte << shift
            shift += 5

            if byte < 0x1F:
                break

        lon += ~(result >> 1) if result & 1 else result >> 1
        coordinates.append([lat / factor, lon / factor])

    return coordinates


def get_osrm_walking_geometry(from_stop, to_stop):
    if not OSRM_BASE_URL:
        return None

    if not all(key in from_stop for key in ["lat", "lon"]):
        return None

    if not all(key in to_stop for key in ["lat", "lon"]):
        return None

    direct_distance = haversine_meters(
        float(from_stop["lat"]),
        float(from_stop["lon"]),
        float(to_stop["lat"]),
        float(to_stop["lon"])
    )

    cache_key = (
        round(float(from_stop["lat"]), 6),
        round(float(from_stop["lon"]), 6),
        round(float(to_stop["lat"]), 6),
        round(float(to_stop["lon"]), 6),
        ",".join(OSRM_PROFILES),
    )

    if cache_key in _geometry_cache:
        return _geometry_cache[cache_key]

    best_geometry = None
    best_distance = None

    for profile in OSRM_PROFILES:
        url = (
            f"{OSRM_BASE_URL.rstrip('/')}/route/v1/{profile}/"
            f"{from_stop['lon']},{from_stop['lat']};{to_stop['lon']},{to_stop['lat']}"
            "?overview=full&geometries=polyline"
        )

        request = Request(
            url,
            headers={
                "User-Agent": "IZEE-Graduation-Project/1.0",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=OSRM_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            continue

        if payload.get("code") != "Ok":
            continue

        routes = payload.get("routes", [])

        if not routes:
            continue

        route = routes[0]
        geometry = route.get("geometry")

        if not geometry:
            continue

        route_distance = route.get("distance")

        if (
            route_distance is not None
            and direct_distance <= SHORT_WALK_DIRECT_METERS
            and route_distance > direct_distance * MAX_WALKING_DETOUR_RATIO
        ):
            continue

        decoded_geometry = decode_polyline(geometry)

        if len(decoded_geometry) < 2:
            continue

        if best_distance is None or route_distance < best_distance:
            best_distance = route_distance
            best_geometry = decoded_geometry

    if best_geometry is None:
        return None

    _geometry_cache[cache_key] = best_geometry

    return best_geometry


def clear_walking_geometry_cache():
    _geometry_cache.clear()


def walking_geometry_cache_size():
    return len(_geometry_cache)

}

Models: 

transit_graph.py{
    from dataclasses import dataclass
from typing import List, Dict

@dataclass
class StopTime:
    stop_id: int
    arrival: int      # Seconds from midnight
    departure: int
    segment_id: str

@dataclass
class Trip:
    id: str
    route_id: str
    stop_times: List[StopTime]

@dataclass
class Route:
    id: str
    stops: List[int]
    trips: List[Trip]

class TransitGraph:
    def __init__(self):
        self.stops: Dict[int, dict] = {} # Metadata like lat/lon
        self.routes: Dict[str, Route] = {}
        self.stop_to_routes: Dict[int, List[str]] = {}
}

walking_transfer.py{
    from sqlalchemy import Column, String, Float, Integer
from database.connection import Base

class WalkingTransfer(Base):
    __tablename__ = "walking_transfer"

    from_stop_id = Column(String, primary_key=True)
    to_stop_id = Column(String, primary_key=True)
    walk_type = Column(String, primary_key=True)  # normal_transfer / emergency_access

    distance_meters = Column(Float, nullable=False)
    walking_time = Column(Integer, nullable=False)

}

main.py{
    from routing.gtfs_loader import load_multiple_gtfs
from routing.graph_builder import build_graph_from_gtfs
from routing.gtfs_validator import validate_gtfs
from routing.raptor_index_builder import build_raptor_indexes
from routing.frequency_expander import expand_frequencies
from routing.raptor_router import simple_raptor
from routing.trip_plan_builder import build_trip_plan
from routing.access_egress import build_access_candidates, build_egress_candidates
from routing.eta_provider import collect_segment_requests, get_segment_estimates
from routing.nearest_stop_search import find_candidate_stops, haversine_meters
from routing.station_aliases import station_area_metadata_for_stop
from routing.walking_geometry import (
    clear_walking_geometry_cache,
    get_osrm_walking_geometry,
    walking_geometry_cache_size,
)
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
import os
import pickle
import pytz
import threading
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from database.connection import engine, Base, SessionLocal
from models.walking_transfer import WalkingTransfer

Base.metadata.create_all(bind=engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GTFS_PATHS = [
    "C:\\Users\\omaro\\Desktop\\semeser 8\\link (7)",
    "C:\\Users\\omaro\\Desktop\\semeser 8\\Metro-GTFS-master\\Metro-GTFS-master",
]
EXPERIMENTAL_BRT_GTFS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "gtfs_experimental",
    "brt",
)
EXPERIMENTAL_LRT_GTFS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "gtfs_experimental",
    "lrt",
)

EXPERIMENTAL_BRT_ENABLED = (
    os.getenv("IZEE_ENABLE_EXPERIMENTAL_BRT", "1").lower()
    in {"1", "true", "yes", "on"}
)
EXPERIMENTAL_LRT_ENABLED = (
    os.getenv("IZEE_ENABLE_EXPERIMENTAL_LRT", "1").lower()
    in {"1", "true", "yes", "on"}
)

if EXPERIMENTAL_BRT_ENABLED:
    GTFS_PATHS.append(EXPERIMENTAL_BRT_GTFS_PATH)

if EXPERIMENTAL_LRT_ENABLED:
    GTFS_PATHS.append(EXPERIMENTAL_LRT_GTFS_PATH)

_cache_modes = []
if EXPERIMENTAL_BRT_ENABLED:
    _cache_modes.append("brt")
if EXPERIMENTAL_LRT_ENABLED:
    _cache_modes.append("lrt")
RAPTOR_CACHE_VERSION = "raptor_indexes_v7_" + (
    "_".join(_cache_modes)
    if _cache_modes
    else "base"
)
RAPTOR_CACHE_PATH = os.path.join(
    os.path.dirname(__file__),
    ".cache",
    f"{RAPTOR_CACHE_VERSION}.pkl"
)
raptor_indexes_cache = None
walking_transfers_cache = {}
brt_feeder_transfer_count_cache = 0
lrt_feeder_transfer_count_cache = 0
eta_segment_requests_cache = None
geocode_search_cache = {}
walking_transfers_preload_started = False
NORMAL_ACCESS_RADIUS_METERS = 1000
NORMAL_EGRESS_RADIUS_METERS = 700
NORMAL_ACCESS_CANDIDATE_LIMIT = 25
NORMAL_EGRESS_CANDIDATE_LIMIT = 10
EMERGENCY_ACCESS_RADIUS_METERS = 3000
EMERGENCY_EGRESS_RADIUS_METERS = 3000
UNLIMITED_NEAREST_STOP_RADIUS_METERS = None
IZEE_BRT_ACCESS_RADIUS_M = int(os.getenv("IZEE_BRT_ACCESS_RADIUS_M", "900"))
IZEE_BACKBONE_ACCESS_RADIUS_M = int(
    os.getenv("IZEE_BACKBONE_ACCESS_RADIUS_M", "1500")
)
IZEE_BACKBONE_CANDIDATES_PER_MODE = int(
    os.getenv("IZEE_BACKBONE_CANDIDATES_PER_MODE", "3")
)
IZEE_BRT_TRANSFER_RADIUS_M = int(os.getenv("IZEE_BRT_TRANSFER_RADIUS_M", "500"))
IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M = int(
    os.getenv("IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M", "900")
)
IZEE_ENABLE_BRT_FEEDER_TRANSFERS = (
    os.getenv("IZEE_ENABLE_BRT_FEEDER_TRANSFERS", "1").lower()
    in {"1", "true", "yes", "on"}
)
IZEE_LRT_TRANSFER_RADIUS_M = int(os.getenv("IZEE_LRT_TRANSFER_RADIUS_M", "500"))
IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M = int(
    os.getenv("IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M", "900")
)
IZEE_ENABLE_LRT_FEEDER_TRANSFERS = (
    os.getenv("IZEE_ENABLE_LRT_FEEDER_TRANSFERS", "1").lower()
    in {"1", "true", "yes", "on"}
)
BRT_MAJOR_INTERCHANGE_STOP_IDS = {
    "BRT_ADLY_MANSOUR",
    "BRT_MARG",
    "BRT_SALAM",
    "BRT_MOSTOROD",
}
BRT_FEEDER_MODES = {"bus", "microbus", "metro", "minibus"}
LRT_MAJOR_INTERCHANGE_STOP_IDS = {
    "LRT_ADLY_MANSOUR",
    "LRT_BADR",
    "LRT_ARTS_CULTURE",
    "LRT_CAPITAL_AIRPORT",
    "LRT_CENTRAL_CAPITAL",
}
LRT_FEEDER_MODES = {"bus", "microbus", "metro", "minibus", "brt", "monorail"}
BACKBONE_ACCESS_MODES = {"brt", "metro", "lrt", "monorail"}
BRT_STOP_ALIASES = {
    "BRT_NAZLET_QALYUB": ["???? ?????", "brt nazlet qalyub"],
    "BRT_AL_SHARQAWIYA": ["?????????", "brt al sharqawiya"],
    "BRT_SHOBRA_BANHA": ["???? ????", "brt shobra banha"],
    "BRT_BAHTEEM": ["?????", "brt bahteem"],
    "BRT_MOSTOROD": ["?????", "brt mostorod"],
    "BRT_KHOSOUS": ["??????", "brt khosous"],
    "BRT_MARG": ["?????", "brt marg"],
    "BRT_QALAG": ["?????", "brt qalag"],
    "BRT_ZAKAH_FOUNDATION": ["????? ??????", "brt zakah foundation"],
    "BRT_ORABI": ["?????", "brt orabi"],
    "BRT_SALAM": ["??????", "brt salam"],
    "BRT_ADLY_MANSOUR": ["???? ?????", "brt adly mansour"],
    "BRT_SUEZ_ROAD": ["???? ??????", "brt suez road"],
    "BRT_POLICE_ACADEMY": ["???????? ??????", "brt police academy"],
}
LRT_STOP_ALIASES = {
    "LRT_CITY_CENTER": ["???? ???????", "city center", "lrt city center"],
    "LRT_10TH_RAMADAN": ["?????? ?? ?????", "10th of ramadan", "lrt 10th of ramadan"],
    "LRT_WEST_10TH": ["??? ??????", "west 10th", "lrt west 10th"],
    "LRT_ADLY_MANSOUR": ["???? ?????", "adly mansour", "lrt adly mansour"],
    "LRT_EL_OBOUR": ["??????", "el obour", "lrt obour"],
    "LRT_FUTURE": ["????????", "future", "lrt future"],
    "LRT_EL_SHOROUK": ["??????", "el shorouk", "lrt shorouk"],
    "LRT_NEW_HELIOPOLIS": ["?????????", "new heliopolis", "lrt heliopolis"],
    "LRT_BADR": ["???", "badr", "lrt badr"],
    "LRT_EL_ROBAIKEY": ["????????", "el robaikey", "lrt robaikey"],
    "LRT_HADAYEK_AL_ASSEMA": ["????? ???????", "hadayek al assema", "capital gardens"],
    "LRT_CAPITAL_AIRPORT": ["???? ???????", "capital airport", "lrt capital airport"],
    "LRT_ARTS_CULTURE": ["????? ?????? ????????", "arts and culture city", "?????? ????????"],
    "LRT_CATHEDRAL_NATIVITY": ["????????? ???????", "cathedral of the nativity"],
    "LRT_STRATEGIC_COMMAND": ["??????? ????????????", "strategic command"],
    "LRT_INDUSTRIAL_PARK": ["??????? ????????", "industrial park"],
    "LRT_NEW_OBOUR": ["?????? ???????", "new obour"],
    "LRT_INTERNATIONAL_SPORTS_CITY": ["??????? ???????? ???????", "international sports city"],
    "LRT_CENTRAL_CAPITAL": ["??????? ????????", "central capital"],
}
DEFAULT_TRIP_DEPARTURE_TIME = os.getenv(
    "IZEE_DEFAULT_TRIP_DEPARTURE_TIME",
    "08:00:00",
)

class Coordinate(BaseModel):
    lat: float
    lon: float


class TripPlanRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    departure_time: str | None = DEFAULT_TRIP_DEPARTURE_TIME
    max_transfers: int = 2
    use_walking: bool = True


def build_geocode_query_variants(query: str):
    query = query.strip()
    variants = [
        query,
        f"{query}, Cairo",
        f"{query}, Egypt",
        f"{query}, ???????",
        f"{query}, ?????? ???????",
    ]
    seen = set()
    unique_variants = []

    for variant in variants:
        normalized = variant.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique_variants.append(variant)

    return unique_variants


def fetch_nominatim_results(query: str, limit: int):
    params = urlencode({
        "q": query,
        "format": "json",
        "limit": limit,
        "countrycodes": "eg",
        "accept-language": "ar,en",
        "addressdetails": 1,
    })

    request = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={
            "User-Agent": "IZEE-Graduation-Project/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = response.read().decode("utf-8")
    except HTTPError:
        return []
    except URLError:
        return []

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return []


def search_places_with_nominatim(query: str, limit: int = 10):
    cache_key = (query.strip().lower(), int(limit))

    if cache_key in geocode_search_cache:
        return geocode_search_cache[cache_key]

    results = []
    seen = set()

    for query_variant in build_geocode_query_variants(query):
        data = fetch_nominatim_results(query_variant, limit=limit)

        for place in data:
            if "lat" not in place or "lon" not in place:
                continue

            dedupe_key = (
                round(float(place["lat"]), 6),
                round(float(place["lon"]), 6),
                str(place.get("display_name", "")).lower(),
            )

            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            results.append({
                "name": place.get("display_name", query),
                "lat": float(place["lat"]),
                "lon": float(place["lon"]),
                "source": "openstreetmap",
                "result_type": osm_result_type(place),
                "type": osm_result_type(place),
                "matched_query": query_variant,
                "_rank": score_osm_place_result(place, query_variant),
            })

    results.sort(key=lambda result: result.pop("_rank"))
    results = results[:limit]

    geocode_search_cache[cache_key] = results
    return results


def score_osm_place_result(place, query_variant):
    name = str(place.get("display_name", "")).lower()
    variant = str(query_variant).lower()
    lat = float(place["lat"])
    lon = float(place["lon"])
    score = 0

    greater_cairo_terms = (
        "???????",
        "cairo",
        "??????",
        "giza",
        "?????????",
        "qalyubia",
    )

    if any(term in name for term in greater_cairo_terms):
        score -= 100

    if any(term in variant for term in ("cairo", "???????")):
        score -= 25

    if 29.75 <= lat <= 30.35 and 30.95 <= lon <= 31.65:
        score -= 75
    else:
        score += 75

    return score


def normalize_place_query(value):
    return str(value or "").strip().lower()


def osm_result_type(place):
    place_class = str(place.get("class", "")).lower()
    place_type = str(place.get("type", "")).lower()

    if place_class == "place" or place_type in {
        "suburb",
        "neighbourhood",
        "city",
        "town",
        "village",
        "quarter",
    }:
        return "district"

    if place_class in {"amenity", "tourism", "building", "shop", "leisure"}:
        return "landmark"

    return "osm_place"


def query_has_transit_intent(query):
    normalized = normalize_place_query(query)
    transit_terms = (
        "brt",
        "lrt",
        "metro",
        "????",
        "????",
        "station",
    )

    return any(term in normalized for term in transit_terms)


def normalize_query_for_exact_match(query):
    normalized = normalize_place_query(query)
    for term in ("brt", "lrt", "metro", "????", "????", "station"):
        normalized = normalized.replace(term, " ")
    return " ".join(normalized.split())


def internal_stop_search(query, limit=10):
    normalized_query = normalize_place_query(query)
    normalized_core_query = normalize_query_for_exact_match(query)
    indexes = get_raptor_indexes()
    stop_details = indexes.get("stop_details", {})
    route_modes = indexes.get("route_modes", {})
    routes_by_stop = indexes.get("routes_by_stop", {})
    results = []

    for stop_id, stop in stop_details.items():
        stop_id = str(stop_id)
        modes = {
            route_modes.get(route_id, "unknown")
            for route_id in routes_by_stop.get(stop_id, [])
        }
        aliases = list(BRT_STOP_ALIASES.get(stop_id, []))
        aliases.extend(LRT_STOP_ALIASES.get(stop_id, []))
        upper_stop_id = stop_id.upper()
        if "metro" in modes and "MRG_METRO" in upper_stop_id:
            aliases.extend(["?????", "metro marg"])
        if "metro" in modes and "NMR_METRO" in upper_stop_id:
            aliases.extend(["????? ???????", "new el marg", "metro new marg"])
        station_metadata = station_area_metadata_for_stop(stop.get("name", ""))

        if station_metadata:
            aliases.extend(station_metadata["aliases"])
            aliases.extend(station_metadata.get("nearby_landmarks", []))

        search_text = " ".join([
            stop_id,
            str(stop.get("name", "")),
            *aliases,
            *modes,
        ]).lower()

        if (
            normalized_query not in search_text
            and normalized_core_query not in search_text
        ):
            continue

        primary_mode = (
            "brt" if "brt" in modes
            else "metro" if "metro" in modes
            else "lrt" if "lrt" in modes
            else "monorail" if "monorail" in modes
            else "bus"
        )
        display_name = aliases[0] if aliases else stop.get("name", stop_id)
        prefix = primary_mode.upper() if primary_mode in {"brt", "metro", "lrt"} else "Transit"
        subtitle_parts = []

        if station_metadata:
            subtitle_parts.append("Official Mobility Cairo station-area map")

            if station_metadata.get("nearby_landmarks"):
                subtitle_parts.append(
                    "Nearby: " + ", ".join(station_metadata["nearby_landmarks"][:3])
                )

        result = {
            "name": f"{prefix} {display_name}",
            "display_name": f"{prefix} {display_name}",
            "subtitle": " · ".join(subtitle_parts),
            "lat": stop["lat"],
            "lon": stop["lon"],
            "source": "internal_stop",
            "result_type": "transit_stop",
            "type": "transit_stop",
            "stop_id": stop_id,
            "mode": primary_mode,
            "modes": sorted(modes),
            "_match_text": " ".join([
                str(stop.get("name", "")),
                *aliases,
            ]).lower(),
        }

        if station_metadata:
            result["station_metadata"] = {
                "station_name_en": station_metadata["station_name_en"],
                "station_name_ar": station_metadata["station_name_ar"],
                "nearby_landmarks": station_metadata.get("nearby_landmarks", []),
                "source_urls": station_metadata["source_urls"],
                "confidence": station_metadata["confidence"],
                "usage": station_metadata["usage"],
            }

        results.append(result)

    mode_order = {
        "brt": 0,
        "metro": 1,
        "lrt": 2,
        "monorail": 3,
        "bus": 4,
        "minibus": 5,
        "microbus": 6,
    }
    deduped_results = []
    seen_internal_places = set()
    for item in results:
        key = (
            item["mode"],
            item["name"],
            round(float(item["lat"]), 6),
            round(float(item["lon"]), 6),
        )
        if key in seen_internal_places:
            continue
        seen_internal_places.add(key)
        deduped_results.append(item)

    deduped_results.sort(key=lambda item: (
        mode_order.get(item["mode"], 99),
        0 if item.get("station_metadata") else 1,
        0 if item["stop_id"] in BRT_MAJOR_INTERCHANGE_STOP_IDS else 1,
        item["name"],
    ))

    return deduped_results[:limit]


def merged_place_search(query, limit=10):
    internal_results = internal_stop_search(query, limit=limit)
    osm_results = search_places_with_nominatim(query, limit=limit)
    transit_intent = query_has_transit_intent(query)
    normalized_exact = normalize_query_for_exact_match(query)
    exact_internal = []
    other_internal = []

    for place in internal_results:
        match_text = place.get("_match_text", "").lower()
        is_exact = (
            normalized_exact
            and (
                normalized_exact == match_text
                or normalized_exact in match_text.split()
                or normalized_exact in match_text
            )
        )

        if is_exact:
            exact_internal.append(place)
        else:
            other_internal.append(place)

    if transit_intent:
        ordered_candidates = [
            *exact_internal,
            *other_internal,
            *osm_results,
        ]
    else:
        ordered_candidates = [
            *exact_internal[:1],
            *osm_results[:1],
            *exact_internal[1:],
            *other_internal,
            *osm_results[1:],
        ]

    seen = set()
    merged = []

    for place in ordered_candidates:
        key = (round(float(place["lat"]), 6), round(float(place["lon"]), 6))
        if key in seen:
            continue
        seen.add(key)
        clean_place = dict(place)
        clean_place.pop("_match_text", None)
        merged.append(clean_place)

        if len(merged) >= limit:
            break

    return merged[:limit]


def time_to_seconds_value(value: str):
    h, m, s = map(int, str(value).split(":"))
    return h * 3600 + m * 60 + s


def current_cairo_time_seconds():
    now = datetime.now(pytz.timezone("Africa/Cairo"))
    return now.hour * 3600 + now.minute * 60 + now.second


def departure_time_to_seconds(value):
    if value is None:
        return time_to_seconds_value(DEFAULT_TRIP_DEPARTURE_TIME)

    text = str(value).strip()

    if not text or text.lower() in {"now", "current", "current_time"}:
        return time_to_seconds_value(DEFAULT_TRIP_DEPARTURE_TIME)

    if "T" in text:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        cairo_time = parsed.astimezone(pytz.timezone("Africa/Cairo"))
        return cairo_time.hour * 3600 + cairo_time.minute * 60 + cairo_time.second

    return time_to_seconds_value(text)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




def load_project_gtfs():
    return load_multiple_gtfs(GTFS_PATHS)

def load_raptor_indexes_from_disk():
    if not os.path.exists(RAPTOR_CACHE_PATH):
        return None

    print("Loading RAPTOR indexes from disk cache...")

    try:
        with open(RAPTOR_CACHE_PATH, "rb") as cache_file:
            return pickle.load(cache_file)
    except (OSError, pickle.PickleError, EOFError, ValueError, AttributeError) as exc:
        print(f"RAPTOR disk cache could not be loaded; rebuilding. Reason: {exc}")
        return None


def save_raptor_indexes_to_disk(indexes):
    os.makedirs(os.path.dirname(RAPTOR_CACHE_PATH), exist_ok=True)

    with open(RAPTOR_CACHE_PATH, "wb") as cache_file:
        pickle.dump(indexes, cache_file, protocol=pickle.HIGHEST_PROTOCOL)


def preload_raptor_indexes_if_cached():
    global raptor_indexes_cache

    if raptor_indexes_cache is not None:
        return

    raptor_indexes_cache = load_raptor_indexes_from_disk()

    if raptor_indexes_cache is not None:
        print("RAPTOR indexes loaded from disk cache at startup.")


def get_raptor_indexes():
    global raptor_indexes_cache

    if raptor_indexes_cache is None:
        raptor_indexes_cache = load_raptor_indexes_from_disk()

    if raptor_indexes_cache is None:
        print("Building RAPTOR indexes...")

        stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()

        expanded_trips, expanded_stop_times = expand_frequencies(
            trips,
            stop_times,
            frequencies
        )

        raptor_indexes_cache = build_raptor_indexes(
            expanded_stop_times,
            expanded_trips,
            routes,
            stops,
            shapes
        )

        save_raptor_indexes_to_disk(raptor_indexes_cache)

        print("RAPTOR indexes built and cached.")

    return raptor_indexes_cache


def get_eta_segment_requests(indexes):
    global eta_segment_requests_cache

    if eta_segment_requests_cache is None:
        eta_segment_requests_cache = collect_segment_requests(indexes)

    return eta_segment_requests_cache


def get_eta_estimates_for_routing(indexes, departure_time_seconds):
    segment_requests = get_eta_segment_requests(indexes)

    return get_segment_estimates(
        segment_requests=segment_requests,
        departure_time_seconds=departure_time_seconds
    )


@app.on_event("startup")
def startup_preload_raptor_indexes():
    preload_raptor_indexes_if_cached()
    start_walking_transfer_preload_background()

def get_walking_transfers_from_db(db: Session, walk_type: str = "normal_transfer"):
    if walk_type in walking_transfers_cache:
        return walking_transfers_cache[walk_type]

    print(f"Loading walking transfers for {walk_type}...")

    rows = db.query(WalkingTransfer).filter(
        WalkingTransfer.walk_type == walk_type
    ).all()

    transfers = {}

    for row in rows:
        transfers.setdefault(row.from_stop_id, []).append({
            "to": row.to_stop_id,
            "distance_meters": row.distance_meters,
            "walking_time": row.walking_time
        })

    walking_transfers_cache[walk_type] = transfers

    print(f"Walking transfers for {walk_type} loaded and cached.")

    return transfers


def preload_walking_transfers():
    db = SessionLocal()

    try:
        get_walking_transfers_from_db(db, walk_type="normal_transfer")
        get_walking_transfers_from_db(db, walk_type="emergency_access")
    except Exception as exc:
        print(f"Walking transfer preload failed: {exc}")
    finally:
        db.close()


def start_walking_transfer_preload_background():
    global walking_transfers_preload_started

    if walking_transfers_preload_started:
        return

    walking_transfers_preload_started = True
    thread = threading.Thread(
        target=preload_walking_transfers,
        name="walking-transfer-preload",
        daemon=True
    )
    thread.start()


def merge_walking_transfers(*transfer_maps):
    merged = {}
    best_edges = {}

    for transfer_map in transfer_maps:
        for from_stop_id, edges in transfer_map.items():
            for edge in edges:
                key = (str(from_stop_id), str(edge["to"]))
                previous = best_edges.get(key)

                if (
                    previous is None
                    or float(edge.get("distance_meters", 0))
                    < float(previous.get("distance_meters", 0))
                ):
                    best_edges[key] = edge

    for (from_stop_id, _), edge in best_edges.items():
        merged.setdefault(from_stop_id, []).append(edge)

    return merged


def stop_modes(stop_id, indexes):
    route_modes = indexes.get("route_modes", {})
    routes = indexes.get("routes_by_stop", {}).get(str(stop_id), [])

    return {
        route_modes.get(route_id, "unknown")
        for route_id in routes
    }


def is_brt_stop(stop_id, indexes):
    stop_id = str(stop_id)
    return stop_id.startswith("BRT_") or "brt" in stop_modes(stop_id, indexes)


def is_lrt_stop(stop_id, indexes):
    stop_id = str(stop_id)
    return stop_id.startswith("LRT_") or "lrt" in stop_modes(stop_id, indexes)


def build_brt_feeder_transfers(indexes):
    global brt_feeder_transfer_count_cache
    cache_key = "brt_feeder_transfer_generated"

    if cache_key in walking_transfers_cache:
        return walking_transfers_cache[cache_key]

    if not (EXPERIMENTAL_BRT_ENABLED and IZEE_ENABLE_BRT_FEEDER_TRANSFERS):
        walking_transfers_cache[cache_key] = {}
        brt_feeder_transfer_count_cache = 0
        return {}

    stop_details = indexes.get("stop_details", {})
    transfers = {}
    edge_count = 0

    brt_stop_ids = [
        stop_id
        for stop_id in stop_details
        if is_brt_stop(stop_id, indexes)
    ]

    for brt_stop_id in brt_stop_ids:
        brt_stop = stop_details[brt_stop_id]
        radius = (
            IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M
            if brt_stop_id in BRT_MAJOR_INTERCHANGE_STOP_IDS
            else IZEE_BRT_TRANSFER_RADIUS_M
        )

        for other_stop_id, other_stop in stop_details.items():
            other_stop_id = str(other_stop_id)

            if other_stop_id == brt_stop_id:
                continue

            if is_brt_stop(other_stop_id, indexes):
                continue

            modes = stop_modes(other_stop_id, indexes)
            if not modes.intersection(BRT_FEEDER_MODES):
                continue

            distance = haversine_meters(
                brt_stop["lat"],
                brt_stop["lon"],
                other_stop["lat"],
                other_stop["lon"],
            )

            if distance > radius:
                continue

            edge_base = {
                "mode": "walk",
                "distance_meters": round(distance, 2),
                "walking_time": int(distance / 1.3),
                "walk_type": "brt_feeder_transfer",
                "source": "generated_brt_feeder",
                "confidence": "medium",
            }
            transfers.setdefault(brt_stop_id, []).append({
                **edge_base,
                "to": other_stop_id,
            })
            transfers.setdefault(other_stop_id, []).append({
                **edge_base,
                "to": brt_stop_id,
            })
            edge_count += 2

    walking_transfers_cache[cache_key] = transfers
    brt_feeder_transfer_count_cache = edge_count
    print(f"Generated {edge_count} BRT feeder walking transfers.")

    return transfers


def build_lrt_feeder_transfers(indexes):
    global lrt_feeder_transfer_count_cache
    cache_key = "lrt_feeder_transfer_generated"

    if cache_key in walking_transfers_cache:
        return walking_transfers_cache[cache_key]

    if not (EXPERIMENTAL_LRT_ENABLED and IZEE_ENABLE_LRT_FEEDER_TRANSFERS):
        walking_transfers_cache[cache_key] = {}
        lrt_feeder_transfer_count_cache = 0
        return {}

    stop_details = indexes.get("stop_details", {})
    transfers = {}
    edge_count = 0

    lrt_stop_ids = [
        stop_id
        for stop_id in stop_details
        if is_lrt_stop(stop_id, indexes)
    ]

    for lrt_stop_id in lrt_stop_ids:
        lrt_stop = stop_details[lrt_stop_id]
        radius = (
            IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M
            if lrt_stop_id in LRT_MAJOR_INTERCHANGE_STOP_IDS
            else IZEE_LRT_TRANSFER_RADIUS_M
        )

        for other_stop_id, other_stop in stop_details.items():
            other_stop_id = str(other_stop_id)

            if other_stop_id == lrt_stop_id:
                continue

            if is_lrt_stop(other_stop_id, indexes):
                continue

            modes = stop_modes(other_stop_id, indexes)
            if not modes.intersection(LRT_FEEDER_MODES):
                continue

            distance = haversine_meters(
                lrt_stop["lat"],
                lrt_stop["lon"],
                other_stop["lat"],
                other_stop["lon"],
            )

            if distance > radius:
                continue

            edge_base = {
                "mode": "walk",
                "distance_meters": round(distance, 2),
                "walking_time": int(distance / 1.3),
                "walk_type": "lrt_feeder_transfer",
                "source": "generated_lrt_feeder",
                "confidence": "medium",
            }
            transfers.setdefault(lrt_stop_id, []).append({
                **edge_base,
                "to": other_stop_id,
            })
            transfers.setdefault(other_stop_id, []).append({
                **edge_base,
                "to": lrt_stop_id,
            })
            edge_count += 2

    walking_transfers_cache[cache_key] = transfers
    lrt_feeder_transfer_count_cache = edge_count
    print(f"Generated {edge_count} LRT feeder walking transfers.")

    return transfers


def nearest_brt_candidates(point, indexes, radius_meters=None, limit=3):
    radius_meters = radius_meters or IZEE_BRT_ACCESS_RADIUS_M
    brt_stop_details = {
        stop_id: stop
        for stop_id, stop in indexes.get("stop_details", {}).items()
        if is_brt_stop(stop_id, indexes)
    }

    return find_candidate_stops(
        lat=point["lat"],
        lon=point["lon"],
        stop_details=brt_stop_details,
        max_distance_meters=radius_meters,
        limit=limit,
    )


def nearest_lrt_candidates(point, indexes, radius_meters=None, limit=3):
    radius_meters = radius_meters or IZEE_BACKBONE_ACCESS_RADIUS_M
    lrt_stop_details = {
        stop_id: stop
        for stop_id, stop in indexes.get("stop_details", {}).items()
        if is_lrt_stop(stop_id, indexes)
    }

    return find_candidate_stops(
        lat=point["lat"],
        lon=point["lon"],
        stop_details=lrt_stop_details,
        max_distance_meters=radius_meters,
        limit=limit,
    )


def nearest_backbone_candidates_by_mode(
    point,
    indexes,
    radius_meters=IZEE_BACKBONE_ACCESS_RADIUS_M,
    per_mode_limit=IZEE_BACKBONE_CANDIDATES_PER_MODE,
    modes=BACKBONE_ACCESS_MODES,
):
    candidates = []
    stop_details = indexes.get("stop_details", {})

    for mode in modes:
        mode_stop_details = {
            stop_id: stop
            for stop_id, stop in stop_details.items()
            if mode in stop_modes(stop_id, indexes)
        }

        mode_candidates = find_candidate_stops(
            lat=point["lat"],
            lon=point["lon"],
            stop_details=mode_stop_details,
            max_distance_meters=radius_meters,
            limit=per_mode_limit,
        )

        for candidate in mode_candidates:
            candidate["candidate_policy"] = f"nearest_{mode}_backbone"

        candidates.extend(mode_candidates)

    return candidates


def nearest_backbone_candidates_unbounded(
    point,
    indexes,
    per_mode_limit=1,
    modes=BACKBONE_ACCESS_MODES,
):
    return nearest_backbone_candidates_by_mode(
        point=point,
        indexes=indexes,
        radius_meters=None,
        per_mode_limit=per_mode_limit,
        modes=modes,
    )


def merge_candidates_with_priority(base_candidates, priority_candidates, indexes=None):
    by_stop_id = {
        str(candidate["stop_id"]): candidate
        for candidate in base_candidates
    }

    for candidate in priority_candidates:
        stop_id = str(candidate["stop_id"])
        previous = by_stop_id.get(stop_id)

        if (
            previous is None
            or candidate["distance_meters"] < previous["distance_meters"]
        ):
            by_stop_id[stop_id] = candidate

    return sorted(
        by_stop_id.values(),
        key=lambda candidate: (
            0 if indexes is not None
            and stop_modes(candidate["stop_id"], indexes).intersection(BACKBONE_ACCESS_MODES)
            else 1,
            candidate["distance_meters"],
        ),
    )


def annotate_emergency_fallback(raw_result, reason):
    raw_result["fallback_used"] = True
    raw_result["fallback_type"] = "emergency_access"
    raw_result["fallback_reason"] = reason

    for alternative in raw_result.get("alternatives", []):
        alternative["fallback_used"] = True
        alternative["fallback_type"] = "emergency_access"
        alternative["fallback_reason"] = reason

    return raw_result


def is_metro_stop_detail(stop):
    stop_id = str(stop.get("stop_id", "")).upper()
    stop_name = str(stop.get("name", "")).upper()

    return "_METRO" in stop_id or " METRO" in stop_name or stop_name.endswith("METRO")


def nearby_stop_failure_response(kind, point, stop_details, max_distance_meters):
    wider_candidates = build_access_candidates(
        origin=point,
        stop_details=stop_details,
        max_distance_meters=5000,
        limit=3
    )

    return {
        "request_id": None,
        "routes": [],
        "message": (
            f"No nearby {kind} stops found within {max_distance_meters} meters. "
            "Try choosing a place closer to the transit coverage area."
        ),
        "nearest_stops": [
            {
                "stop_id": candidate["stop_id"],
                "name": candidate.get("stop", {}).get("name"),
                "distance_meters": candidate["distance_meters"],
                "walking_time": candidate["walking_time"],
            }
            for candidate in wider_candidates
        ],
    }


def summarize_candidate_stop(candidate, indexes):
    stop_id = str(candidate["stop_id"])
    routes = indexes["routes_by_stop"].get(stop_id, [])
    modes = sorted(stop_modes(stop_id, indexes))
    primary_mode = (
        "brt" if "brt" in modes
        else "metro" if "metro" in modes
        else "lrt" if "lrt" in modes
        else "monorail" if "monorail" in modes
        else modes[0] if modes
        else "unknown"
    )

    return {
        "stop_id": stop_id,
        "stop_name": candidate.get("stop", {}).get("name"),
        "name": candidate.get("stop", {}).get("name"),
        "mode": primary_mode,
        "station_type": (
            "backbone"
            if set(modes).intersection(BACKBONE_ACCESS_MODES)
            else "surface"
        ),
        "distance_meters": candidate["distance_meters"],
        "walking_time": candidate["walking_time"],
        "candidate_policy": candidate.get("candidate_policy", "nearest_overall"),
        "routes_available": routes,
        "route_modes_available": modes,
        "reachable_routes": [
            {
                "route_id": route_id,
                "label": indexes["route_labels"].get(route_id, route_id),
                "mode": indexes["route_modes"].get(route_id, "unknown"),
            }
            for route_id in routes
        ],
    }

@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/geocode/search")
def geocode_search(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=10),
    debug: bool = False
):
    started_at = time.perf_counter()
    limit = int(limit)
    results = search_places_with_nominatim(query, limit=limit)
    response = {
        "query": query,
        "results": results
    }

    if debug:
        response["debug"] = {
            "performance": {
                "geocoding_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2
                )
            }
        }

    return {
        **response
    }


@app.get("/places/search")
def places_search(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=10),
    debug: bool = False
):
    started_at = time.perf_counter()
    limit = int(limit)
    results = merged_place_search(query, limit=limit)
    response = {
        "query": query,
        "results": results,
    }

    if debug:
        response["debug"] = {
            "performance": {
                "places_search_ms": round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                ),
            },
            "internal_result_count": sum(
                1
                for result in results
                if result.get("source") == "internal_stop"
            ),
            "brt_enabled": EXPERIMENTAL_BRT_ENABLED,
        }

    return response


@app.get("/debug/graph")
def debug_graph():
    stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()

    graph = build_graph_from_gtfs(stop_times, trips)

    return graph

@app.get("/debug/transfers")
def debug_transfers(
    walk_type: str = "normal_transfer",
    limit: int = 100,
    db: Session = Depends(get_db)
):
    transfers = db.query(WalkingTransfer).filter(
        WalkingTransfer.walk_type == walk_type
    ).limit(limit).all()

    return {
        "walk_type": walk_type,
        "limit": limit,
        "transfers": [
            {
                "from": t.from_stop_id,
                "to": t.to_stop_id,
                "mode": "walk",
                "walk_type": t.walk_type,
                "distance_meters": t.distance_meters,
                "walking_time": t.walking_time
            }
            for t in transfers
        ]
    }

@app.get("/debug/transfers/{stop_id}")
def debug_transfers_for_stop(
    stop_id: str,
    walk_type: str = "normal_transfer",
    db: Session = Depends(get_db)
):
    transfers = db.query(WalkingTransfer).filter(
        WalkingTransfer.from_stop_id == stop_id,
        WalkingTransfer.walk_type == walk_type
    ).all()

    return {
        "stop_id": stop_id,
        "walk_type": walk_type,
        "transfers": [
            {
                "to": t.to_stop_id,
                "mode": "walk",
                "walk_type": t.walk_type,
                "distance_meters": t.distance_meters,
                "walking_time": t.walking_time
            }
            for t in transfers
        ]
    }


@app.get("/debug/metro/stops")
def debug_metro_stops(limit: int = 50):
    indexes = get_raptor_indexes()
    metro_stops = [
        stop
        for stop in indexes["stop_details"].values()
        if is_metro_stop_detail(stop)
    ]

    return {
        "count": len(metro_stops),
        "sample": metro_stops[:limit]
    }


@app.get("/debug/stops/search")
def debug_search_stops(query: str, limit: int = 20):
    indexes = get_raptor_indexes()
    query_upper = query.upper()
    matches = [
        stop
        for stop in indexes["stop_details"].values()
        if query_upper in str(stop.get("name", "")).upper()
        or query_upper in str(stop.get("stop_id", "")).upper()
    ]

    return {
        "query": query,
        "count": len(matches),
        "sample": matches[:limit]
    }


@app.get("/debug/metro/transfers/{stop_id}")
def debug_metro_transfers_for_stop(
    stop_id: str,
    walk_type: str = "normal_transfer",
    db: Session = Depends(get_db)
):
    indexes = get_raptor_indexes()
    stop_details = indexes["stop_details"]

    rows = db.query(WalkingTransfer).filter(
        WalkingTransfer.from_stop_id == stop_id,
        WalkingTransfer.walk_type == walk_type
    ).all()

    metro_transfers = []

    for row in rows:
        to_stop = stop_details.get(row.to_stop_id, {"stop_id": row.to_stop_id})

        if not is_metro_stop_detail(to_stop):
            continue

        metro_transfers.append({
            "to": row.to_stop_id,
            "to_stop": to_stop,
            "distance_meters": row.distance_meters,
            "walking_time": row.walking_time
        })

    metro_transfers.sort(key=lambda item: item["distance_meters"])

    return {
        "stop_id": stop_id,
        "from_stop": stop_details.get(stop_id, {"stop_id": stop_id}),
        "walk_type": walk_type,
        "metro_transfer_count": len(metro_transfers),
        "metro_transfers": metro_transfers
    }


@app.post("/debug/cache/clear-walking-transfers")
def debug_clear_walking_transfer_cache():
    walking_transfers_cache.clear()

    return {"status": "walking_transfer_cache_cleared"}


@app.post("/debug/cache/clear-walking-geometry")
def debug_clear_walking_geometry_cache():
    clear_walking_geometry_cache()

    return {"status": "walking_geometry_cache_cleared"}


@app.get("/debug/walking-geometry")
def debug_walking_geometry(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float
):
    geometry = get_osrm_walking_geometry(
        {"lat": from_lat, "lon": from_lon},
        {"lat": to_lat, "lon": to_lon}
    )

    return {
        "source": "street_route" if geometry else "fallback_unavailable",
        "point_count": len(geometry) if geometry else 0,
        "cache_size": walking_geometry_cache_size(),
        "geometry": geometry or []
    }

@app.get("/debug/gtfs/validate")
def debug_validate_gtfs():
    stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()

    report = validate_gtfs(
        stops=stops,
        routes=routes,
        trips=trips,
        stop_times=stop_times,
        calendar=calendar
    )

    return report

@app.get("/debug/frequencies/expand")
def debug_expand_frequencies():
    stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()

    expanded_trips, expanded_stop_times = expand_frequencies(
        trips,
        stop_times,
        frequencies
    )

    frequency_trip_ids = set(frequencies["trip_id"].astype(str))

    remaining_template_trips = expanded_trips[
        expanded_trips["trip_id"].astype(str).isin(frequency_trip_ids)
    ]

    return {
        "original_trips": len(trips),
        "original_stop_times": len(stop_times),
        "frequency_template_trips": len(frequency_trip_ids),
        "expanded_trips": len(expanded_trips),
        "expanded_stop_times": len(expanded_stop_times),
        "remaining_template_trips": len(remaining_template_trips),
        "generated_virtual_trips": len(expanded_trips) - (len(trips) - len(frequency_trip_ids)),
        "generated_stop_times": len(expanded_stop_times) - len(
            stop_times[
                ~stop_times["trip_id"].astype(str).isin(frequency_trip_ids)
            ]
        )
    }

@app.get("/debug/index/routes-by-stop/{stop_id}")
def debug_routes_by_stop(stop_id: str):
    indexes = get_raptor_indexes()

    return {
        "stop_id": stop_id,
        "routes": indexes["routes_by_stop"].get(stop_id, [])
    }

@app.get("/debug/index/stops-by-route/{route_id}")
def debug_stops_by_route(route_id: str):
    indexes = get_raptor_indexes()

    return {
        "route_id": route_id,
        "stops": indexes["stops_by_route"].get(route_id, [])
    }

@app.get("/debug/index/trips-by-route/{route_id}")
def debug_trips_by_route(route_id: str):
    indexes = get_raptor_indexes()

    return {
        "route_id": route_id,
        "trips": indexes["trips_by_route"].get(route_id, [])
    }

@app.get("/debug/index/cache-status")
def debug_index_cache_status():
    if raptor_indexes_cache is None:
        return {
            "status": "not_built",
            "disk_cache_exists": os.path.exists(RAPTOR_CACHE_PATH),
            "eta_segment_requests": 0 if eta_segment_requests_cache is None else len(eta_segment_requests_cache),
            "walking_transfer_cache": {
                walk_type: sum(len(edges) for edges in transfers.values())
                for walk_type, transfers in walking_transfers_cache.items()
            }
        }

    return {
        "status": "built",
        "disk_cache_exists": os.path.exists(RAPTOR_CACHE_PATH),
        "routes_by_stop": len(raptor_indexes_cache["routes_by_stop"]),
        "stops_by_route": len(raptor_indexes_cache["stops_by_route"]),
        "trips_by_route": len(raptor_indexes_cache["trips_by_route"]),
        "stop_times_by_trip": len(raptor_indexes_cache["stop_times_by_trip"]),
        "route_modes": len(raptor_indexes_cache["route_modes"]),
        "route_labels": len(raptor_indexes_cache["route_labels"]),
        "stop_details": len(raptor_indexes_cache["stop_details"]),
        "shape_points": len(raptor_indexes_cache["shape_points"]),
        "trip_shapes": len(raptor_indexes_cache["trip_shapes"]),
        "trip_stop_index": len(raptor_indexes_cache["trip_stop_index"]),
        "eta_segment_requests": len(get_eta_segment_requests(raptor_indexes_cache)),
        "walking_geometry_cache_size": walking_geometry_cache_size(),
        "walking_transfer_cache": {
            walk_type: sum(len(edges) for edges in transfers.values())
            for walk_type, transfers in walking_transfers_cache.items()
        }
    }


@app.post("/debug/cache/clear-raptor-indexes")
def debug_clear_raptor_index_cache():
    global raptor_indexes_cache, eta_segment_requests_cache

    raptor_indexes_cache = None
    eta_segment_requests_cache = None

    if os.path.exists(RAPTOR_CACHE_PATH):
        os.remove(RAPTOR_CACHE_PATH)

    return {"status": "raptor_index_cache_cleared"}

@app.get("/debug/route/stop-to-stop")
def debug_route_stop_to_stop(
    origin_stop_id: str,
    destination_stop_id: str,
    departure_time: int = 21600,
    max_transfers: int = 2,
    use_walking: bool = True,
    trace: str | None = None,
    db: Session = Depends(get_db)
):
    timings = {}

    start = time.perf_counter()
    indexes = get_raptor_indexes()
    timings["indexes_seconds"] = round(time.perf_counter() - start, 4)

    walking_transfers = {}

    if use_walking:
        start = time.perf_counter()
        walking_transfers = merge_walking_transfers(
            get_walking_transfers_from_db(
                db,
                walk_type="normal_transfer"
            ),
            build_brt_feeder_transfers(indexes)
        )
        timings["walking_seconds"] = round(time.perf_counter() - start, 4)
    else:
        timings["walking_seconds"] = 0

    start = time.perf_counter()
    eta_estimates = get_eta_estimates_for_routing(
        indexes,
        departure_time_seconds=departure_time
    )
    timings["eta_seconds"] = round(time.perf_counter() - start, 4)
    timings["eta_estimate_count"] = len(eta_estimates)

    start = time.perf_counter()
    result = simple_raptor(
        indexes=indexes,
        origin_stop_id=origin_stop_id,
        destination_stop_id=destination_stop_id,
        departure_time_seconds=departure_time,
        max_transfers=max_transfers,
        walking_transfers=walking_transfers,
        eta_estimates=eta_estimates,
        trace_mode=trace,
        collect_diagnostics=True,
    )
    timings["raptor_seconds"] = round(time.perf_counter() - start, 4)
    result["timings"] = timings

    return result

@app.get("/trip-plan/stop-to-stop")
def trip_plan_stop_to_stop(
    origin_stop_id: str,
    destination_stop_id: str,
    departure_time: int = 21600,
    max_transfers: int = 2,
    use_walking: bool = True,
    debug: bool = False,
    trace: str | None = None,
    street_geometry: bool = False,
    street_geometry_scope: str = "none",
    db: Session = Depends(get_db)
):
    indexes = get_raptor_indexes()
    walking_transfers = {}

    if use_walking:
        walking_transfers = merge_walking_transfers(
            get_walking_transfers_from_db(
                db=db,
                walk_type="normal_transfer"
            ),
            build_brt_feeder_transfers(indexes),
            build_lrt_feeder_transfers(indexes)
        )

    eta_estimates = get_eta_estimates_for_routing(
        indexes,
        departure_time_seconds=departure_time
    )

    raw_result = simple_raptor(
        indexes=indexes,
        origin_stop_id=origin_stop_id,
        destination_stop_id=destination_stop_id,
        departure_time_seconds=departure_time,
        max_transfers=max_transfers,
        walking_transfers=walking_transfers,
        eta_estimates=eta_estimates,
        trace_mode=trace if debug else None,
        collect_diagnostics=debug,
    )

    return build_trip_plan(
        raw_result,
        indexes,
        debug=debug,
        use_street_geometry=street_geometry,
        street_geometry_scope=street_geometry_scope
    )

@app.post("/trip-plan")
def trip_plan(
    request: TripPlanRequest,
    debug: bool = False,
    trace: str | None = None,
    street_geometry: bool = False,
    street_geometry_scope: str = "none",
    db: Session = Depends(get_db)
):
    timings = {}
    request_start = time.perf_counter()

    start = time.perf_counter()
    indexes = get_raptor_indexes()
    timings["indexes_seconds"] = round(time.perf_counter() - start, 4)

    stop_details = indexes["stop_details"]
    departure_time_seconds = departure_time_to_seconds(request.departure_time)

    origin = request.origin.model_dump()
    destination = request.destination.model_dump()

    start = time.perf_counter()
    origin_candidates = build_access_candidates(
        origin=origin,
        stop_details=stop_details,
        max_distance_meters=NORMAL_ACCESS_RADIUS_METERS,
        limit=NORMAL_ACCESS_CANDIDATE_LIMIT
    )
    nearest_origin_brt = nearest_brt_candidates(origin, indexes)
    nearest_origin_lrt = nearest_lrt_candidates(origin, indexes)
    nearest_origin_backbone = nearest_backbone_candidates_by_mode(origin, indexes)
    nearest_origin_backbone_unbounded = nearest_backbone_candidates_unbounded(
        origin,
        indexes,
    )
    origin_candidates = merge_candidates_with_priority(
        origin_candidates,
        nearest_origin_backbone,
        indexes=indexes,
    )[:NORMAL_ACCESS_CANDIDATE_LIMIT]
    timings["access_candidates_seconds"] = round(
        time.perf_counter() - start,
        4
    )

    start = time.perf_counter()
    destination_candidates = build_egress_candidates(
        destination=destination,
        stop_details=stop_details,
        max_distance_meters=NORMAL_EGRESS_RADIUS_METERS,
        limit=NORMAL_EGRESS_CANDIDATE_LIMIT,
        max_extra_distance_meters=NORMAL_EGRESS_RADIUS_METERS
    )
    nearest_destination_brt = nearest_brt_candidates(destination, indexes)
    nearest_destination_lrt = nearest_lrt_candidates(destination, indexes)
    nearest_destination_backbone = nearest_backbone_candidates_by_mode(destination, indexes)
    nearest_destination_backbone_unbounded = nearest_backbone_candidates_unbounded(
        destination,
        indexes,
    )
    destination_candidates = merge_candidates_with_priority(
        destination_candidates,
        nearest_destination_backbone,
        indexes=indexes,
    )[:NORMAL_EGRESS_CANDIDATE_LIMIT]
    timings["egress_candidates_seconds"] = round(
        time.perf_counter() - start,
        4
    )

    emergency_candidate_reason = None

    if not origin_candidates:
        start = time.perf_counter()
        origin_candidates = build_access_candidates(
            origin=origin,
            stop_details=stop_details,
            max_distance_meters=UNLIMITED_NEAREST_STOP_RADIUS_METERS,
            limit=NORMAL_ACCESS_CANDIDATE_LIMIT
        )
        timings["emergency_origin_candidates_seconds"] = round(
            time.perf_counter() - start,
            4
        )
        emergency_candidate_reason = "no_origin_stop_within_normal_radius_using_nearest_available_stop"

    if not destination_candidates:
        start = time.perf_counter()
        destination_candidates = build_egress_candidates(
            destination=destination,
            stop_details=stop_details,
            max_distance_meters=UNLIMITED_NEAREST_STOP_RADIUS_METERS,
            limit=NORMAL_EGRESS_CANDIDATE_LIMIT,
            max_extra_distance_meters=500
        )
        timings["emergency_destination_candidates_seconds"] = round(
            time.perf_counter() - start,
            4
        )
        emergency_candidate_reason = "no_destination_stop_within_normal_radius_using_nearest_available_stop"

    if not origin_candidates:
        return nearby_stop_failure_response(
            "origin",
            origin,
            stop_details,
            max_distance_meters=EMERGENCY_ACCESS_RADIUS_METERS
        )

    if not destination_candidates:
        return nearby_stop_failure_response(
            "destination",
            destination,
            stop_details,
            max_distance_meters=EMERGENCY_EGRESS_RADIUS_METERS
        )

    walking_transfers = {}
    emergency_walking_transfers = {}
    brt_feeder_transfers = {}
    lrt_feeder_transfers = {}

    if request.use_walking:
        start = time.perf_counter()
        walking_transfers = get_walking_transfers_from_db(
            db=db,
            walk_type="normal_transfer"
        )
        brt_feeder_transfers = build_brt_feeder_transfers(indexes)
        lrt_feeder_transfers = build_lrt_feeder_transfers(indexes)
        emergency_walking_transfers = get_walking_transfers_from_db(
            db=db,
            walk_type="emergency_access"
        )
        timings["walking_seconds"] = round(time.perf_counter() - start, 4)
    else:
        timings["walking_seconds"] = 0

    start = time.perf_counter()
    eta_estimates = get_eta_estimates_for_routing(
        indexes,
        departure_time_seconds=departure_time_seconds
    )
    timings["eta_seconds"] = round(time.perf_counter() - start, 4)
    timings["eta_estimate_count"] = len(eta_estimates)

    start = time.perf_counter()
    fallback_reason = emergency_candidate_reason
    routing_walking_transfers = merge_walking_transfers(
        walking_transfers,
        brt_feeder_transfers,
        lrt_feeder_transfers,
    )

    if fallback_reason and request.use_walking:
        routing_walking_transfers = merge_walking_transfers(
            walking_transfers,
            brt_feeder_transfers,
            lrt_feeder_transfers,
            emergency_walking_transfers
        )

    raw_result = simple_raptor(
        indexes=indexes,
        departure_time_seconds=departure_time_seconds,
        max_transfers=request.max_transfers,
        walking_transfers=routing_walking_transfers,
        origin_candidates=origin_candidates,
        destination_candidates=destination_candidates,
        final_origin=origin,
        final_destination=destination,
        eta_estimates=eta_estimates,
        trace_mode=trace if debug else None,
        collect_diagnostics=debug,
    )

    if (
        request.use_walking
        and not raw_result.get("found")
        and not fallback_reason
    ):
        fallback_reason = "normal_route_not_found"
        raw_result = simple_raptor(
            indexes=indexes,
            departure_time_seconds=departure_time_seconds,
            max_transfers=request.max_transfers,
            walking_transfers=merge_walking_transfers(
                walking_transfers,
                brt_feeder_transfers,
                lrt_feeder_transfers,
                emergency_walking_transfers
            ),
            origin_candidates=origin_candidates,
            destination_candidates=destination_candidates,
            final_origin=origin,
            final_destination=destination,
            eta_estimates=eta_estimates,
            trace_mode=trace if debug else None,
            collect_diagnostics=debug,
        )

    if fallback_reason and raw_result.get("found"):
        annotate_emergency_fallback(raw_result, fallback_reason)

    timings["raptor_seconds"] = round(time.perf_counter() - start, 4)
    raw_result["timings"] = timings

    build_start = time.perf_counter()
    response = build_trip_plan(
        raw_result,
        indexes,
        debug=debug,
        use_street_geometry=street_geometry,
        origin=origin,
        street_geometry_scope=street_geometry_scope,
    )
    timings["response_build_seconds"] = round(
        time.perf_counter() - build_start,
        4
    )
    timings["total_seconds"] = round(
        time.perf_counter() - request_start,
        4
    )

    if debug:
        routing_diagnostics = raw_result.get("routing_diagnostics", {})
        stage_timings = routing_diagnostics.get("stage_timings_seconds", {})
        performance = {
            "access_ms": round(
                timings.get("access_candidates_seconds", 0) * 1000,
                2,
            ),
            "egress_ms": round(
                timings.get("egress_candidates_seconds", 0) * 1000,
                2,
            ),
            "raptor_ms": round(
                timings.get("raptor_seconds", 0) * 1000,
                2,
            ),
            "raptor_rounds_ms": round(
                stage_timings.get("raptor_rounds", 0) * 1000,
                2,
            ),
            "label_creation_ms": round(
                stage_timings.get("raptor_rounds", 0) * 1000,
                2,
            ),
            "dominance_checks_ms": round(
                stage_timings.get("raptor_rounds", 0) * 1000,
                2,
            ),
            "reconstruction_ms": round(
                stage_timings.get("candidate_reconstruction", 0) * 1000,
                2,
            ),
            "alternatives_ms": round(
                stage_timings.get("alternative_generation", 0) * 1000,
                2,
            ),
            "alternative_deduplication_ms": round(
                stage_timings.get("alternative_generation", 0) * 1000,
                2,
            ),
            "geometry_ms": round(
                timings.get("response_build_seconds", 0) * 1000,
                2,
            ),
            "osrm_ms": (
                round(timings.get("response_build_seconds", 0) * 1000, 2)
                if street_geometry
                else 0
            ),
            "response_serialization_ms": round(
                timings.get("response_build_seconds", 0) * 1000,
                2,
            ),
            "total_ms": round(
                timings.get("total_seconds", 0) * 1000,
                2,
            ),
        }
        response["debug"] = {
            "timings": timings,
            "performance": performance,
            "origin_candidates": [
                summarize_candidate_stop(candidate, indexes)
                for candidate in origin_candidates
            ],
            "destination_candidates": [
                summarize_candidate_stop(candidate, indexes)
                for candidate in destination_candidates
            ],
            "brt_access": {
                "enabled": EXPERIMENTAL_BRT_ENABLED,
                "feeder_transfers_enabled": IZEE_ENABLE_BRT_FEEDER_TRANSFERS,
                "access_radius_m": IZEE_BRT_ACCESS_RADIUS_M,
                "backbone_access_radius_m": IZEE_BACKBONE_ACCESS_RADIUS_M,
                "backbone_candidates_per_mode": IZEE_BACKBONE_CANDIDATES_PER_MODE,
                "transfer_radius_m": IZEE_BRT_TRANSFER_RADIUS_M,
                "major_interchange_radius_m": IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M,
                "generated_brt_feeder_transfer_count": brt_feeder_transfer_count_cache,
                "nearest_origin_brt_stops": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_origin_brt
                ],
                "nearest_destination_brt_stops": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_destination_brt
                ],
                "nearest_origin_backbone_stops": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_origin_backbone
                ],
                "nearest_destination_backbone_stops": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_destination_backbone
                ],
                "nearest_origin_backbone_stops_unbounded": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_origin_backbone_unbounded
                ],
                "nearest_destination_backbone_stops_unbounded": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_destination_backbone_unbounded
                ],
                "origin_brt_injected": bool(nearest_origin_brt),
                "destination_brt_injected": bool(nearest_destination_brt),
            },
            "lrt_access": {
                "enabled": EXPERIMENTAL_LRT_ENABLED,
                "feeder_transfers_enabled": IZEE_ENABLE_LRT_FEEDER_TRANSFERS,
                "transfer_radius_m": IZEE_LRT_TRANSFER_RADIUS_M,
                "major_interchange_radius_m": IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M,
                "generated_lrt_feeder_transfer_count": lrt_feeder_transfer_count_cache,
                "nearest_origin_lrt_stops": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_origin_lrt
                ],
                "nearest_destination_lrt_stops": [
                    summarize_candidate_stop(candidate, indexes)
                    for candidate in nearest_destination_lrt
                ],
                "origin_lrt_injected": bool(nearest_origin_lrt),
                "destination_lrt_injected": bool(nearest_destination_lrt),
            },
            "routing_diagnostics": routing_diagnostics,
            "lrt_debug": routing_diagnostics.get("lrt_debug"),
            "brt_debug": routing_diagnostics.get("brt_debug"),
            "round_cap_analysis": (
                raw_result
                .get("routing_diagnostics", {})
                .get("round_cap_analysis")
            ),
            "raptor_trace": (
                raw_result
                .get("routing_diagnostics", {})
                .get("raptor_trace")
            ),
        }

    return response

@app.get("/debug/modes/routes")
def debug_route_modes():
    indexes = get_raptor_indexes()
    route_modes = indexes["route_modes"]

    summary = {}
    for mode in route_modes.values():
        summary[mode] = summary.get(mode, 0) + 1

    return {
        "summary": summary,
        "sample": dict(list(route_modes.items())[:50])
    }

@app.get("/debug/modes/routes/{route_id}")
def debug_route_mode(route_id: str):
    indexes = get_raptor_indexes()

    return {
        "route_id": route_id,
        "mode": indexes["route_modes"].get(route_id, "unknown")
    }

@app.get("/debug/agencies")
def debug_agencies():
    stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()

    if "agency_id" not in routes.columns:
        return {"error": "agency_id column missing"}

    agencies = routes["agency_id"].dropna().unique().tolist()

    return {
        "agencies": sorted([str(a) for a in agencies])
    }
}