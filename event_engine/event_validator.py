# event_engine/event_validator.py


def validate_event(event):
    """
    Final safety gate before event persistence.

    Returns:
        True  -> store event
        False -> discard invalid event
    """

    event_type = event.get("event_type")

    # only strict validation for completed segments
    if event_type == "segment_completed":

        segment_id = event.get("segment_id")

        if not segment_id:
            print("INVALID EVENT: missing segment_id")
            return False

        metrics = event.get("metrics", {})

        travel_time = metrics.get("travel_time")

        if travel_time is None:
            print("INVALID EVENT: missing travel_time")
            return False

        try:
            travel_time = float(travel_time)
        except Exception:
            print("INVALID EVENT: bad travel_time")
            return False

        if travel_time <= 0:
            print("INVALID EVENT: travel_time <= 0")
            return False

    return True