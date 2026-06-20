# event_engine/dwell_lifecycle.py

from datetime import datetime

from event_engine.dwell_tracker import (
    start_dwell,
    get_active_dwell,
    clear_dwell
)

from event_engine.traversal_tracker import (
    get_active_traversal,
    start_traversal,
    clear_traversal
)

from event_engine.builder import build_event


def process_dwell_lifecycle(
    events,
    current_state
):
    """
    Process:
    - dwell lifecycle
    - travel_time generation
    - segment completion
    """

    lifecycle_events = []

    vehicle_id = current_state.get("vehicle_id")

    for event in events:

        event_type = event.get("event_type")
        stop_id = event.get("stop_id")
        timestamp = event.get("timestamp")

        # -----------------------------------
        # ARRIVAL
        # -----------------------------------

        if event_type == "stop_arrival":

            # start dwell lifecycle
            start_dwell(
                vehicle_id,
                stop_id,
                timestamp
            )

            # check traversal completion
            stored = get_active_traversal(vehicle_id)

            if stored:

                try:

                    t1 = datetime.fromisoformat(
                        stored["departure_time"]
                    )

                    t2 = datetime.fromisoformat(
                        timestamp
                    )

                    travel_time = (
                        t2 - t1
                    ).total_seconds()

                    raw_segment_completed = {
                        "event_type": "segment_completed",

                        "from_stop_id": stored["from_stop_id"],
                        "to_stop_id": stop_id,

                        "segment_id": stored["segment_id"],

                        "metrics": {
                            "travel_time": travel_time
                        }
                    }

                    full_segment_completed = build_event(
                        raw_segment_completed,
                        current_state
                    )

                    lifecycle_events.append(
                        full_segment_completed
                    )

                except Exception:
                    pass

                # cleanup traversal lifecycle
                clear_traversal(vehicle_id)

        # -----------------------------------
        # DEPARTURE
        # -----------------------------------

        elif event_type == "stop_departure":

            start_traversal(
                vehicle_id,
                stop_id,
                timestamp,
                current_state.get("segment_id")
            )

            stored_dwell = get_active_dwell(
                vehicle_id
            )

            if (
                stored_dwell
                and stored_dwell.get("stop_id") == stop_id
            ):

                try:

                    t1 = datetime.fromisoformat(
                        stored_dwell["arrival_time"]
                    )

                    t2 = datetime.fromisoformat(
                        timestamp
                    )

                    dwell_time = (
                        t2 - t1
                    ).total_seconds()

                    raw_dwell_event = {
                        "event_type": "dwell_time",
                        "stop_id": stop_id,

                        "metrics": {
                            "dwell_time": dwell_time
                        }
                    }

                    full_dwell_event = build_event(
                        raw_dwell_event,
                        current_state
                    )

                    lifecycle_events.append(
                        full_dwell_event
                    )

                except Exception:
                    pass

            # cleanup dwell lifecycle
            clear_dwell(vehicle_id)

    return lifecycle_events