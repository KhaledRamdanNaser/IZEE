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

    # Compute set of valid route IDs for validation later
    valid_route_ids = set(routes["route_id"].astype(str)) if routes is not None else set()
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
        "trip_stop_index": trip_stop_index,
        "valid_route_ids": valid_route_ids
    }
