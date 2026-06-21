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
