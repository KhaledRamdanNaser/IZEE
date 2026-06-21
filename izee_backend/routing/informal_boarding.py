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
