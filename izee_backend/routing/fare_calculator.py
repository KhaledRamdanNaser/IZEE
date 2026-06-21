DEFAULT_CURRENCY = "EGP"

STATIC_FARES_BY_MODE = {
    "bus": 15,
    "minibus": 20,
    "microbus": 12,
    "metro": 15,
    "lrt": 20,
    "brt": 15,
    "monorail": 25,
}

LRT_ROUTE_STOPS = {
    "LRT_ADLY_10RAMADAN": [
        "LRT_ADLY_MANSOUR",
        "LRT_EL_OBOUR",
        "LRT_FUTURE",
        "LRT_EL_SHOROUK",
        "LRT_NEW_HELIOPOLIS",
        "LRT_BADR",
        "LRT_INDUSTRIAL_PARK",
        "LRT_NEW_OBOUR",
        "LRT_WEST_10TH",
        "LRT_10TH_RAMADAN",
        "LRT_CITY_CENTER",
    ],
    "LRT_ADLY_CAPITAL": [
        "LRT_ADLY_MANSOUR",
        "LRT_EL_OBOUR",
        "LRT_FUTURE",
        "LRT_EL_SHOROUK",
        "LRT_NEW_HELIOPOLIS",
        "LRT_BADR",
        "LRT_EL_ROBAIKEY",
        "LRT_HADAYEK_AL_ASSEMA",
        "LRT_CAPITAL_AIRPORT",
        "LRT_ARTS_CULTURE",
        "LRT_CATHEDRAL_NATIVITY",
        "LRT_STRATEGIC_COMMAND",
        "LRT_INTERNATIONAL_SPORTS_CITY",
        "LRT_CENTRAL_CAPITAL",
    ],
}


def calculate_leg_fare(leg):
    mode = leg.get("mode")

    if mode == "walk":
        return 0

    if mode == "lrt":
        return calculate_lrt_leg_fare(leg)

    return STATIC_FARES_BY_MODE.get(mode, STATIC_FARES_BY_MODE["bus"])


def calculate_lrt_leg_fare(leg):
    route_id = leg.get("route_id")
    route_stops = LRT_ROUTE_STOPS.get(route_id)

    if not route_stops:
        return STATIC_FARES_BY_MODE["lrt"]

    try:
        from_index = route_stops.index(leg.get("from_stop_id"))
        to_index = route_stops.index(leg.get("to_stop_id"))
    except ValueError:
        return STATIC_FARES_BY_MODE["lrt"]

    station_count = abs(to_index - from_index) + 1

    if station_count <= 3:
        return 10
    if station_count <= 7:
        return 15
    return 20


def calculate_path_fare(path):
    leg_fares = []
    charged_continuous_rides = set()

    previous_transit_leg = None

    for index, leg in enumerate(path):
        fare = calculate_leg_fare(leg)
        mode = leg.get("mode")
        route_id = leg.get("route_id")

        if mode != "walk" and route_id:
            ride_key = (mode, route_id)
            is_continuous_same_route = (
                previous_transit_leg is not None
                and previous_transit_leg.get("mode") == mode
                and previous_transit_leg.get("route_id") == route_id
                and previous_transit_leg.get("to_stop_id") == leg.get("from_stop_id")
            )

            if is_continuous_same_route and ride_key in charged_continuous_rides:
                fare = 0
            else:
                charged_continuous_rides.add(ride_key)

            previous_transit_leg = leg

        leg_fares.append({
            "mode": leg.get("mode"),
            "from_stop_id": leg.get("from_stop_id"),
            "to_stop_id": leg.get("to_stop_id"),
            "route_id": leg.get("route_id"),
            "leg_index": index,
            "fare": fare,
            "currency": DEFAULT_CURRENCY
        })

    return {
        "total_fare": sum(item["fare"] for item in leg_fares),
        "currency": DEFAULT_CURRENCY,
        "leg_fares": leg_fares
    }
