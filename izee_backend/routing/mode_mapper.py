def infer_route_mode(route):
    agency_id = str(route.get("agency_id", "")).upper()
    route_type = str(route.get("route_type", ""))
    route_long_name = str(route.get("route_long_name", "")).upper()
    route_short_name = str(route.get("route_short_name", "")).upper()

    text = f"{agency_id} {route_long_name} {route_short_name}"

    # Egypt/Cairo agency-specific mapping.
    agency_mode_map = {
        "CTA": "bus",
        "CTA_M": "minibus",
        "MM": "bus",
        "GRN": "bus",
        "P_O_14": "microbus",
        "P_B_8": "microbus",
        "COOP": "microbus",
        "BOX": "microbus",
        "LTRA_M": "minibus",
    }

    if agency_id in agency_mode_map:
        return agency_mode_map[agency_id]

    # Text-based overrides.
    if "BRT" in text:
        return "brt"
    if "LRT" in text:
        return "lrt"
    if "MONORAIL" in text:
        return "monorail"
    if "METRO" in text:
        return "metro"
    if "MICROBUS" in text:
        return "microbus"
    if "MINIBUS" in text:
        return "minibus"

    # GTFS route_type fallback.
    if route_type == "1":
        return "metro"
    if route_type == "0":
        return "lrt"
    if route_type == "3":
        return "bus"

    return "bus"


def build_route_modes(routes):
    route_modes = {}

    for _, route in routes.iterrows():
        route_id = str(route["route_id"])
        route_modes[route_id] = infer_route_mode(route)

    return route_modes
