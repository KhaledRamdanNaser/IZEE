import uuid


def build_event(raw_event, current_state):
    """
    Standardize event into TransitEvent contract
    """

    return {
        "event_id": str(uuid.uuid4()),

        "event_type": raw_event.get("event_type"),

        "vehicle_id": current_state.get("vehicle_id"),
        "route_id": current_state.get("route_id"),
        "timestamp": current_state.get("timestamp"),

        # Optional fields (default None)
        "stop_id": raw_event.get("stop_id"),
        "from_stop_id": raw_event.get("from_stop_id"),
        "to_stop_id": raw_event.get("to_stop_id"),
        "segment_id": raw_event.get("segment_id"),
        "stop_sequence": current_state.get("stop_sequence"),

        # Metrics
        "metrics": raw_event.get("metrics", {}),

        # Confidence (allow override)
        "confidence": raw_event.get(
            "confidence_override",
            current_state.get("confidence", "medium")
        ),

        # Metadata
        "source": current_state.get("source"),
        "simulation_flag": current_state.get("simulation_flag")
    }