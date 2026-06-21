from routing.eta_provider import build_segment_id
from routing.fare_calculator import calculate_path_fare
from routing.journey_scorer import calculate_path_stats, score_path
from routing.nearest_stop_search import haversine_meters
from routing.postprocessing import simplify_legs
import time


INF = 10**18
WALKING_SPEED_MPS = 1.3
MAX_DIRECT_WALK_METERS = 1000
MAX_LABELS_PER_STOP = 6
MAX_BOARDING_LABELS_PER_ROUTE = 12
MAX_NEW_LABELS_PER_ROUND = 3000
ROUTE_MODE_PRIORITY = {
    "metro": 0,
    "subway": 0,
    "brt": 1,
    "lrt": 2,
    "tram": 2,
    "monorail": 3,
    "bus": 4,
    "minibus": 5,
    "microbus": 6,
}
METRO_TRACE_STOP_MARKERS = (
    "SHB_METRO",
    "SHO_METRO",
    "SAD_METRO",
    "MGR_METRO",
)
METRO_TRACE_STOP_NAMES = (
    "SADAT",
    "MAR GIRGIS",
    "AL-SHOHADAA",
    "SHUBRA EL-KHEIMA",
)
BRT_TRACE_STOP_IDS = (
    "BRT_KHOSOUS",
    "BRT_MARG",
    "BRT_BAHTEEM",
    "BRT_ADLY_MANSOUR",
    "BRT_NAZLET_QALYUB",
    "BRT_POLICE_ACADEMY",
)
TRUNK_BACKTRACK_GUARD_MODES = {
    "metro",
    "brt",
    "lrt",
    "monorail",
}
TRUNK_MODES = {"metro", "brt", "lrt", "monorail"}
SURFACE_MODES = {"bus", "microbus", "minibus"}
MAX_NON_TRUNK_TRANSFERS = 2
LEAST_WALKING_MAX_RECOMMENDED_RATIO = 2.0


def normalize_route_mode(mode):
    return str(mode or "unknown").strip().lower()


def route_scan_priority(route_id, route_modes):
    route_mode = normalize_route_mode(route_modes.get(route_id))
    return ROUTE_MODE_PRIORITY.get(route_mode, 99)


def route_scan_sort_key(route_id, route_modes, route_labels):
    route_mode = normalize_route_mode(route_modes.get(route_id))
    route_label = str(route_labels.get(route_id, route_id))

    return (
        route_scan_priority(route_id, route_modes),
        route_mode,
        route_label,
        str(route_id),
    )


def increment_count(mapping, key, amount=1):
    mapping[key] = mapping.get(key, 0) + amount


def canonical_stop_id_for_signature(stop_id):
    stop_id = str(stop_id)

    for suffix in ("_N2", "_S2", "_N", "_S", "_E", "_W"):
        if "_METRO" in stop_id and stop_id.endswith(suffix):
            return stop_id[:-len(suffix)]

    return stop_id


def label_mode_for_stats(label):
    for leg in reversed(label.get("path") or []):
        mode = normalize_route_mode(leg.get("mode"))

        if mode:
            return mode

    return "access"


def round_stats(label_stats, round_number):
    key = str(round_number)

    if key not in label_stats["rounds"]:
        label_stats["rounds"][key] = {
            "round_number": round_number,
            "labels_created": 0,
            "labels_accepted": 0,
            "labels_rejected_by_dominance": 0,
            "existing_labels_removed_by_dominance": 0,
            "dominance_checks": 0,
            "labels_created_by_mode": {},
            "labels_accepted_by_mode": {},
        }

    return label_stats["rounds"][key]


def get_eta_estimate(
    eta_estimates,
    route_id,
    direction_id,
    from_stop_id,
    to_stop_id
):
    segment_id = build_segment_id(
        route_id,
        direction_id,
        from_stop_id,
        to_stop_id
    )

    if not eta_estimates:
        return segment_id, None

    estimate = eta_estimates.get(segment_id)

    if estimate is not None:
        return segment_id, estimate

    fallback_segment_id = build_segment_id(
        route_id,
        None,
        from_stop_id,
        to_stop_id
    )

    estimate = eta_estimates.get(fallback_segment_id)

    if estimate is None:
        return segment_id, None

    return fallback_segment_id, estimate


def resolve_segment_travel_time(
    eta_estimates,
    route_id,
    direction_id,
    from_stop,
    to_stop
):
    scheduled_travel_time = max(
        0,
        int(to_stop["arrival_time"]) - int(from_stop["departure_time"])
    )
    segment_id, estimate = get_eta_estimate(
        eta_estimates,
        route_id,
        direction_id,
        from_stop["stop_id"],
        to_stop["stop_id"]
    )

    if not estimate:
        return scheduled_travel_time, {
            "segment_id": segment_id,
            "source": "gtfs_schedule",
            "scheduled_travel_time": scheduled_travel_time
        }

    if estimate.get("predicted_travel_time") is not None:
        travel_time = max(0, int(estimate["predicted_travel_time"]))
    else:
        predicted_delay = int(estimate.get("predicted_delay", 0))
        travel_time = max(0, scheduled_travel_time + predicted_delay)

    return travel_time, {
        "segment_id": segment_id,
        "source": "eta_engine",
        "scheduled_travel_time": scheduled_travel_time,
        "predicted_travel_time": travel_time,
        "predicted_delay": estimate.get("predicted_delay"),
        "confidence": estimate.get("confidence"),
        "timestamp": estimate.get("timestamp")
    }


def apply_walking_transfers(
    from_stops,
    arrival_times,
    paths,
    walking_transfers,
    new_marked_stops,
    round_number
):
    for from_stop_id in from_stops:
        if from_stop_id not in arrival_times:
            continue

        from_time = arrival_times[from_stop_id]
        from_path = paths.get(from_stop_id, [])

        for edge in walking_transfers.get(from_stop_id, []):
            to_stop_id = edge["to"]
            walking_time = edge["walking_time"]
            arrival_time = from_time + walking_time

            if arrival_time < arrival_times.get(to_stop_id, INF):
                arrival_times[to_stop_id] = arrival_time
                new_marked_stops.add(to_stop_id)

                leg = {
                    "from_stop_id": from_stop_id,
                    "to_stop_id": to_stop_id,
                    "route_id": None,
                    "trip_id": None,
                    "mode": "walk",
                    "departure_time": from_time,
                    "arrival_time": arrival_time,
                    "waiting_time": 0,
                    "distance_meters": edge.get("distance_meters"),
                    "walking_time": walking_time,
                    "route_label": None,
                    "round": round_number
                }
                paths[to_stop_id] = from_path + [leg]


def find_earliest_trip_on_route(
    route_id,
    trips_by_route,
    stop_times_by_trip,
    trip_stop_index,
    boarding_stop_id,
    earliest_board_time
):
    """
    Find the earliest trip on route_id that can be boarded at boarding_stop_id
    after earliest_board_time.
    """

    best_trip_id = None
    best_trip_times = None
    best_departure_time = INF
    best_board_index = None

    for trip_id in trips_by_route.get(route_id, []):
        idx = trip_stop_index.get(trip_id, {}).get(boarding_stop_id)

        if idx is None:
            continue

        trip_times = stop_times_by_trip.get(trip_id, [])

        if not trip_times:
            continue

        dep = trip_times[idx]["departure_time"]

        if dep >= earliest_board_time and dep < best_departure_time:
            best_trip_id = trip_id
            best_trip_times = trip_times
            best_departure_time = dep
            best_board_index = idx

    return best_trip_id, best_trip_times, best_departure_time, best_board_index


def find_earliest_trips_on_route_by_direction(
    route_id,
    trips_by_route,
    stop_times_by_trip,
    trip_stop_index,
    boarding_stop_id,
    earliest_board_time
):
    best_by_direction = {}

    for trip_id in trips_by_route.get(route_id, []):
        idx = trip_stop_index.get(trip_id, {}).get(boarding_stop_id)

        if idx is None:
            continue

        trip_times = stop_times_by_trip.get(trip_id, [])

        if not trip_times:
            continue

        dep = trip_times[idx]["departure_time"]

        if dep < earliest_board_time:
            continue

        direction_id = trip_times[idx].get("direction_id")
        direction_key = direction_id if direction_id is not None else trip_id
        existing = best_by_direction.get(direction_key)

        if existing is None or dep < existing[2]:
            best_by_direction[direction_key] = (
                trip_id,
                trip_times,
                dep,
                idx,
            )

    return sorted(best_by_direction.values(), key=lambda item: item[2])


def make_label(stop_id, arrival_time, path, departure_time_seconds):
    score = score_path(path, arrival_time - departure_time_seconds)

    return {
        "stop_id": str(stop_id),
        "arrival_time": arrival_time,
        "path": path,
        "score": score,
    }


def label_sequences(label):
    path = label.get("path", [])

    return {
        "mode_sequence": [
            leg.get("mode")
            for leg in path
        ],
        "route_sequence": [
            leg.get("route_label") or leg.get("route_id") or "walk"
            for leg in path
        ],
    }


def label_trace_summary(label, stop_details=None):
    stats = label["score"]["stats"]
    sequences = label_sequences(label)
    stop_id = str(label["stop_id"])
    stop = (stop_details or {}).get(stop_id, {})

    return {
        "stop_id": stop_id,
        "stop_name": stop.get("name"),
        "arrival_time": label["arrival_time"],
        "transfer_count": stats["transfer_count"],
        "total_cost": label["score"]["total_cost"],
        "walking_time": stats["walking_time"],
        "waiting_time": stats["waiting_time"],
        **sequences,
    }


def label_transit_modes(label):
    return [
        mode
        for mode in label_sequences(label)["mode_sequence"]
        if mode != "walk"
    ]


def is_metro_only_label(label):
    transit_modes = label_transit_modes(label)

    return bool(transit_modes) and all(
        mode == "metro"
        for mode in transit_modes
    )


def is_metro_candidate_label(label):
    return "metro" in label_transit_modes(label)


def is_trace_focus_stop(stop_id, stop_details, trace_mode="metro"):
    stop_id = str(stop_id)

    if trace_mode == "brt":
        return stop_id in BRT_TRACE_STOP_IDS or stop_id.startswith("BRT_")

    if trace_mode == "lrt":
        return stop_id.startswith("LRT_")

    if trace_mode == "monorail":
        return stop_id.startswith("MONORAIL_")

    if any(marker in stop_id.upper() for marker in METRO_TRACE_STOP_MARKERS):
        return True

    stop_name = str(
        (stop_details or {}).get(stop_id, {}).get("name", "")
    ).upper()

    return (
        any(marker == stop_name for marker in METRO_TRACE_STOP_NAMES)
        and (
            "METRO" in stop_id.upper()
            or "METRO" in stop_name
        )
    )


def should_trace_label(label, trace):
    if not trace:
        return False

    transit_modes = label_transit_modes(label)
    focus_stop = is_trace_focus_stop(
        label["stop_id"],
        trace.get("stop_details", {}),
        trace.get("mode", "metro"),
    )

    if trace.get("mode") == "brt":
        return focus_stop or "brt" in transit_modes

    if trace.get("mode") == "lrt":
        return focus_stop or "lrt" in transit_modes

    if trace.get("mode") == "monorail":
        return focus_stop or "monorail" in transit_modes

    return (
        focus_stop
        and (
            not transit_modes
            or "metro" in transit_modes
        )
    )


def create_trace_context(trace_mode, stop_details):
    if trace_mode not in {"metro", "brt", "lrt", "monorail"}:
        return None

    focus_stops = [
        {
            "stop_id": stop_id,
            "name": stop.get("name"),
        }
        for stop_id, stop in stop_details.items()
        if is_trace_focus_stop(stop_id, stop_details, trace_mode)
    ]

    return {
        "mode": trace_mode,
        "stop_details": stop_details,
        "focus_stops": focus_stops,
        "events": [],
        "summary": {},
        "console_event_count": 0,
        "console_event_limit": 250,
        "console_limit_reported": False,
    }


def print_trace_line(trace, message):
    if trace["console_event_count"] < trace["console_event_limit"]:
        print(message)
        trace["console_event_count"] += 1
    elif not trace["console_limit_reported"]:
        print(
            "[RAPTOR TRACE] console event limit reached; "
            "full trace is available in debug.raptor_trace.events"
        )
        trace["console_limit_reported"] = True


def trace_event(trace, event, label=None, round_number=None, **extra):
    if not trace:
        return

    if label is not None and not should_trace_label(label, trace):
        return

    payload = {
        "round_number": round_number,
        "event": event,
        **extra,
    }

    if label is not None:
        payload.update(label_trace_summary(
            label,
            trace.get("stop_details", {})
        ))

    trace["events"].append(payload)

    stop_id = payload.get("stop_id", "-")
    arrival_time = payload.get("arrival_time", "-")
    transfer_count = payload.get("transfer_count", "-")
    mode_sequence = " -> ".join(payload.get("mode_sequence", []) or [])
    route_sequence = " -> ".join(payload.get("route_sequence", []) or [])

    print_trace_line(
        trace,
        (
            "[RAPTOR TRACE] "
            f"round={round_number} event={event} stop={stop_id} "
            f"arrival={arrival_time} transfers={transfer_count} "
            f"modes={mode_sequence} routes={route_sequence}"
        )
    )


def dominance_diagnostic(candidate_label, existing_label):
    conditions = dominance_conditions(candidate_label, existing_label)

    return {
        "candidate": label_trace_summary(candidate_label),
        "existing": label_trace_summary(existing_label),
        "conditions": conditions,
        "dominated": all(conditions.values()),
    }


def dominance_conditions(candidate_label, existing_label):
    candidate_stats = candidate_label["score"]["stats"]
    existing_stats = existing_label["score"]["stats"]
    arrival_condition = (
        existing_label["arrival_time"] <= candidate_label["arrival_time"]
    )
    cost_condition = (
        existing_label["score"]["total_cost"]
        <= candidate_label["score"]["total_cost"]
    )
    transfer_condition = (
        existing_stats["transfer_count"]
        <= candidate_stats["transfer_count"]
    )
    walking_condition = (
        existing_stats["walking_time"]
        <= candidate_stats["walking_time"]
    )
    strict_better_condition = (
        existing_label["arrival_time"] < candidate_label["arrival_time"]
        or existing_label["score"]["total_cost"]
        < candidate_label["score"]["total_cost"]
        or existing_stats["transfer_count"]
        < candidate_stats["transfer_count"]
        or existing_stats["walking_time"]
        < candidate_stats["walking_time"]
    )

    return {
        "existing_arrival_time_lte_candidate": arrival_condition,
        "existing_total_cost_lte_candidate": cost_condition,
        "existing_transfer_count_lte_candidate": transfer_condition,
        "existing_walking_time_lte_candidate": walking_condition,
        "existing_strictly_better_in_at_least_one_metric": (
            strict_better_condition
        ),
    }


def label_is_dominated(candidate_label, existing_label):
    return all(dominance_conditions(candidate_label, existing_label).values())


def add_label(
    labels_by_stop,
    label,
    max_labels_per_stop=MAX_LABELS_PER_STOP,
    trace=None,
    round_number=None,
    source=None,
    label_stats=None
):
    stop_id = label["stop_id"]
    labels = labels_by_stop.setdefault(stop_id, [])
    stats = None
    label_mode = label_mode_for_stats(label)

    if label_stats is not None:
        stats = round_stats(label_stats, round_number)
        stats["labels_created"] += 1
        increment_count(stats["labels_created_by_mode"], label_mode)

    trace_event(
        trace,
        "created",
        label,
        round_number=round_number,
        source=source,
    )

    for existing_label in labels:
        if stats is not None:
            stats["dominance_checks"] += 1

        if trace:
            diagnostic = dominance_diagnostic(label, existing_label)
            dominated = diagnostic["dominated"]
        else:
            diagnostic = None
            dominated = label_is_dominated(label, existing_label)

        if dominated:
            if stats is not None:
                stats["labels_rejected_by_dominance"] += 1

            if trace:
                trace_event(
                    trace,
                    "rejected_by_dominance",
                    label,
                    round_number=round_number,
                    source=source,
                    dominance=diagnostic,
                )
            return False

    kept_labels = []

    for existing_label in labels:
        if stats is not None:
            stats["dominance_checks"] += 1

        if trace:
            diagnostic = dominance_diagnostic(existing_label, label)
            dominated = diagnostic["dominated"]
        else:
            diagnostic = None
            dominated = label_is_dominated(existing_label, label)

        if dominated:
            if stats is not None:
                stats["existing_labels_removed_by_dominance"] += 1

            if trace:
                trace_event(
                    trace,
                    "removed_existing_by_dominance",
                    existing_label,
                    round_number=round_number,
                    source=source,
                    dominance=diagnostic,
                )
            continue

        kept_labels.append(existing_label)

    labels[:] = kept_labels

    labels.append(label)
    trim_labels_for_stop(
        labels,
        max_labels_per_stop,
        trace=trace,
        round_number=round_number,
    )

    if label in labels:
        if stats is not None:
            stats["labels_accepted"] += 1
            increment_count(stats["labels_accepted_by_mode"], label_mode)

        trace_event(
            trace,
            "accepted",
            label,
            round_number=round_number,
            source=source,
        )

    return label in labels


def trim_labels_for_stop(
    labels,
    max_labels_per_stop,
    trace=None,
    round_number=None
):
    if len(labels) <= max_labels_per_stop:
        labels.sort(
            key=lambda item: (
                item["score"]["total_cost"],
                item["arrival_time"],
            )
        )
        return

    if len(labels) > max_labels_per_stop:
        trace_event(
            trace,
            "label_cap_exceeded_but_preserved",
            labels[0] if labels else None,
            round_number=round_number,
            reason="non_dominated_labels_preserved",
            max_labels_per_stop=max_labels_per_stop,
            label_count=len(labels),
        )

    labels.sort(
        key=lambda item: (
            item["score"]["total_cost"],
            item["arrival_time"],
        )
    )
    return

    keep = []

    def add_best(key_fn):
        if not labels:
            return

        best = min(labels, key=key_fn)

        if best not in keep:
            keep.append(best)

    add_best(lambda item: (
        item["score"]["total_cost"],
        item["arrival_time"],
    ))
    add_best(lambda item: (
        item["arrival_time"],
        item["score"]["total_cost"],
    ))
    add_best(lambda item: (
        item["score"]["stats"]["transfer_count"],
        item["arrival_time"],
        item["score"]["total_cost"],
    ))
    add_best(lambda item: (
        item["score"]["stats"]["walking_time"],
        item["score"]["total_cost"],
        item["arrival_time"],
    ))

    for item in sorted(
        labels,
        key=lambda label: (
            label["score"]["total_cost"],
            label["arrival_time"],
            label["score"]["stats"]["transfer_count"],
        )
    ):
        if item not in keep:
            keep.append(item)

        if len(keep) >= max_labels_per_stop:
            break

    removed_labels = [
        label
        for label in labels
        if label not in keep[:max_labels_per_stop]
    ]
    labels[:] = keep[:max_labels_per_stop]

    for label in removed_labels:
        trace_event(
            trace,
            "trimmed",
            label,
            round_number=round_number,
            reason="max_labels_per_stop",
            max_labels_per_stop=max_labels_per_stop,
        )

    labels.sort(
        key=lambda item: (
            item["score"]["total_cost"],
            item["arrival_time"],
        )
    )


def select_boarding_labels_for_route(
    labels,
    route_stop_index,
    trace=None,
    round_number=None,
    route_id=None,
    route_label=None,
    route_mode=None
):
    best_by_stop = {}

    for label in labels:
        stop_id = label["stop_id"]

        if stop_id not in route_stop_index:
            continue

        existing_label = best_by_stop.get(stop_id)

        if existing_label is None:
            best_by_stop[stop_id] = label
            continue

        if (
            label["score"]["total_cost"],
            label["arrival_time"],
        ) < (
            existing_label["score"]["total_cost"],
            existing_label["arrival_time"],
        ):
            best_by_stop[stop_id] = label

    boarding_labels = list(best_by_stop.values())
    boarding_labels.sort(
        key=lambda label: (
            label["score"]["total_cost"],
            label["arrival_time"],
            route_stop_index[label["stop_id"]],
        )
    )

    selected_labels = boarding_labels[:MAX_BOARDING_LABELS_PER_ROUTE]

    for label in selected_labels:
        trace_event(
            trace,
            "boarding_candidate",
            label,
            round_number=round_number,
            route_id=route_id,
            route_label=route_label,
            route_mode=route_mode,
            route_stop_index=route_stop_index.get(label["stop_id"]),
        )

    for label in boarding_labels[MAX_BOARDING_LABELS_PER_ROUTE:]:
        trace_event(
            trace,
            "boarding_candidate_not_selected",
            label,
            round_number=round_number,
            route_id=route_id,
            route_label=route_label,
            route_mode=route_mode,
            reason="max_boarding_labels_per_route",
            max_boarding_labels_per_route=MAX_BOARDING_LABELS_PER_ROUTE,
        )

    return selected_labels


def apply_walking_transfers_to_labels(
    labels,
    labels_by_stop,
    walking_transfers,
    departure_time_seconds,
    round_number,
    trace=None,
    label_stats=None
):
    new_labels = []

    for label in labels:
        from_stop_id = label["stop_id"]

        for edge in walking_transfers.get(from_stop_id, []):
            to_stop_id = str(edge["to"])
            walking_time = int(edge["walking_time"])
            arrival_time = label["arrival_time"] + walking_time
            leg = {
                "from_stop_id": from_stop_id,
                "to_stop_id": to_stop_id,
                "route_id": None,
                "trip_id": None,
                "mode": "walk",
                "departure_time": label["arrival_time"],
                "arrival_time": arrival_time,
                "waiting_time": 0,
                "distance_meters": edge.get("distance_meters"),
                "walking_time": walking_time,
                "walk_type": edge.get("walk_type"),
                "source": edge.get("source"),
                "confidence": edge.get("confidence"),
                "route_label": None,
                "round": round_number
            }
            new_label = make_label(
                to_stop_id,
                arrival_time,
                label["path"] + [leg],
                departure_time_seconds
            )

            if add_label(
                labels_by_stop,
                new_label,
                trace=trace,
                round_number=round_number,
                source="walking_transfer",
                label_stats=label_stats,
            ):
                new_labels.append(new_label)

    return new_labels


def route_signature(path):
    return tuple(
        (
            leg.get("mode"),
            leg.get("route_id"),
            canonical_stop_id_for_signature(leg.get("from_stop_id")),
            canonical_stop_id_for_signature(leg.get("to_stop_id")),
        )
        for leg in path
    )


def transit_legs(path):
    return [
        leg
        for leg in path
        if normalize_route_mode(leg.get("mode")) != "walk"
    ]


def has_same_route_direction_backtracking(path):
    for previous_leg, current_leg in zip(transit_legs(path), transit_legs(path)[1:]):
        previous_mode = normalize_route_mode(previous_leg.get("mode"))
        current_mode = normalize_route_mode(current_leg.get("mode"))

        if previous_mode != current_mode:
            continue

        if previous_mode not in TRUNK_BACKTRACK_GUARD_MODES:
            continue

        if previous_leg.get("route_id") != current_leg.get("route_id"):
            continue

        if previous_leg.get("to_stop_id") != current_leg.get("from_stop_id"):
            continue

        previous_direction = previous_leg.get("direction_id")
        current_direction = current_leg.get("direction_id")
        direction_changed = (
            previous_direction is not None
            and current_direction is not None
            and previous_direction != current_direction
        )
        trip_changed = (
            previous_leg.get("trip_id") is not None
            and current_leg.get("trip_id") is not None
            and previous_leg.get("trip_id") != current_leg.get("trip_id")
        )

        if direction_changed or trip_changed:
            return True

    return False


def route_diagnostic_summary(route):
    legs = route.get("legs", [])
    stats = route.get("score", {}).get("stats") or calculate_path_stats(legs)
    quality = route_quality_metrics(route)

    return {
        "transfer_count": stats["transfer_count"],
        "total_travel_time": route.get("total_travel_time"),
        "total_walking_time": stats["walking_time"],
        "waiting_time": stats["waiting_time"],
        "generalized_cost": route.get("generalized_cost"),
        "route_sequence": [
            leg.get("route_label") or leg.get("route_id") or "walk"
            for leg in legs
        ],
        "modes_sequence": [
            leg.get("mode")
            for leg in legs
        ],
        "signature": route_signature(legs),
        "same_route_backtracking": has_same_route_direction_backtracking(legs),
        **quality,
        "rejected_by_quality_filter": route.get("rejected_by_quality_filter"),
    }


def transit_modes_for_route(route):
    return [
        normalize_route_mode(leg.get("mode"))
        for leg in route.get("legs", [])
        if normalize_route_mode(leg.get("mode")) != "walk"
    ]


def route_uses_brt_feeder_transfer(route):
    return any(
        leg.get("walk_type") == "brt_feeder_transfer"
        or leg.get("source") == "generated_brt_feeder"
        for leg in route.get("legs", [])
    )


def max_consecutive_surface_transit_legs(route):
    longest = 0
    current = 0

    for mode in transit_modes_for_route(route):
        if mode in SURFACE_MODES:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return longest


def surface_chain_count(route):
    longest = max_consecutive_surface_transit_legs(route)
    return max(0, longest - 1)


def has_brt_after_feeder_transfer(route):
    feeder_seen = False

    for leg in route.get("legs", []):
        mode = normalize_route_mode(leg.get("mode"))
        if (
            leg.get("walk_type") == "brt_feeder_transfer"
            or leg.get("source") == "generated_brt_feeder"
        ):
            feeder_seen = True
            continue

        if feeder_seen and mode == "brt":
            return True

    return False


def route_quality_metrics(route):
    modes = transit_modes_for_route(route)
    has_trunk = any(mode in TRUNK_MODES for mode in modes)
    has_brt = "brt" in modes
    used_brt_feeder = route_uses_brt_feeder_transfer(route)

    return {
        "has_trunk_mode": has_trunk,
        "has_brt": has_brt,
        "used_brt_feeder_transfer": used_brt_feeder,
        "surface_chain_count": surface_chain_count(route),
    }


def route_quality_rejection_reason(route):
    stats = route.get("score", {}).get("stats") or calculate_path_stats(
        route.get("legs", [])
    )
    quality = route_quality_metrics(route)

    if (
        quality["used_brt_feeder_transfer"]
        and not quality["has_brt"]
        and not has_brt_after_feeder_transfer(route)
    ):
        return "used_brt_feeder_transfer_without_boarding_brt"

    if (
        not quality["has_trunk_mode"]
        and stats["transfer_count"] > MAX_NON_TRUNK_TRANSFERS
    ):
        return "non_trunk_route_exceeds_transfer_cap"

    if not quality["has_trunk_mode"] and quality["surface_chain_count"] >= 2:
        return "surface_only_chain_without_trunk"

    return None


def route_quality_penalty(route):
    quality = route_quality_metrics(route)
    stats = route.get("score", {}).get("stats") or calculate_path_stats(
        route.get("legs", [])
    )
    penalty = 0

    if quality["surface_chain_count"]:
        penalty += quality["surface_chain_count"] * 900

    if not quality["has_trunk_mode"] and quality["surface_chain_count"]:
        penalty += 1800

    if not quality["has_trunk_mode"] and stats["transfer_count"] > 1:
        penalty += stats["transfer_count"] * 700

    if quality["used_brt_feeder_transfer"] and not quality["has_brt"]:
        penalty += 5000

    return penalty


def infer_metro_trace_reason(
    trace,
    metro_only_candidates,
    destination_candidates,
    stop_details
):
    if metro_only_candidates:
        return "metro_only_candidate_reached_destination"

    events = trace.get("events", [])
    metro_accepted = [
        event
        for event in events
        if event.get("event") == "accepted"
        and "metro" in (event.get("mode_sequence") or [])
    ]
    metro_rejected = [
        event
        for event in events
        if event.get("event") in (
            "rejected_by_dominance",
            "trimmed",
            "boarding_candidate_not_selected",
        )
        and "metro" in (event.get("mode_sequence") or [])
    ]
    destination_metro_candidates = [
        candidate
        for candidate in destination_candidates
        if is_trace_focus_stop(candidate["stop_id"], stop_details)
    ]

    if metro_rejected:
        last_event = metro_rejected[-1]
        return (
            "metro_label_discarded_by_"
            f"{last_event.get('event')}"
        )

    if metro_accepted and not destination_metro_candidates:
        return "destination_metro_stop_not_present_in_egress_candidates"

    if metro_accepted:
        return (
            "metro_labels_exist_but_no_metro_only_label_reached_a_destination"
        )

    return "no_metro_label_generated_or_boarded"


def build_candidate_result(
    origin_stop_id,
    destination_stop_id,
    departure_time_seconds,
    arrival_time,
    path,
    score
):
    fare = calculate_path_fare(path or [])

    return {
        "found": True,
        "origin_stop_id": origin_stop_id,
        "destination_stop_id": str(destination_stop_id),
        "departure_time": departure_time_seconds,
        "arrival_time": arrival_time,
        "total_travel_time": arrival_time - departure_time_seconds,
        "generalized_cost": score["total_cost"],
        "total_fare": fare["total_fare"],
        "fare_currency": fare["currency"],
        "fare_breakdown": fare["leg_fares"],
        "score": score,
        "legs": path or []
    }


def is_walk_only_route(route):
    legs = route.get("legs", [])

    return (
        len(legs) == 1
        and legs[0].get("mode") == "walk"
        and legs[0].get("from_stop_id") == "origin"
        and legs[0].get("to_stop_id") == "destination"
    )


def classify_route_type(route):
    if is_walk_only_route(route):
        return "walk_only"

    return "transit"


def infer_origin_stop_id(path, fallback_stop_id=None):
    if not path:
        return fallback_stop_id

    first_leg = path[0]

    if first_leg.get("from_stop_id") == "origin":
        return first_leg.get("to_stop_id", fallback_stop_id)

    return first_leg.get("from_stop_id", fallback_stop_id)


def select_route_alternatives(candidates, limit=4):
    unique_candidates = {}

    for candidate in candidates:
        signature = route_signature(candidate["legs"])

        if signature not in unique_candidates:
            unique_candidates[signature] = candidate
            continue

        if candidate["generalized_cost"] < unique_candidates[signature]["generalized_cost"]:
            unique_candidates[signature] = candidate

    candidates = list(unique_candidates.values())

    if not candidates:
        return []

    for candidate in candidates:
        candidate["route_type"] = classify_route_type(candidate)
        candidate["quality"] = route_quality_metrics(candidate)
        candidate["quality_penalty"] = route_quality_penalty(candidate)
        candidate["selection_cost"] = (
            candidate["generalized_cost"] + candidate["quality_penalty"]
        )

    walk_only_routes = [
        route
        for route in candidates
        if route["route_type"] == "walk_only"
    ]
    transit_routes = [
        route
        for route in candidates
        if route["route_type"] != "walk_only"
    ]
    recommended_baseline = min(
        transit_routes,
        key=lambda route: (
            route["selection_cost"],
            route["total_travel_time"],
        ),
        default=None,
    )
    recommended_time = (
        recommended_baseline["total_travel_time"]
        if recommended_baseline is not None
        else None
    )

    def transfer_count(route):
        stats = route.get("score", {}).get("stats")

        if stats is not None:
            return stats["transfer_count"]

        return calculate_path_stats(route["legs"])["transfer_count"]

    def passes_least_walking_guard(route):
        quality = route.get("quality") or route_quality_metrics(route)

        if (
            not quality["has_trunk_mode"]
            and transfer_count(route) > MAX_NON_TRUNK_TRANSFERS
        ):
            return False

        if not quality["has_trunk_mode"] and quality["surface_chain_count"] >= 2:
            return False

        if (
            recommended_time
            and route["total_travel_time"]
            > recommended_time * LEAST_WALKING_MAX_RECOMMENDED_RATIO
        ):
            return False

        return True

    least_walking_routes = [
        route
        for route in candidates
        if passes_least_walking_guard(route)
    ]
    brt_lrt_routes = [
        route
        for route in transit_routes
        if route.get("quality", {}).get("has_brt")
        and any(leg.get("mode") == "lrt" for leg in route.get("legs", []))
    ]

    profiles = [
        (
            "Recommended route",
            "recommended",
            transit_routes,
            lambda route: (
                route["selection_cost"],
                route["total_travel_time"],
            )
        ),
        (
            "Fastest transit",
            "fastest transit",
            transit_routes,
            lambda route: (
                route["total_travel_time"],
                route["generalized_cost"],
            )
        ),
        (
            "Fewest transfers",
            "fewest transfers",
            transit_routes,
            lambda route: (
                transfer_count(route),
                route["score"]["breakdown"].get("mode_switch_penalty", 0),
                route["total_travel_time"],
                route["selection_cost"],
            )
        ),
        (
            "BRT + LRT connection",
            "brt + lrt",
            brt_lrt_routes,
            lambda route: (
                route["selection_cost"],
                route["total_travel_time"],
            )
        ),
        (
            "Least walking",
            "least walking",
            least_walking_routes,
            lambda route: (
                route["score"]["stats"]["walking_time"],
                route["selection_cost"],
                route["total_travel_time"],
            )
        ),
    ]

    selected = []
    selected_by_signature = {}
    selected_signatures = set()

    for label, badge, route_pool, key_fn in profiles:
        if not route_pool:
            continue

        best_candidate = sorted(route_pool, key=key_fn)[0]
        signature = route_signature(best_candidate["legs"])

        if signature in selected_signatures:
            existing = selected_by_signature[signature]

            if badge not in existing["badges"]:
                existing["badges"].append(badge)

            continue

        alternative = dict(best_candidate)
        alternative["alternative_label"] = label
        alternative["badges"] = [badge]
        selected.append(alternative)
        selected_by_signature[signature] = alternative
        selected_signatures.add(signature)

        if len(selected) >= limit:
            break

    if walk_only_routes:
        walk_only_route = min(
            walk_only_routes,
            key=lambda route: (
                route["total_travel_time"],
                route["generalized_cost"],
            )
        )
        signature = route_signature(walk_only_route["legs"])

        if signature in selected_by_signature:
            existing = selected_by_signature[signature]

            if "walk only" not in existing["badges"]:
                existing["badges"].append("walk only")

            return selected

        alternative = dict(walk_only_route)
        alternative["alternative_label"] = "Walk only"
        alternative["badges"] = ["walk only"]
        selected.append(alternative)

    return selected


def simple_raptor(
    indexes,
    departure_time_seconds,
    max_transfers=2,
    walking_transfers=None,
    origin_candidates=None,
    destination_candidates=None,
    final_origin=None,
    final_destination=None,
    origin_stop_id=None,
    destination_stop_id=None,
    eta_estimates=None,
    trace_mode=None,
    collect_diagnostics=True
):
    diagnostics = {
        "stage_timings_seconds": {},
        "round_cap_analysis": {
            "rounds": [],
        },
        "label_stats": {
            "rounds": {},
        },
    }
    stage_start = time.perf_counter()
    routes_by_stop = indexes["routes_by_stop"]
    stops_by_route = indexes["stops_by_route"]
    trips_by_route = indexes["trips_by_route"]
    stop_times_by_trip = indexes["stop_times_by_trip"]
    trip_stop_index = indexes["trip_stop_index"]
    stop_index_by_route = indexes["stop_index_by_route"]
    route_modes = indexes.get("route_modes", {})
    route_labels = indexes.get("route_labels", {})
    stop_details = indexes.get("stop_details", {})
    trace = create_trace_context(trace_mode, stop_details)
    label_stats = diagnostics["label_stats"] if collect_diagnostics else None
    if walking_transfers is None:
        walking_transfers = {}
    if eta_estimates is None:
        eta_estimates = {}
    diagnostics["stage_timings_seconds"]["setup"] = round(
        time.perf_counter() - stage_start,
        4
    )

    stage_start = time.perf_counter()
    rounds = max_transfers + 1
    labels_by_stop = {}

    if origin_candidates is None:
        if origin_stop_id is None:
            raise ValueError("origin_stop_id is required when origin_candidates is not provided")

        origin_candidates = [{
            "stop_id": origin_stop_id,
            "walking_time": 0,
            "distance_meters": 0,
            "stop": None
        }]

    if destination_candidates is None:
        if destination_stop_id is None:
            raise ValueError("destination_stop_id is required when destination_candidates is not provided")

        destination_candidates = [{
            "stop_id": destination_stop_id,
            "walking_time": 0,
            "distance_meters": 0,
            "stop": None
        }]

    marked_labels = []

    for candidate in origin_candidates:
        stop_id = str(candidate["stop_id"])
        walking_time = int(candidate.get("walking_time", 0))
        arrival_time = departure_time_seconds + walking_time

        if walking_time > 0 and final_origin is not None:
            initial_path = [{
                "from_stop_id": "origin",
                "to_stop_id": stop_id,
                "from_stop": {
                    "stop_id": "origin",
                    "name": "Origin",
                    "lat": final_origin["lat"],
                    "lon": final_origin["lon"]
                },
                "to_stop": candidate.get("stop"),
                "route_id": None,
                "trip_id": None,
                "mode": "walk",
                "departure_time": departure_time_seconds,
                "arrival_time": arrival_time,
                "waiting_time": 0,
                "distance_meters": candidate.get("distance_meters"),
                "walking_time": walking_time,
                "route_label": None,
                "round": 0
            }]
        else:
            initial_path = []

        label = make_label(
            stop_id,
            arrival_time,
            initial_path,
            departure_time_seconds
        )

        if add_label(
            labels_by_stop,
            label,
            trace=trace,
            round_number=0,
            source="origin_access",
            label_stats=label_stats,
        ):
            marked_labels.append(label)

    marked_labels.extend(apply_walking_transfers_to_labels(
        labels=marked_labels,
        labels_by_stop=labels_by_stop,
        walking_transfers=walking_transfers,
        departure_time_seconds=departure_time_seconds,
        round_number=0,
        trace=trace,
        label_stats=label_stats,
    ))
    diagnostics["stage_timings_seconds"]["initial_access_labels"] = round(
        time.perf_counter() - stage_start,
        4
    )

    stage_start = time.perf_counter()
    for round_number in range(rounds):
        if not marked_labels:
            break

        new_marked_labels = []
        routes_to_scan = set()
        round_marked_labels = list(marked_labels)

        # Find routes serving currently reachable stops.
        for label in round_marked_labels:
            for route_id in routes_by_stop.get(label["stop_id"], []):
                routes_to_scan.add(route_id)

        sorted_routes_to_scan = sorted(
            routes_to_scan,
            key=lambda route_id: route_scan_sort_key(
                route_id,
                route_modes,
                route_labels,
            )
        )
        round_cap_reached = False
        round_analysis = {
            "round_number": round_number,
            "total_candidate_routes": len(sorted_routes_to_scan),
            "total_routes_scanned": 0,
            "routes_skipped_due_cap": 0,
            "metro_routes_scanned": 0,
            "metro_routes_skipped": 0,
            "labels_generated_by_mode": {},
            "routes_scanned_by_mode": {},
            "routes_skipped_by_mode": {},
            "route_scan_order": [],
            "cap_reached": False,
            "cap_route": None,
            "max_new_labels_per_round": MAX_NEW_LABELS_PER_ROUND,
        } if collect_diagnostics else None

        # Scan each route.
        for route_index, route_id in enumerate(sorted_routes_to_scan):
            route_stop_index = stop_index_by_route.get(route_id, {})
            route_label = route_labels.get(route_id, route_id)
            route_mode = normalize_route_mode(route_modes.get(route_id, "unknown"))
            route_priority = route_scan_priority(route_id, route_modes)
            route_generated_labels = 0
            if round_analysis is not None:
                round_analysis["total_routes_scanned"] += 1
                increment_count(round_analysis["routes_scanned_by_mode"], route_mode)

            if round_analysis is not None and route_mode == "metro":
                round_analysis["metro_routes_scanned"] += 1

            if round_analysis is not None:
                round_analysis["route_scan_order"].append({
                    "scan_order": route_index + 1,
                    "route_id": route_id,
                    "route_label": route_label,
                    "route_mode": route_mode,
                    "scan_priority": route_priority,
                })

            reachable_boarding_labels = select_boarding_labels_for_route(
                round_marked_labels,
                route_stop_index,
                trace=trace,
                round_number=round_number,
                route_id=route_id,
                route_label=route_label,
                route_mode=route_mode,
            )

            if trace and (
                route_mode == trace.get("mode")
                or (
                    trace.get("mode") == "metro"
                    and route_label in ("M1", "M2", "M3")
                )
            ):
                trace["events"].append({
                    "round_number": round_number,
                    "event": "route_scanned",
                    "route_id": route_id,
                    "route_label": route_label,
                    "route_mode": route_mode,
                    "scan_priority": route_priority,
                    "scan_order": route_index + 1,
                    "boarding_label_count": len(reachable_boarding_labels),
                })
                print_trace_line(
                    trace,
                    (
                        "[RAPTOR TRACE] "
                        f"round={round_number} event=route_scanned "
                        f"order={route_index + 1} priority={route_priority} "
                        f"route={route_label} mode={route_mode} "
                        f"boarding_labels={len(reachable_boarding_labels)}"
                    )
                )

            # Find reachable boarding stops on this route.
            for boarding_label in reachable_boarding_labels:
                boarding_stop_id = boarding_label["stop_id"]
                earliest_board_time = boarding_label["arrival_time"]

                trip_options = find_earliest_trips_on_route_by_direction(
                    route_id=route_id,
                    trips_by_route=trips_by_route,
                    stop_times_by_trip=stop_times_by_trip,
                    trip_stop_index=trip_stop_index,
                    boarding_stop_id=boarding_stop_id,
                    earliest_board_time=earliest_board_time
                )

                if not trip_options:
                    continue

                for trip_id, trip_times, departure_time, board_index in trip_options:
                    adjusted_time_at_previous_stop = departure_time
                    eta_segments = []
                    previous_stop = trip_times[board_index]

                    for st in trip_times[board_index + 1:]:
                        stop_id = st["stop_id"]
                        segment_travel_time, eta_segment = resolve_segment_travel_time(
                            eta_estimates=eta_estimates,
                            route_id=route_id,
                            direction_id=previous_stop.get("direction_id"),
                            from_stop=previous_stop,
                            to_stop=st
                        )
                        if eta_segment["source"] == "eta_engine":
                            eta_segments = eta_segments + [eta_segment]
                        arrival_time = adjusted_time_at_previous_stop + segment_travel_time

                        leg = {
                            "from_stop_id": boarding_stop_id,
                            "to_stop_id": stop_id,
                            "route_id": route_id,
                            "trip_id": trip_id,
                            "mode": route_modes.get(route_id, "unknown"),
                            "route_label": route_labels.get(route_id, route_id),
                            "departure_time": departure_time,
                            "arrival_time": arrival_time,
                            "waiting_time": departure_time - earliest_board_time,
                            "eta_adjusted": bool(eta_segments),
                            "eta_segments": eta_segments,
                            "round": round_number,
                            "direction_id": previous_stop.get("direction_id"),
                        }
                        new_label = make_label(
                            stop_id,
                            arrival_time,
                            boarding_label["path"] + [leg],
                            departure_time_seconds
                        )

                        if add_label(
                            labels_by_stop,
                            new_label,
                            trace=trace,
                            round_number=round_number,
                            source="route_scan",
                            label_stats=label_stats,
                        ):
                            new_marked_labels.append(new_label)
                            route_generated_labels += 1
                            if round_analysis is not None:
                                increment_count(
                                    round_analysis["labels_generated_by_mode"],
                                    route_mode,
                                )

                            if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                                round_cap_reached = True
                                break

                        dwell_time = max(
                            0,
                            int(st["departure_time"]) - int(st["arrival_time"])
                        )
                        adjusted_time_at_previous_stop = arrival_time + dwell_time
                        previous_stop = st

                    if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                        round_cap_reached = True
                        break

                if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                    round_cap_reached = True
                    break

            if len(new_marked_labels) >= MAX_NEW_LABELS_PER_ROUND:
                round_cap_reached = True
                if round_analysis is not None and route_generated_labels:
                    route_order_entry = round_analysis["route_scan_order"][-1]
                    route_order_entry["generated_labels"] = route_generated_labels

                skipped_routes = sorted_routes_to_scan[route_index + 1:]
                if round_analysis is not None:
                    round_analysis["cap_reached"] = True
                    round_analysis["cap_route"] = {
                        "route_id": route_id,
                        "route_label": route_label,
                        "route_mode": route_mode,
                        "scan_order": route_index + 1,
                        "scan_priority": route_priority,
                        "new_label_count": len(new_marked_labels),
                    }
                    round_analysis["routes_skipped_due_cap"] = len(skipped_routes)

                    for skipped_route_id in skipped_routes:
                        skipped_route_mode = normalize_route_mode(
                            route_modes.get(skipped_route_id, "unknown")
                        )
                        increment_count(
                            round_analysis["routes_skipped_by_mode"],
                            skipped_route_mode,
                        )

                        if skipped_route_mode == "metro":
                            round_analysis["metro_routes_skipped"] += 1

                if trace:
                    trace["events"].append({
                        "round_number": round_number,
                        "event": "round_cap_reached",
                        "route_id": route_id,
                        "route_label": route_label,
                        "route_mode": route_mode,
                        "scan_priority": route_priority,
                        "scan_order": route_index + 1,
                        "new_label_count": len(new_marked_labels),
                        "max_new_labels_per_round": MAX_NEW_LABELS_PER_ROUND,
                    })

                    for skipped_route_id in skipped_routes:
                        skipped_scan_order = (
                            sorted_routes_to_scan.index(skipped_route_id) + 1
                        )
                        skipped_route_label = route_labels.get(
                            skipped_route_id,
                            skipped_route_id,
                        )
                        skipped_route_mode = normalize_route_mode(
                            route_modes.get(skipped_route_id, "unknown")
                        )
                        skipped_route_priority = route_scan_priority(
                            skipped_route_id,
                            route_modes,
                        )

                        if (
                            skipped_route_mode == trace.get("mode")
                            or (
                                trace.get("mode") == "metro"
                                and skipped_route_label in ("M1", "M2", "M3")
                            )
                        ):
                            trace["events"].append({
                                "round_number": round_number,
                                "event": "route_skipped_due_round_cap",
                                "route_id": skipped_route_id,
                                "route_label": skipped_route_label,
                                "route_mode": skipped_route_mode,
                                "scan_priority": skipped_route_priority,
                                "scan_order": skipped_scan_order,
                                "new_label_count": len(new_marked_labels),
                                "max_new_labels_per_round": MAX_NEW_LABELS_PER_ROUND,
                            })
                break

            if round_analysis is not None and route_generated_labels:
                route_order_entry = round_analysis["route_scan_order"][-1]
                route_order_entry["generated_labels"] = route_generated_labels

        if round_analysis is not None:
            diagnostics["round_cap_analysis"]["rounds"].append(round_analysis)

        new_marked_labels.extend(apply_walking_transfers_to_labels(
            labels=new_marked_labels,
            labels_by_stop=labels_by_stop,
            walking_transfers=walking_transfers,
            departure_time_seconds=departure_time_seconds,
            round_number=round_number,
            trace=trace,
            label_stats=label_stats,
        ))
        marked_labels = new_marked_labels
        if label_stats is not None:
            surviving_labels = sum(
                len(stop_labels)
                for stop_labels in labels_by_stop.values()
            )
            round_stats(
                label_stats,
                round_number,
            )["labels_surviving"] = surviving_labels
    round_cap_rounds = diagnostics["round_cap_analysis"]["rounds"]
    round_cap_summary = {
        "total_routes_scanned": 0,
        "routes_skipped_due_cap": 0,
        "metro_routes_scanned": 0,
        "metro_routes_skipped": 0,
        "labels_generated_by_mode": {},
        "routes_scanned_by_mode": {},
        "routes_skipped_by_mode": {},
    }

    for round_analysis in round_cap_rounds:
        round_cap_summary["total_routes_scanned"] += round_analysis[
            "total_routes_scanned"
        ]
        round_cap_summary["routes_skipped_due_cap"] += round_analysis[
            "routes_skipped_due_cap"
        ]
        round_cap_summary["metro_routes_scanned"] += round_analysis[
            "metro_routes_scanned"
        ]
        round_cap_summary["metro_routes_skipped"] += round_analysis[
            "metro_routes_skipped"
        ]

        for mode, count in round_analysis["labels_generated_by_mode"].items():
            increment_count(
                round_cap_summary["labels_generated_by_mode"],
                mode,
                count,
            )

        for mode, count in round_analysis["routes_scanned_by_mode"].items():
            increment_count(
                round_cap_summary["routes_scanned_by_mode"],
                mode,
                count,
            )

        for mode, count in round_analysis["routes_skipped_by_mode"].items():
            increment_count(
                round_cap_summary["routes_skipped_by_mode"],
                mode,
                count,
            )

    diagnostics["round_cap_analysis"]["summary"] = round_cap_summary
    label_rounds = sorted(
        diagnostics["label_stats"]["rounds"].values(),
        key=lambda item: (
            item["round_number"] is None,
            item["round_number"] if item["round_number"] is not None else -1,
        )
    )
    diagnostics["label_stats"]["rounds"] = label_rounds
    diagnostics["label_stats"]["summary"] = {
        "labels_created": sum(
            item["labels_created"]
            for item in label_rounds
        ),
        "labels_accepted": sum(
            item["labels_accepted"]
            for item in label_rounds
        ),
        "labels_rejected_by_dominance": sum(
            item["labels_rejected_by_dominance"]
            for item in label_rounds
        ),
        "existing_labels_removed_by_dominance": sum(
            item["existing_labels_removed_by_dominance"]
            for item in label_rounds
        ),
        "dominance_checks": sum(
            item["dominance_checks"]
            for item in label_rounds
        ),
    }
    diagnostics["stage_timings_seconds"]["raptor_rounds"] = round(
        time.perf_counter() - stage_start,
        4
    )

    stage_start = time.perf_counter()
    candidate_results = []

    if final_origin is not None and final_destination is not None:
        direct_distance = haversine_meters(
            final_origin["lat"],
            final_origin["lon"],
            final_destination["lat"],
            final_destination["lon"]
        )

        if direct_distance <= MAX_DIRECT_WALK_METERS:
            direct_walking_time = int(direct_distance / WALKING_SPEED_MPS)
            direct_path = [{
                "from_stop_id": "origin",
                "to_stop_id": "destination",
                "from_stop": {
                    "stop_id": "origin",
                    "name": "Origin",
                    "lat": final_origin["lat"],
                    "lon": final_origin["lon"]
                },
                "to_stop": {
                    "stop_id": "destination",
                    "name": "Destination",
                    "lat": final_destination["lat"],
                    "lon": final_destination["lon"]
                },
                "route_id": None,
                "trip_id": None,
                "mode": "walk",
                "departure_time": departure_time_seconds,
                "arrival_time": departure_time_seconds + direct_walking_time,
                "waiting_time": 0,
                "distance_meters": round(direct_distance, 2),
                "walking_time": direct_walking_time,
                "route_label": None,
                "round": None
            }]
            direct_score = score_path(
                direct_path,
                direct_walking_time,
                final_walking_time=direct_walking_time
            )

            candidate_results.append(build_candidate_result(
                origin_stop_id=infer_origin_stop_id(direct_path, origin_stop_id),
                destination_stop_id="destination",
                departure_time_seconds=departure_time_seconds,
                arrival_time=departure_time_seconds + direct_walking_time,
                path=direct_path,
                score=direct_score
            ))

    for candidate in destination_candidates:
        stop_id = str(candidate["stop_id"])

        if stop_id not in labels_by_stop:
            continue

        egress_walking_time = int(candidate.get("walking_time", 0))

        for destination_label in labels_by_stop[stop_id]:
            final_arrival_time = destination_label["arrival_time"] + egress_walking_time
            candidate_path = list(destination_label["path"])

            if egress_walking_time > 0 and final_destination is not None:
                candidate_path.append({
                    "from_stop_id": stop_id,
                    "to_stop_id": "destination",
                    "from_stop": candidate.get("stop"),
                    "to_stop": {
                        "stop_id": "destination",
                        "name": "Destination",
                        "lat": final_destination["lat"],
                        "lon": final_destination["lon"]
                    },
                    "route_id": None,
                    "trip_id": None,
                    "mode": "walk",
                    "departure_time": destination_label["arrival_time"],
                    "arrival_time": final_arrival_time,
                    "waiting_time": 0,
                    "distance_meters": candidate.get("distance_meters"),
                    "walking_time": egress_walking_time,
                    "route_label": None,
                    "round": None
                })

            total_travel_time = final_arrival_time - departure_time_seconds
            candidate_path = simplify_legs(candidate_path)
            score = score_path(
                candidate_path,
                total_travel_time,
                final_walking_time=egress_walking_time
            )
            generalized_cost = score["total_cost"]

            candidate_results.append(build_candidate_result(
                origin_stop_id=infer_origin_stop_id(candidate_path, origin_stop_id),
                destination_stop_id=candidate["stop_id"],
                departure_time_seconds=departure_time_seconds,
                arrival_time=final_arrival_time,
                path=candidate_path,
                score=score
            ))
    diagnostics["stage_timings_seconds"]["candidate_reconstruction"] = round(
        time.perf_counter() - stage_start,
        4
    )
    diagnostics["candidate_count"] = len(candidate_results)
    diagnostics["candidates"] = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
    ]
    brt_candidates_before_quality_filter = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "brt" for leg in candidate.get("legs", []))
    ]
    rejected_backtracking_candidates = [
        candidate
        for candidate in candidate_results
        if has_same_route_direction_backtracking(candidate.get("legs", []))
    ]
    candidate_results = [
        candidate
        for candidate in candidate_results
        if not has_same_route_direction_backtracking(candidate.get("legs", []))
    ]
    quality_rejected_candidates = []
    quality_kept_candidates = []

    for candidate in candidate_results:
        rejection_reason = route_quality_rejection_reason(candidate)
        candidate["quality"] = route_quality_metrics(candidate)
        candidate["quality_penalty"] = route_quality_penalty(candidate)

        if rejection_reason:
            rejected_candidate = dict(candidate)
            rejected_candidate["rejected_by_quality_filter"] = rejection_reason
            quality_rejected_candidates.append(rejected_candidate)
            continue

        candidate["rejected_by_quality_filter"] = None
        quality_kept_candidates.append(candidate)

    quality_filter_fallback_used = False
    if quality_kept_candidates:
        candidate_results = quality_kept_candidates
    elif quality_rejected_candidates:
        quality_filter_fallback_used = True
        candidate_results = [
            {
                **candidate,
                "rejected_by_quality_filter": None,
                "quality_filter_fallback": True,
            }
            for candidate in quality_rejected_candidates
        ]

    diagnostics["quality_guard"] = {
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
        "same_route_backtracking_rejected_routes": [
            route_diagnostic_summary(candidate)
            for candidate in rejected_backtracking_candidates
        ],
        "route_quality_rejected": len(quality_rejected_candidates),
        "route_quality_rejected_routes": [
            route_diagnostic_summary(candidate)
            for candidate in quality_rejected_candidates
        ],
        "quality_filter_fallback_used": quality_filter_fallback_used,
        "brt_alternatives_before_quality_filter": len(
            brt_candidates_before_quality_filter
        ),
        "brt_alternatives_after_quality_filter": sum(
            1
            for candidate in candidate_results
            if any(leg.get("mode") == "brt" for leg in candidate.get("legs", []))
        ),
        "candidate_count_after_quality_guard": len(candidate_results),
    }

    stage_start = time.perf_counter()
    alternatives = select_route_alternatives(candidate_results)
    diagnostics["stage_timings_seconds"]["alternative_generation"] = round(
        time.perf_counter() - stage_start,
        4
    )
    diagnostics["selected_alternatives"] = [
        {
            **route_diagnostic_summary(alternative),
            "alternative_label": alternative.get("alternative_label"),
            "badges": alternative.get("badges", []),
        }
        for alternative in alternatives
    ]
    brt_candidate_summaries = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "brt" for leg in candidate.get("legs", []))
    ]
    diagnostics["metro_only_candidates"] = [
        summary
        for summary in diagnostics["candidates"]
        if any(mode == "metro" for mode in summary["modes_sequence"])
        and all(
            mode in ("walk", "metro")
            for mode in summary["modes_sequence"]
        )
    ]
    brt_destination_stop_ids = {
        str(candidate["stop_id"])
        for candidate in destination_candidates
    }
    brt_labels_at_destination = [
        label
        for stop_id, labels in labels_by_stop.items()
        if str(stop_id) in brt_destination_stop_ids
        for label in labels
        if "brt" in label_transit_modes(label)
    ]
    brt_feeder_labels = [
        label
        for labels in labels_by_stop.values()
        for label in labels
        if str(label.get("stop_id", "")).startswith("BRT_")
        and any(
            leg.get("walk_type") == "brt_feeder_transfer"
            for leg in label.get("path", [])
        )
    ]
    brt_rounds = [
        round_item
        for round_item in diagnostics.get("label_stats", {}).get("rounds", [])
    ]
    diagnostics["brt_debug"] = {
        "brt_phase1_exists_in_route_modes": route_modes.get("BRT_PHASE1") == "brt",
        "brt_stop_count": sum(
            1
            for stop_id in stop_details
            if str(stop_id).startswith("BRT_")
        ),
        "brt_khosous_routes": routes_by_stop.get("BRT_KHOSOUS", []),
        "brt_marg_routes": routes_by_stop.get("BRT_MARG", []),
        "brt_phase1_scan_count": sum(
            1
            for round_analysis in diagnostics["round_cap_analysis"]["rounds"]
            for route_entry in round_analysis.get("route_scan_order", [])
            if route_entry.get("route_id") == "BRT_PHASE1"
        ),
        "brt_labels_created": sum(
            round_item.get("labels_created_by_mode", {}).get("brt", 0)
            for round_item in brt_rounds
        ),
        "brt_labels_accepted": sum(
            round_item.get("labels_accepted_by_mode", {}).get("brt", 0)
            for round_item in brt_rounds
        ),
        "brt_destination_label_count": len(brt_labels_at_destination),
        "brt_stops_reached_by_feeder_transfer": sorted({
            str(label.get("stop_id"))
            for label in brt_feeder_labels
        }),
        "brt_alternatives_before_filtering": len(
            brt_candidates_before_quality_filter
        ),
        "brt_alternatives_after_quality_filter": len(brt_candidate_summaries),
        "brt_alternatives_after_filtering": sum(
            1
            for alternative in alternatives
            if any(leg.get("mode") == "brt" for leg in alternative.get("legs", []))
        ),
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
    }
    if diagnostics["brt_debug"]["brt_alternatives_after_filtering"] == 0:
        if diagnostics["brt_debug"]["brt_alternatives_before_filtering"] > 0:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = (
                "brt_alternative_filtered_or_not_selected"
            )
        elif diagnostics["brt_debug"]["brt_labels_accepted"] == 0:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = (
                "brt_labels_not_accepted_or_dominated"
            )
        elif diagnostics["brt_debug"]["brt_phase1_scan_count"] == 0:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = "brt_not_scanned"
        else:
            diagnostics["brt_debug"]["brt_not_returned_reason"] = (
                "brt_slower_than_selected_alternatives"
            )
    lrt_destination_stop_ids = {
        str(candidate["stop_id"])
        for candidate in destination_candidates
    }
    lrt_labels_at_destination = [
        label
        for stop_id, labels in labels_by_stop.items()
        if str(stop_id) in lrt_destination_stop_ids
        for label in labels
        if "lrt" in label_transit_modes(label)
    ]
    lrt_feeder_labels = [
        label
        for labels in labels_by_stop.values()
        for label in labels
        if str(label.get("stop_id", "")).startswith("LRT_")
        and any(
            leg.get("walk_type") == "lrt_feeder_transfer"
            for leg in label.get("path", [])
        )
    ]
    lrt_candidates_before_quality_filter = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "lrt" for leg in candidate.get("legs", []))
    ]
    diagnostics["lrt_debug"] = {
        "lrt_enabled_in_route_modes": any(
            mode == "lrt"
            for mode in route_modes.values()
        ),
        "lrt_stop_count": sum(
            1
            for stop_id in stop_details
            if str(stop_id).startswith("LRT_")
        ),
        "lrt_route_ids": sorted([
            route_id
            for route_id, mode in route_modes.items()
            if mode == "lrt"
        ]),
        "lrt_routes_scanned": sum(
            1
            for round_analysis in diagnostics["round_cap_analysis"]["rounds"]
            for route_entry in round_analysis.get("route_scan_order", [])
            if route_entry.get("route_mode") == "lrt"
        ),
        "lrt_labels_created": sum(
            round_item.get("labels_created_by_mode", {}).get("lrt", 0)
            for round_item in brt_rounds
        ),
        "lrt_labels_accepted": sum(
            round_item.get("labels_accepted_by_mode", {}).get("lrt", 0)
            for round_item in brt_rounds
        ),
        "lrt_destination_label_count": len(lrt_labels_at_destination),
        "lrt_stops_reached_by_feeder_transfer": sorted({
            str(label.get("stop_id"))
            for label in lrt_feeder_labels
        }),
        "lrt_alternatives_before_filtering": len(lrt_candidates_before_quality_filter),
        "lrt_alternatives_after_filtering": sum(
            1
            for alternative in alternatives
            if any(leg.get("mode") == "lrt" for leg in alternative.get("legs", []))
        ),
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
    }
    if diagnostics["lrt_debug"]["lrt_alternatives_after_filtering"] == 0:
        if diagnostics["lrt_debug"]["lrt_alternatives_before_filtering"] > 0:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = (
                "lrt_alternative_filtered_or_not_selected"
            )
        elif diagnostics["lrt_debug"]["lrt_labels_accepted"] == 0:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = (
                "lrt_labels_not_accepted_or_dominated"
            )
        elif diagnostics["lrt_debug"]["lrt_routes_scanned"] == 0:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = "lrt_not_scanned"
        else:
            diagnostics["lrt_debug"]["lrt_not_returned_reason"] = (
                "lrt_slower_than_selected_alternatives"
            )

    monorail_destination_stop_ids = {
        str(candidate["stop_id"])
        for candidate in destination_candidates
    }
    monorail_labels_at_destination = [
        label
        for stop_id, labels in labels_by_stop.items()
        if str(stop_id) in monorail_destination_stop_ids
        for label in labels
        if "monorail" in label_transit_modes(label)
    ]
    monorail_feeder_labels = [
        label
        for labels in labels_by_stop.values()
        for label in labels
        if str(label.get("stop_id", "")).startswith("MONORAIL_")
        and any(
            leg.get("walk_type") == "monorail_feeder_transfer"
            for leg in label.get("path", [])
        )
    ]
    monorail_candidates_before_quality_filter = [
        route_diagnostic_summary(candidate)
        for candidate in candidate_results
        if any(leg.get("mode") == "monorail" for leg in candidate.get("legs", []))
    ]
    diagnostics["monorail_debug"] = {
        "monorail_enabled_in_route_modes": any(
            mode == "monorail"
            for mode in route_modes.values()
        ),
        "monorail_stop_count": sum(
            1
            for stop_id in stop_details
            if str(stop_id).startswith("MONORAIL_")
        ),
        "monorail_route_ids": sorted([
            route_id
            for route_id, mode in route_modes.items()
            if mode == "monorail"
        ]),
        "monorail_routes_scanned": sum(
            1
            for round_analysis in diagnostics["round_cap_analysis"]["rounds"]
            for route_entry in round_analysis.get("route_scan_order", [])
            if route_entry.get("route_mode") == "monorail"
        ),
        "monorail_labels_created": sum(
            round_item.get("labels_created_by_mode", {}).get("monorail", 0)
            for round_item in brt_rounds
        ),
        "monorail_labels_accepted": sum(
            round_item.get("labels_accepted_by_mode", {}).get("monorail", 0)
            for round_item in brt_rounds
        ),
        "monorail_destination_label_count": len(monorail_labels_at_destination),
        "monorail_stops_reached_by_feeder_transfer": sorted({
            str(label.get("stop_id"))
            for label in monorail_feeder_labels
        }),
        "monorail_alternatives_before_filtering": len(monorail_candidates_before_quality_filter),
        "monorail_alternatives_after_filtering": sum(
            1
            for alternative in alternatives
            if any(leg.get("mode") == "monorail" for leg in alternative.get("legs", []))
        ),
        "same_route_backtracking_rejected": len(rejected_backtracking_candidates),
    }
    if diagnostics["monorail_debug"]["monorail_alternatives_after_filtering"] == 0:
        if diagnostics["monorail_debug"]["monorail_alternatives_before_filtering"] > 0:
            diagnostics["monorail_debug"]["monorail_not_returned_reason"] = (
                "monorail_alternative_filtered_or_not_selected"
            )
        elif diagnostics["monorail_debug"]["monorail_labels_accepted"] == 0:
            diagnostics["monorail_debug"]["monorail_not_returned_reason"] = (
                "monorail_labels_not_accepted_or_dominated"
            )
        elif diagnostics["monorail_debug"]["monorail_routes_scanned"] == 0:
            diagnostics["monorail_debug"]["monorail_not_returned_reason"] = "monorail_not_scanned"
        else:
            diagnostics["monorail_debug"]["monorail_not_returned_reason"] = (
                "monorail_slower_than_selected_alternatives"
            )
    if trace:
        trace_summary = {
            "event_count": len(trace["events"]),
            "focus_stops": trace["focus_stops"],
        }

        if trace.get("mode") == "brt":
            trace_summary.update({
                "brt_phase1_exists_in_route_modes": diagnostics["brt_debug"][
                    "brt_phase1_exists_in_route_modes"
                ],
                "brt_stop_count": diagnostics["brt_debug"]["brt_stop_count"],
                "brt_phase1_scan_count": diagnostics["brt_debug"][
                    "brt_phase1_scan_count"
                ],
                "brt_labels_created": diagnostics["brt_debug"][
                    "brt_labels_created"
                ],
                "brt_labels_accepted": diagnostics["brt_debug"][
                    "brt_labels_accepted"
                ],
                "brt_destination_label_count": diagnostics["brt_debug"][
                    "brt_destination_label_count"
                ],
                "same_route_backtracking_rejected": diagnostics["brt_debug"][
                    "same_route_backtracking_rejected"
                ],
                "brt_stops_reached_by_feeder_transfer": diagnostics["brt_debug"][
                    "brt_stops_reached_by_feeder_transfer"
                ],
                "brt_alternatives_before_filtering": diagnostics["brt_debug"][
                    "brt_alternatives_before_filtering"
                ],
                "brt_alternatives_after_filtering": diagnostics["brt_debug"][
                    "brt_alternatives_after_filtering"
                ],
            })
        elif trace.get("mode") == "lrt":
            trace_summary.update({
                "lrt_enabled_in_route_modes": diagnostics["lrt_debug"][
                    "lrt_enabled_in_route_modes"
                ],
                "lrt_stop_count": diagnostics["lrt_debug"]["lrt_stop_count"],
                "lrt_route_ids": diagnostics["lrt_debug"]["lrt_route_ids"],
                "lrt_routes_scanned": diagnostics["lrt_debug"]["lrt_routes_scanned"],
                "lrt_labels_created": diagnostics["lrt_debug"]["lrt_labels_created"],
                "lrt_labels_accepted": diagnostics["lrt_debug"]["lrt_labels_accepted"],
                "lrt_destination_label_count": diagnostics["lrt_debug"][
                    "lrt_destination_label_count"
                ],
                "lrt_stops_reached_by_feeder_transfer": diagnostics["lrt_debug"][
                    "lrt_stops_reached_by_feeder_transfer"
                ],
                "lrt_alternatives_before_filtering": diagnostics["lrt_debug"][
                    "lrt_alternatives_before_filtering"
                ],
                "lrt_alternatives_after_filtering": diagnostics["lrt_debug"][
                    "lrt_alternatives_after_filtering"
                ],
            })
        elif trace.get("mode") == "monorail":
            trace_summary.update({
                "monorail_enabled_in_route_modes": diagnostics["monorail_debug"][
                    "monorail_enabled_in_route_modes"
                ],
                "monorail_stop_count": diagnostics["monorail_debug"]["monorail_stop_count"],
                "monorail_route_ids": diagnostics["monorail_debug"]["monorail_route_ids"],
                "monorail_routes_scanned": diagnostics["monorail_debug"]["monorail_routes_scanned"],
                "monorail_labels_created": diagnostics["monorail_debug"]["monorail_labels_created"],
                "monorail_labels_accepted": diagnostics["monorail_debug"]["monorail_labels_accepted"],
                "monorail_destination_label_count": diagnostics["monorail_debug"][
                    "monorail_destination_label_count"
                ],
                "monorail_stops_reached_by_feeder_transfer": diagnostics["monorail_debug"][
                    "monorail_stops_reached_by_feeder_transfer"
                ],
                "monorail_alternatives_before_filtering": diagnostics["monorail_debug"][
                    "monorail_alternatives_before_filtering"
                ],
                "monorail_alternatives_after_filtering": diagnostics["monorail_debug"][
                    "monorail_alternatives_after_filtering"
                ],
            })
        else:
            trace_summary.update({
                "metro_only_candidate_count": len(diagnostics["metro_only_candidates"]),
                "metro_candidate_event_count": sum(
                1
                for event in trace["events"]
                if "metro" in (event.get("mode_sequence") or [])
                ),
                "closest_reason": infer_metro_trace_reason(
                    trace,
                    diagnostics["metro_only_candidates"],
                    destination_candidates,
                    stop_details,
                ),
            })

        trace["summary"] = trace_summary
        diagnostics["raptor_trace"] = {
            "mode": trace["mode"],
            "summary": trace["summary"],
            "events": trace["events"],
        }

    if not alternatives:
        return {
            "found": False,
            "message": "No route found",
            "routing_diagnostics": diagnostics,
        }

    best_route = alternatives[0]
    best_route["alternatives"] = alternatives
    best_route["routing_diagnostics"] = diagnostics

    return best_route
