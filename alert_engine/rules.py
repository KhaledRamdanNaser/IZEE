from alert_engine.config import (
    ALERT_EXPIRY_DELAY,
    ALERT_EXPIRY_DWELL,
    DELAY_THRESHOLD_HIGH,
    DELAY_THRESHOLD_LOW,
    DELAY_THRESHOLD_MEDIUM,
    DWELL_THRESHOLD_HIGH,
    DWELL_THRESHOLD_MEDIUM,
)


def handle_segment_completed(event_row: dict, segment_stats_row: dict | None) -> dict | None:
    metrics = event_row.get("metrics") or {}
    travel_time = metrics.get("travel_time")
    if travel_time is None or segment_stats_row is None:
        return None

    avg_time = segment_stats_row.get("avg_travel_time")
    if avg_time is None or avg_time <= 0:
        return None

    ratio = float(travel_time) / float(avg_time)
    if ratio < DELAY_THRESHOLD_LOW:
        return None

    if ratio >= DELAY_THRESHOLD_HIGH:
        severity = "high"
    elif ratio >= DELAY_THRESHOLD_MEDIUM:
        severity = "medium"
    else:
        severity = "low"

    route_id = event_row.get("route_id") or "unknown"
    segment_id = event_row.get("segment_id") or "unknown"
    actual_min = round(float(travel_time) / 60, 1)
    expected_min = round(float(avg_time) / 60, 1)

    return {
        "type": "delay",
        "severity": severity,
        "message": (
            f"{route_id} vehicle delayed {actual_min} min on segment "
            f"{segment_id}. Expected {expected_min} min."
        ),
        "route_id": event_row.get("route_id"),
        "vehicle_id": event_row.get("vehicle_id"),
        "segment_id": event_row.get("segment_id"),
        "source_event_id": event_row.get("event_id"),
        "lat": event_row.get("lat"),
        "lon": event_row.get("lon"),
        "expires_minutes": ALERT_EXPIRY_DELAY,
    }


def handle_dwell_time(event_row: dict) -> dict | None:
    metrics = event_row.get("metrics") or {}
    dwell = metrics.get("dwell_time")
    if dwell is None or float(dwell) < DWELL_THRESHOLD_MEDIUM:
        return None

    severity = "high" if float(dwell) >= DWELL_THRESHOLD_HIGH else "medium"
    route_id = event_row.get("route_id") or "unknown"
    stop_id = event_row.get("stop_id") or "unknown"
    dwell_min = round(float(dwell) / 60, 1)

    return {
        "type": "dwell_issue",
        "severity": severity,
        "message": (
            f"{route_id} vehicle stationary at Stop {stop_id} for "
            f"{dwell_min} minutes. Possible breakdown."
        ),
        "route_id": event_row.get("route_id"),
        "vehicle_id": event_row.get("vehicle_id"),
        "segment_id": None,
        "source_event_id": event_row.get("event_id"),
        "lat": event_row.get("lat"),
        "lon": event_row.get("lon"),
        "expires_minutes": ALERT_EXPIRY_DWELL,
    }
