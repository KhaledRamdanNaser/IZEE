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

        # Validate route_id against known GTFS routes
        route_id = leg.get("route_id")
        if indexes is not None and "valid_route_ids" in indexes:
            if route_id is not None and route_id not in indexes["valid_route_ids"]:
                # Discard leg with invalid route_id (synthetic)
                continue
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
            "route_id": route_id,
            "trip_id": leg.get("trip_id"),
            "route_label": leg.get("route_label") or route_id,
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

    # If no valid legs remain, indicate that this alternative should be omitted
    if not legs:
        return None
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

    # Filter out any None routes (invalid alternatives)
    routes = [r for r in routes if r]
    # If no routes remain, return empty result with message
    if not routes:
        return {
            "request_id": request_id,
            "routes": [],
            "message": "No feasible route found",
            "timestamp": timestamp
        }
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
