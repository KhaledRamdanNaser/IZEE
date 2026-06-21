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
