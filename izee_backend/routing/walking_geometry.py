import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from routing.nearest_stop_search import haversine_meters

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OSRM_PROFILES = [
    profile.strip()
    for profile in os.getenv("OSRM_PROFILES", "foot,walking,driving").split(",")
    if profile.strip()
]
OSRM_TIMEOUT_SECONDS = float(os.getenv("OSRM_TIMEOUT_SECONDS", "2"))
MAX_WALKING_DETOUR_RATIO = float(os.getenv("MAX_WALKING_DETOUR_RATIO", "1.8"))
SHORT_WALK_DIRECT_METERS = float(os.getenv("SHORT_WALK_DIRECT_METERS", "700"))
_geometry_cache = {}


def decode_polyline(polyline, precision=5):
    coordinates = []
    index = 0
    lat = 0
    lon = 0
    factor = 10 ** precision

    while index < len(polyline):
        result = 1
        shift = 0

        while True:
            byte = ord(polyline[index]) - 63 - 1
            index += 1
            result += byte << shift
            shift += 5

            if byte < 0x1F:
                break

        lat += ~(result >> 1) if result & 1 else result >> 1
        result = 1
        shift = 0

        while True:
            byte = ord(polyline[index]) - 63 - 1
            index += 1
            result += byte << shift
            shift += 5

            if byte < 0x1F:
                break

        lon += ~(result >> 1) if result & 1 else result >> 1
        coordinates.append([lat / factor, lon / factor])

    return coordinates


def get_osrm_walking_geometry(from_stop, to_stop):
    if not OSRM_BASE_URL:
        return None

    if not all(key in from_stop for key in ["lat", "lon"]):
        return None

    if not all(key in to_stop for key in ["lat", "lon"]):
        return None

    direct_distance = haversine_meters(
        float(from_stop["lat"]),
        float(from_stop["lon"]),
        float(to_stop["lat"]),
        float(to_stop["lon"])
    )

    cache_key = (
        round(float(from_stop["lat"]), 6),
        round(float(from_stop["lon"]), 6),
        round(float(to_stop["lat"]), 6),
        round(float(to_stop["lon"]), 6),
        ",".join(OSRM_PROFILES),
    )

    if cache_key in _geometry_cache:
        return _geometry_cache[cache_key]

    best_geometry = None
    best_distance = None

    for profile in OSRM_PROFILES:
        url = (
            f"{OSRM_BASE_URL.rstrip('/')}/route/v1/{profile}/"
            f"{from_stop['lon']},{from_stop['lat']};{to_stop['lon']},{to_stop['lat']}"
            "?overview=full&geometries=polyline"
        )

        request = Request(
            url,
            headers={
                "User-Agent": "IZEE-Graduation-Project/1.0",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=OSRM_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            continue

        if payload.get("code") != "Ok":
            continue

        routes = payload.get("routes", [])

        if not routes:
            continue

        route = routes[0]
        geometry = route.get("geometry")

        if not geometry:
            continue

        route_distance = route.get("distance")

        if (
            route_distance is not None
            and direct_distance <= SHORT_WALK_DIRECT_METERS
            and route_distance > direct_distance * MAX_WALKING_DETOUR_RATIO
        ):
            continue

        decoded_geometry = decode_polyline(geometry)

        if len(decoded_geometry) < 2:
            continue

        if best_distance is None or route_distance < best_distance:
            best_distance = route_distance
            best_geometry = decoded_geometry

    if best_geometry is None:
        return None

    _geometry_cache[cache_key] = best_geometry

    return best_geometry


def clear_walking_geometry_cache():
    _geometry_cache.clear()


def walking_geometry_cache_size():
    return len(_geometry_cache)
