def merge_adjacent_walk_legs(raw_legs):
    merged_legs = []

    for leg in raw_legs:
        if (
            merged_legs
            and leg["mode"] == "walk"
            and merged_legs[-1]["mode"] == "walk"
        ):
            previous_leg = merged_legs[-1]
            previous_leg["to_stop_id"] = leg["to_stop_id"]
            previous_leg["to_stop"] = leg.get("to_stop")
            previous_leg["arrival_time"] = leg["arrival_time"]
            previous_leg["walking_time"] = (
                int(previous_leg.get("walking_time", 0))
                + int(leg.get("walking_time", 0))
            )
            previous_distance = previous_leg.get("distance_meters") or 0
            current_distance = leg.get("distance_meters") or 0
            previous_leg["distance_meters"] = round(
                float(previous_distance) + float(current_distance),
                2
            )
            previous_leg["waiting_time"] = 0
            previous_leg["route_id"] = None
            previous_leg["trip_id"] = None
            previous_leg["route_label"] = None
            if leg.get("walk_type") and not previous_leg.get("walk_type"):
                previous_leg["walk_type"] = leg.get("walk_type")
            if leg.get("source") and not previous_leg.get("source"):
                previous_leg["source"] = leg.get("source")
            if leg.get("confidence") and not previous_leg.get("confidence"):
                previous_leg["confidence"] = leg.get("confidence")
            continue

        merged_legs.append(dict(leg))

    return merged_legs


def normalize_metro_platform_stop_id(stop_id):
    stop_id = str(stop_id)

    for suffix in ["_METRO_N", "_METRO_S", "_METRO_E", "_METRO_W"]:
        if stop_id.endswith(suffix):
            return stop_id[:-len(suffix)]

    return stop_id


def is_zero_distance_platform_walk(leg):
    if leg["mode"] != "walk":
        return False

    walking_time = int(leg.get("walking_time", 0))
    distance = float(leg.get("distance_meters") or 0)

    if walking_time > 0 or distance > 0:
        return False

    from_stop_id = leg.get("from_stop_id")
    to_stop_id = leg.get("to_stop_id")

    if from_stop_id == to_stop_id:
        return True

    return (
        normalize_metro_platform_stop_id(from_stop_id)
        == normalize_metro_platform_stop_id(to_stop_id)
    )


def remove_tiny_walks(raw_legs, min_walking_time=5):
    cleaned_legs = []

    for index, leg in enumerate(raw_legs):
        if leg["mode"] != "walk":
            cleaned_legs.append(leg)
            continue

        walking_time = int(leg.get("walking_time", 0))
        is_first_or_last = index == 0 or index == len(raw_legs) - 1
        is_same_stop = leg.get("from_stop_id") == leg.get("to_stop_id")

        if (
            is_zero_distance_platform_walk(leg)
            or is_same_stop
            or (walking_time <= min_walking_time and not is_first_or_last)
        ):
            continue

        cleaned_legs.append(leg)

    return cleaned_legs


def simplify_legs(raw_legs):
    legs = merge_adjacent_walk_legs(raw_legs)
    legs = remove_tiny_walks(legs)
    return merge_adjacent_walk_legs(legs)


def simplify_route(raw_result):
    if not raw_result.get("found"):
        return raw_result

    simplified = dict(raw_result)
    simplified["legs"] = simplify_legs(raw_result.get("legs", []))
    return simplified
