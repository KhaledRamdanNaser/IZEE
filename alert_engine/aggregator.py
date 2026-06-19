from collections import defaultdict

from alert_engine.config import (
    ALERT_EXPIRY_DISRUPTION,
    DISRUPTION_THRESHOLD_HIGH,
    DISRUPTION_THRESHOLD_MEDIUM,
)


def check_route_disruptions(delay_alerts: list[dict]) -> list[dict]:
    route_vehicles = defaultdict(set)

    for alert in delay_alerts:
        if alert.get("severity") not in ("medium", "high"):
            continue

        route_id = alert.get("route_id")
        vehicle_id = alert.get("vehicle_id")
        if route_id and vehicle_id:
            route_vehicles[route_id].add(vehicle_id)

    disruption_alerts = []
    for route_id, vehicles in route_vehicles.items():
        count = len(vehicles)
        if count < DISRUPTION_THRESHOLD_MEDIUM:
            continue

        severity = "high" if count >= DISRUPTION_THRESHOLD_HIGH else "medium"
        disruption_alerts.append({
            "type": "disruption",
            "severity": severity,
            "message": (
                f"Service disruption on {route_id}. {count} vehicles "
                "experiencing severe delays."
            ),
            "route_id": route_id,
            "vehicle_id": None,
            "segment_id": None,
            "source_event_id": None,
            "lat": None,
            "lon": None,
            "expires_minutes": ALERT_EXPIRY_DISRUPTION,
        })

    return disruption_alerts
