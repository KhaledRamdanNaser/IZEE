# event_engine/builder.py

import uuid


def build_event(event, state):
    """
    Build full TransitEvent object
    """

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event["event_type"],

        "vehicle_id": state.get("vehicle_id"),
        "route_id": state.get("route_id"),

        "timestamp": state.get("timestamp"),

        "stop_id": event.get("stop_id"),

        "metrics": {},

        "confidence": state.get("confidence"),
        "source": state.get("source"),
        "simulation_flag": state.get("simulation_flag")
    }