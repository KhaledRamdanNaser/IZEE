"""
routing_integration.py
-----------------------
Registers all routing/geocoding/trip-plan endpoints onto an existing FastAPI
`app` instance.

Usage (inside main.py, after `app` is created):
    from routing_integration import register_routing_routes
    register_routing_routes(app)

Nothing in main.py or the original routing block is changed.
"""

from __future__ import annotations

import json
import os
import pickle
import threading
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytz
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import engine, Base, SessionLocal
from models.walking_transfer import WalkingTransfer
from routing.gtfs_loader import load_multiple_gtfs
from routing.graph_builder import build_graph_from_gtfs
from routing.gtfs_validator import validate_gtfs
from routing.raptor_index_builder import build_raptor_indexes
from routing.frequency_expander import expand_frequencies
from routing.raptor_router import simple_raptor
from routing.trip_plan_builder import build_trip_plan
from routing.access_egress import build_access_candidates, build_egress_candidates
from routing.eta_provider import collect_segment_requests, get_segment_estimates
from routing.nearest_stop_search import find_candidate_stops, haversine_meters
from routing.station_aliases import station_area_metadata_for_stop
from routing.walking_geometry import (
    clear_walking_geometry_cache,
    get_osrm_walking_geometry,
    walking_geometry_cache_size,
)

Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# GTFS paths
# ---------------------------------------------------------------------------
GTFS_PATHS = [
    "C:\\Users\\omaro\\Desktop\\semeser 8\\link (7)",
    "C:\\Users\\omaro\\Desktop\\semeser 8\\Metro-GTFS-master\\Metro-GTFS-master",
]
EXPERIMENTAL_BRT_GTFS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "gtfs_experimental",
    "brt",
)
EXPERIMENTAL_LRT_GTFS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "gtfs_experimental",
    "lrt",
)
EXPERIMENTAL_MONORAIL_GTFS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "gtfs_experimental",
    "monorail",
)

EXPERIMENTAL_BRT_ENABLED = (
    os.getenv("IZEE_ENABLE_EXPERIMENTAL_BRT", "1").lower()
    in {"1", "true", "yes", "on"}
)
EXPERIMENTAL_LRT_ENABLED = (
    os.getenv("IZEE_ENABLE_EXPERIMENTAL_LRT", "1").lower()
    in {"1", "true", "yes", "on"}
)
EXPERIMENTAL_MONORAIL_ENABLED = (
    os.getenv("IZEE_ENABLE_EXPERIMENTAL_MONORAIL", "1").lower()
    in {"1", "true", "yes", "on"}
)

if EXPERIMENTAL_BRT_ENABLED:
    GTFS_PATHS.append(EXPERIMENTAL_BRT_GTFS_PATH)
if EXPERIMENTAL_LRT_ENABLED:
    GTFS_PATHS.append(EXPERIMENTAL_LRT_GTFS_PATH)
if EXPERIMENTAL_MONORAIL_ENABLED:
    GTFS_PATHS.append(EXPERIMENTAL_MONORAIL_GTFS_PATH)

_cache_modes = []
if EXPERIMENTAL_BRT_ENABLED:
    _cache_modes.append("brt")
if EXPERIMENTAL_LRT_ENABLED:
    _cache_modes.append("lrt")
if EXPERIMENTAL_MONORAIL_ENABLED:
    _cache_modes.append("monorail")

RAPTOR_CACHE_VERSION = "raptor_indexes_v7" + (
    "".join(_cache_modes) if _cache_modes else "base"
)
RAPTOR_CACHE_PATH = os.path.join(
    os.path.dirname(__file__),
    ".cache",
    f"{RAPTOR_CACHE_VERSION}.pkl",
)

# ---------------------------------------------------------------------------
# Module-level caches (shared state)
# ---------------------------------------------------------------------------
raptor_indexes_cache = None
walking_transfers_cache: dict = {}
brt_feeder_transfer_count_cache = 0
lrt_feeder_transfer_count_cache = 0
monorail_feeder_transfer_count_cache = 0
eta_segment_requests_cache = None
geocode_search_cache: dict = {}
walking_transfers_preload_started = False

# ---------------------------------------------------------------------------
# Routing constants
# ---------------------------------------------------------------------------
NORMAL_ACCESS_RADIUS_METERS = 1000
NORMAL_EGRESS_RADIUS_METERS = 700
NORMAL_ACCESS_CANDIDATE_LIMIT = 25
NORMAL_EGRESS_CANDIDATE_LIMIT = 10
EMERGENCY_ACCESS_RADIUS_METERS = 3000
EMERGENCY_EGRESS_RADIUS_METERS = 3000
UNLIMITED_NEAREST_STOP_RADIUS_METERS = None
IZEE_BRT_ACCESS_RADIUS_M = int(os.getenv("IZEE_BRT_ACCESS_RADIUS_M", "900"))
IZEE_BACKBONE_ACCESS_RADIUS_M = int(os.getenv("IZEE_BACKBONE_ACCESS_RADIUS_M", "1500"))
IZEE_BACKBONE_CANDIDATES_PER_MODE = int(os.getenv("IZEE_BACKBONE_CANDIDATES_PER_MODE", "3"))
IZEE_BRT_TRANSFER_RADIUS_M = int(os.getenv("IZEE_BRT_TRANSFER_RADIUS_M", "500"))
IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M = int(os.getenv("IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M", "900"))
IZEE_ENABLE_BRT_FEEDER_TRANSFERS = (
    os.getenv("IZEE_ENABLE_BRT_FEEDER_TRANSFERS", "1").lower() in {"1", "true", "yes", "on"}
)
IZEE_LRT_TRANSFER_RADIUS_M = int(os.getenv("IZEE_LRT_TRANSFER_RADIUS_M", "500"))
IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M = int(os.getenv("IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M", "900"))
IZEE_ENABLE_LRT_FEEDER_TRANSFERS = (
    os.getenv("IZEE_ENABLE_LRT_FEEDER_TRANSFERS", "1").lower() in {"1", "true", "yes", "on"}
)
IZEE_MONORAIL_TRANSFER_RADIUS_M = int(os.getenv("IZEE_MONORAIL_TRANSFER_RADIUS_M", "500"))
IZEE_ENABLE_MONORAIL_FEEDER_TRANSFERS = (
    os.getenv("IZEE_ENABLE_MONORAIL_FEEDER_TRANSFERS", "1").lower() in {"1", "true", "yes", "on"}
)
MONORAIL_FEEDER_MODES = {"bus", "microbus", "metro", "minibus", "brt", "lrt"}

BRT_MAJOR_INTERCHANGE_STOP_IDS = {
    "BRT_ADLY_MANSOUR", "BRT_MARG", "BRT_SALAM", "BRT_MOSTOROD",
}
BRT_FEEDER_MODES = {"bus", "microbus", "metro", "minibus"}

LRT_MAJOR_INTERCHANGE_STOP_IDS = {
    "LRT_ADLY_MANSOUR", "LRT_BADR", "LRT_ARTS_CULTURE",
    "LRT_CAPITAL_AIRPORT", "LRT_CENTRAL_CAPITAL",
}
LRT_FEEDER_MODES = {"bus", "microbus", "metro", "minibus", "brt", "monorail"}
BACKBONE_ACCESS_MODES = {"brt", "metro", "lrt", "monorail"}

BRT_STOP_ALIASES: dict = {}   # populated at runtime from original data
LRT_STOP_ALIASES: dict = {}   # populated at runtime from original data

DEFAULT_TRIP_DEPARTURE_TIME = os.getenv("IZEE_DEFAULT_TRIP_DEPARTURE_TIME", "08:00:00")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class Coordinate(BaseModel):
    lat: float
    lon: float


class TripPlanRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    departure_time: str | None = "now"
    max_transfers: int = 2
    use_walking: bool = True


# ---------------------------------------------------------------------------
# Helper functions (copied verbatim from the commented block)
# ---------------------------------------------------------------------------

def build_geocode_query_variants(query: str):
    query = query.strip()
    variants = [
        query,
        f"{query}, Cairo",
        f"{query}, Egypt",
        f"{query}, القاهرة",
        f"{query}, محافظة القاهرة",
    ]
    seen = set()
    unique_variants = []
    for variant in variants:
        normalized = variant.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_variants.append(variant)
    return unique_variants


def fetch_nominatim_results(query: str, limit: int):
    params = urlencode({
        "q": query,
        "format": "json",
        "limit": limit,
        "countrycodes": "eg",
        "accept-language": "ar,en",
        "addressdetails": 1,
    })
    request = Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={
            "User-Agent": "IZEE-Graduation-Project/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = response.read().decode("utf-8")
    except HTTPError:
        return []
    except URLError:
        return []
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return []


def score_osm_place_result(place, query_variant):
    name = str(place.get("display_name", "")).lower()
    variant = str(query_variant).lower()
    lat = float(place["lat"])
    lon = float(place["lon"])
    score = 0
    greater_cairo_terms = ("القاهرة", "cairo", "الجيزة", "giza", "القليوبية", "qalyubia")
    if any(term in name for term in greater_cairo_terms):
        score -= 100
    if any(term in variant for term in ("cairo", "القاهرة")):
        score -= 25
    if 29.75 <= lat <= 30.35 and 30.95 <= lon <= 31.65:
        score -= 75
    else:
        score += 75
    return score


def osm_result_type(place):
    place_class = str(place.get("class", "")).lower()
    place_type = str(place.get("type", "")).lower()
    if place_class == "place" or place_type in {
        "suburb", "neighbourhood", "city", "town", "village", "quarter",
    }:
        return "district"
    if place_class in {"amenity", "tourism", "building", "shop", "leisure"}:
        return "landmark"
    return "osm_place"


def search_places_with_nominatim(query: str, limit: int = 10):
    cache_key = (query.strip().lower(), int(limit))
    if cache_key in geocode_search_cache:
        return geocode_search_cache[cache_key]
    results = []
    seen: set = set()
    
    import time
    for query_variant in build_geocode_query_variants(query):
        data = fetch_nominatim_results(query_variant, limit=limit)
        
        found_new = False
        for place in data:
            if "lat" not in place or "lon" not in place:
                continue
            dedupe_key = (
                round(float(place["lat"]), 6),
                round(float(place["lon"]), 6),
                str(place.get("display_name", "")).lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            found_new = True
            results.append({
                "name": place.get("display_name", query),
                "lat": float(place["lat"]),
                "lon": float(place["lon"]),
                "source": "openstreetmap",
                "result_type": osm_result_type(place),
                "type": osm_result_type(place),
                "matched_query": query_variant,
                "_rank": score_osm_place_result(place, query_variant),
            })
            
        # If we have enough results, stop spamming the API
        if len(results) >= limit:
            break
            
        # Nominatim STRICTLY limits to 1 request per second.
        # Delay to prevent HTTP 429 Too Many Requests blocking the backend.
        time.sleep(1)

    results.sort(key=lambda result: result.pop("_rank"))
    results = results[:limit]
    geocode_search_cache[cache_key] = results
    return results


def normalize_place_query(value):
    return str(value or "").strip().lower()


def normalize_query_for_exact_match(query):
    normalized = normalize_place_query(query)
    for term in ("brt", "lrt", "metro", "مترو", "محطة", "station"):
        normalized = normalized.replace(term, " ")
    return " ".join(normalized.split())


def query_has_transit_intent(query):
    normalized = normalize_place_query(query)
    transit_terms = ("brt", "lrt", "metro", "مترو", "محطة", "station")
    return any(term in normalized for term in transit_terms)


def internal_stop_search(query, limit=10):
    normalized_query = normalize_place_query(query)
    normalized_core_query = normalize_query_for_exact_match(query)
    indexes = get_raptor_indexes()
    stop_details = indexes.get("stop_details", {})
    route_modes = indexes.get("route_modes", {})
    routes_by_stop = indexes.get("routes_by_stop", {})
    results = []
    for stop_id, stop in stop_details.items():
        stop_id = str(stop_id)
        modes = {
            route_modes.get(route_id, "unknown")
            for route_id in routes_by_stop.get(stop_id, [])
        }
        aliases = list(BRT_STOP_ALIASES.get(stop_id, []))
        aliases.extend(LRT_STOP_ALIASES.get(stop_id, []))
        upper_stop_id = stop_id.upper()
        if "metro" in modes and "MRG_METRO" in upper_stop_id:
            aliases.extend(["المرج", "metro marg"])
        if "metro" in modes and "NMR_METRO" in upper_stop_id:
            aliases.extend(["المرج الجديدة", "new el marg", "metro new marg"])
        station_metadata = station_area_metadata_for_stop(stop.get("name", ""))
        if station_metadata:
            aliases.extend(station_metadata["aliases"])
            aliases.extend(station_metadata.get("nearby_landmarks", []))
        search_text = " ".join([
            stop_id,
            str(stop.get("name", "")),
            *aliases,
            *modes,
        ]).lower()
        if (
            normalized_query not in search_text
            and normalized_core_query not in search_text
        ):
            continue
        primary_mode = (
            "brt" if "brt" in modes
            else "metro" if "metro" in modes
            else "lrt" if "lrt" in modes
            else "monorail" if "monorail" in modes
            else "bus"
        )
        display_name = aliases[0] if aliases else stop.get("name", stop_id)
        prefix = primary_mode.upper() if primary_mode in {"brt", "metro", "lrt"} else "Transit"
        subtitle_parts = []
        if station_metadata:
            subtitle_parts.append("Official Mobility Cairo station-area map")
            if station_metadata.get("nearby_landmarks"):
                subtitle_parts.append(
                    "Nearby: " + ", ".join(station_metadata["nearby_landmarks"][:3])
                )
        result = {
            "name": f"{prefix} {display_name}",
            "display_name": f"{prefix} {display_name}",
            "subtitle": " · ".join(subtitle_parts),
            "lat": stop["lat"],
            "lon": stop["lon"],
            "source": "internal_stop",
            "result_type": "transit_stop",
            "type": "transit_stop",
            "stop_id": stop_id,
            "mode": primary_mode,
            "modes": sorted(modes),
            "_match_text": " ".join([
                str(stop.get("name", "")),
                *aliases,
            ]).lower(),
        }
        if station_metadata:
            result["station_metadata"] = {
                "station_name_en": station_metadata["station_name_en"],
                "station_name_ar": station_metadata["station_name_ar"],
                "nearby_landmarks": station_metadata.get("nearby_landmarks", []),
                "source_urls": station_metadata["source_urls"],
                "confidence": station_metadata["confidence"],
                "usage": station_metadata["usage"],
            }
        results.append(result)

    mode_order = {
        "brt": 0, "metro": 1, "lrt": 2, "monorail": 3,
        "bus": 4, "minibus": 5, "microbus": 6,
    }
    deduped_results = []
    seen_internal_places: set = set()
    for item in results:
        key = (
            item["mode"],
            item["name"],
            round(float(item["lat"]), 6),
            round(float(item["lon"]), 6),
        )
        if key in seen_internal_places:
            continue
        seen_internal_places.add(key)
        deduped_results.append(item)

    deduped_results.sort(key=lambda item: (
        mode_order.get(item["mode"], 99),
        0 if item.get("station_metadata") else 1,
        0 if item["stop_id"] in BRT_MAJOR_INTERCHANGE_STOP_IDS else 1,
        item["name"],
    ))
    return deduped_results[:limit]


def merged_place_search(query, limit=10):
    internal_results = internal_stop_search(query, limit=limit)
    osm_results = search_places_with_nominatim(query, limit=limit)
    transit_intent = query_has_transit_intent(query)
    normalized_exact = normalize_query_for_exact_match(query)
    exact_internal = []
    other_internal = []
    for place in internal_results:
        match_text = place.get("_match_text", "").lower()
        is_exact = (
            normalized_exact
            and (
                normalized_exact == match_text
                or normalized_exact in match_text.split()
                or normalized_exact in match_text
            )
        )
        if is_exact:
            exact_internal.append(place)
        else:
            other_internal.append(place)

    if transit_intent:
        ordered_candidates = [*exact_internal, *other_internal, *osm_results]
    else:
        ordered_candidates = [
            *exact_internal[:1],
            *osm_results[:1],
            *exact_internal[1:],
            *other_internal,
            *osm_results[1:],
        ]

    seen: set = set()
    merged = []
    for place in ordered_candidates:
        key = (round(float(place["lat"]), 6), round(float(place["lon"]), 6))
        if key in seen:
            continue
        seen.add(key)
        clean_place = dict(place)
        clean_place.pop("_match_text", None)
        merged.append(clean_place)
        if len(merged) >= limit:
            break
    return merged[:limit]


def time_to_seconds_value(value: str):
    h, m, s = map(int, str(value).split(":"))
    return h * 3600 + m * 60 + s


def current_cairo_time_seconds():
    now = datetime.now(pytz.timezone("Africa/Cairo"))
    return now.hour * 3600 + now.minute * 60 + now.second


def departure_time_to_seconds(value):
    if value is None:
        return current_cairo_time_seconds()
    text = str(value).strip()
    if not text or text.lower() in {"now", "current", "current_time"}:
        return current_cairo_time_seconds()
    if "T" in text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            cairo_time = parsed.astimezone(pytz.timezone("Africa/Cairo"))
            return cairo_time.hour * 3600 + cairo_time.minute * 60 + cairo_time.second
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid departure_time format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
    try:
        return time_to_seconds_value(text)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid departure_time format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
        )



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_project_gtfs():
    return load_multiple_gtfs(GTFS_PATHS)


def load_raptor_indexes_from_disk():
    if not os.path.exists(RAPTOR_CACHE_PATH):
        return None
    print("Loading RAPTOR indexes from disk cache...")
    try:
        with open(RAPTOR_CACHE_PATH, "rb") as cache_file:
            return pickle.load(cache_file)
    except (OSError, pickle.PickleError, EOFError, ValueError, AttributeError) as exc:
        print(f"RAPTOR disk cache could not be loaded; rebuilding. Reason: {exc}")
        return None


def save_raptor_indexes_to_disk(indexes):
    os.makedirs(os.path.dirname(RAPTOR_CACHE_PATH), exist_ok=True)
    with open(RAPTOR_CACHE_PATH, "wb") as cache_file:
        pickle.dump(indexes, cache_file, protocol=pickle.HIGHEST_PROTOCOL)


def preload_raptor_indexes_if_cached():
    global raptor_indexes_cache
    if raptor_indexes_cache is not None:
        return
    raptor_indexes_cache = load_raptor_indexes_from_disk()
    if raptor_indexes_cache is not None:
        print("RAPTOR indexes loaded from disk cache at startup.")


def get_raptor_indexes():
    global raptor_indexes_cache
    if raptor_indexes_cache is None:
        raptor_indexes_cache = load_raptor_indexes_from_disk()
    if raptor_indexes_cache is None:
        print("Building RAPTOR indexes...")
        stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()
        expanded_trips, expanded_stop_times = expand_frequencies(trips, stop_times, frequencies)
        raptor_indexes_cache = build_raptor_indexes(
            expanded_stop_times, expanded_trips, routes, stops, shapes
        )
        save_raptor_indexes_to_disk(raptor_indexes_cache)
        print("RAPTOR indexes built and cached.")
    return raptor_indexes_cache


def get_eta_segment_requests(indexes):
    global eta_segment_requests_cache
    if eta_segment_requests_cache is None:
        eta_segment_requests_cache = collect_segment_requests(indexes)
    return eta_segment_requests_cache


def get_eta_estimates_for_routing(indexes, departure_time_seconds):
    segment_requests = get_eta_segment_requests(indexes)
    return get_segment_estimates(
        segment_requests=segment_requests,
        departure_time_seconds=departure_time_seconds,
    )


def get_walking_transfers_from_db(db: Session, walk_type: str = "normal_transfer"):
    if walk_type in walking_transfers_cache:
        return walking_transfers_cache[walk_type]
    print(f"Loading walking transfers for {walk_type}...")
    rows = db.query(WalkingTransfer).filter(WalkingTransfer.walk_type == walk_type).all()
    transfers: dict = {}
    for row in rows:
        transfers.setdefault(row.from_stop_id, []).append({
            "to": row.to_stop_id,
            "distance_meters": row.distance_meters,
            "walking_time": row.walking_time,
        })
    walking_transfers_cache[walk_type] = transfers
    print(f"Walking transfers for {walk_type} loaded and cached.")
    return transfers


def preload_walking_transfers():
    db = SessionLocal()
    try:
        get_walking_transfers_from_db(db, walk_type="normal_transfer")
        get_walking_transfers_from_db(db, walk_type="emergency_access")
    except Exception as exc:
        print(f"Walking transfer preload failed: {exc}")
    finally:
        db.close()


def start_walking_transfer_preload_background():
    global walking_transfers_preload_started
    if walking_transfers_preload_started:
        return
    walking_transfers_preload_started = True
    thread = threading.Thread(
        target=preload_walking_transfers,
        name="walking-transfer-preload",
        daemon=True,
    )
    thread.start()


def merge_walking_transfers(*transfer_maps):
    merged: dict = {}
    best_edges: dict = {}
    for transfer_map in transfer_maps:
        for from_stop_id, edges in transfer_map.items():
            for edge in edges:
                key = (str(from_stop_id), str(edge["to"]))
                previous = best_edges.get(key)
                if (
                    previous is None
                    or float(edge.get("distance_meters", 0)) < float(previous.get("distance_meters", 0))
                ):
                    best_edges[key] = edge
    for (from_stop_id, _), edge in best_edges.items():
        merged.setdefault(from_stop_id, []).append(edge)
    return merged


def stop_modes(stop_id, indexes):
    route_modes = indexes.get("route_modes", {})
    routes = indexes.get("routes_by_stop", {}).get(str(stop_id), [])
    return {route_modes.get(route_id, "unknown") for route_id in routes}


def is_brt_stop(stop_id, indexes):
    stop_id = str(stop_id)
    return stop_id.startswith("BRT_") or "brt" in stop_modes(stop_id, indexes)


def is_lrt_stop(stop_id, indexes):
    stop_id = str(stop_id)
    return stop_id.startswith("LRT_") or "lrt" in stop_modes(stop_id, indexes)


def build_brt_feeder_transfers(indexes):
    global brt_feeder_transfer_count_cache
    cache_key = "brt_feeder_transfer_generated"
    if cache_key in walking_transfers_cache:
        return walking_transfers_cache[cache_key]
    if not (EXPERIMENTAL_BRT_ENABLED and IZEE_ENABLE_BRT_FEEDER_TRANSFERS):
        walking_transfers_cache[cache_key] = {}
        brt_feeder_transfer_count_cache = 0
        return {}
    stop_details = indexes.get("stop_details", {})
    transfers: dict = {}
    edge_count = 0
    brt_stop_ids = [s for s in stop_details if is_brt_stop(s, indexes)]
    for brt_stop_id in brt_stop_ids:
        brt_stop = stop_details[brt_stop_id]
        radius = (
            IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M
            if brt_stop_id in BRT_MAJOR_INTERCHANGE_STOP_IDS
            else IZEE_BRT_TRANSFER_RADIUS_M
        )
        for other_stop_id, other_stop in stop_details.items():
            other_stop_id = str(other_stop_id)
            if other_stop_id == brt_stop_id:
                continue
            if is_brt_stop(other_stop_id, indexes):
                continue
            modes = stop_modes(other_stop_id, indexes)
            if not modes.intersection(BRT_FEEDER_MODES):
                continue
            distance = haversine_meters(
                brt_stop["lat"], brt_stop["lon"],
                other_stop["lat"], other_stop["lon"],
            )
            if distance > radius:
                continue
            edge_base = {
                "mode": "walk",
                "distance_meters": round(distance, 2),
                "walking_time": int(distance / 1.3),
                "walk_type": "brt_feeder_transfer",
                "source": "generated_brt_feeder",
                "confidence": "medium",
            }
            transfers.setdefault(brt_stop_id, []).append({**edge_base, "to": other_stop_id})
            transfers.setdefault(other_stop_id, []).append({**edge_base, "to": brt_stop_id})
            edge_count += 2
    walking_transfers_cache[cache_key] = transfers
    brt_feeder_transfer_count_cache = edge_count
    print(f"Generated {edge_count} BRT feeder walking transfers.")
    return transfers


def build_lrt_feeder_transfers(indexes):
    global lrt_feeder_transfer_count_cache
    cache_key = "lrt_feeder_transfer_generated"
    if cache_key in walking_transfers_cache:
        return walking_transfers_cache[cache_key]
    if not (EXPERIMENTAL_LRT_ENABLED and IZEE_ENABLE_LRT_FEEDER_TRANSFERS):
        walking_transfers_cache[cache_key] = {}
        lrt_feeder_transfer_count_cache = 0
        return {}
    stop_details = indexes.get("stop_details", {})
    transfers: dict = {}
    edge_count = 0
    lrt_stop_ids = [s for s in stop_details if is_lrt_stop(s, indexes)]
    for lrt_stop_id in lrt_stop_ids:
        lrt_stop = stop_details[lrt_stop_id]
        radius = (
            IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M
            if lrt_stop_id in LRT_MAJOR_INTERCHANGE_STOP_IDS
            else IZEE_LRT_TRANSFER_RADIUS_M
        )
        for other_stop_id, other_stop in stop_details.items():
            other_stop_id = str(other_stop_id)
            if other_stop_id == lrt_stop_id:
                continue
            if is_lrt_stop(other_stop_id, indexes):
                continue
            modes = stop_modes(other_stop_id, indexes)
            if not modes.intersection(LRT_FEEDER_MODES):
                continue
            distance = haversine_meters(
                lrt_stop["lat"], lrt_stop["lon"],
                other_stop["lat"], other_stop["lon"],
            )
            if distance > radius:
                continue
            edge_base = {
                "mode": "walk",
                "distance_meters": round(distance, 2),
                "walking_time": int(distance / 1.3),
                "walk_type": "lrt_feeder_transfer",
                "source": "generated_lrt_feeder",
                "confidence": "medium",
            }
            transfers.setdefault(lrt_stop_id, []).append({**edge_base, "to": other_stop_id})
            transfers.setdefault(other_stop_id, []).append({**edge_base, "to": lrt_stop_id})
            edge_count += 2
    walking_transfers_cache[cache_key] = transfers
    lrt_feeder_transfer_count_cache = edge_count
    print(f"Generated {edge_count} LRT feeder walking transfers.")
    return transfers


def is_monorail_stop(stop_id, indexes):
    stop_id = str(stop_id)
    return stop_id.startswith("MONORAIL_") or "monorail" in stop_modes(stop_id, indexes)


def build_monorail_feeder_transfers(indexes):
    global monorail_feeder_transfer_count_cache
    cache_key = "monorail_feeder_transfer_generated"
    if cache_key in walking_transfers_cache:
        return walking_transfers_cache[cache_key]
    if not (EXPERIMENTAL_MONORAIL_ENABLED and IZEE_ENABLE_MONORAIL_FEEDER_TRANSFERS):
        walking_transfers_cache[cache_key] = {}
        monorail_feeder_transfer_count_cache = 0
        return {}
    stop_details = indexes.get("stop_details", {})
    transfers: dict = {}
    edge_count = 0
    monorail_stop_ids = [s for s in stop_details if is_monorail_stop(s, indexes)]
    for monorail_stop_id in monorail_stop_ids:
        monorail_stop = stop_details[monorail_stop_id]
        radius = IZEE_MONORAIL_TRANSFER_RADIUS_M
        for other_stop_id, other_stop in stop_details.items():
            other_stop_id = str(other_stop_id)
            if other_stop_id == monorail_stop_id:
                continue
            if is_monorail_stop(other_stop_id, indexes):
                continue
            modes = stop_modes(other_stop_id, indexes)
            if not modes.intersection(MONORAIL_FEEDER_MODES):
                continue
            distance = haversine_meters(
                monorail_stop["lat"], monorail_stop["lon"],
                other_stop["lat"], other_stop["lon"],
            )
            if distance > radius:
                continue
            edge_base = {
                "mode": "walk",
                "distance_meters": round(distance, 2),
                "walking_time": int(distance / 1.3),
                "walk_type": "monorail_feeder_transfer",
                "source": "generated_monorail_feeder",
                "confidence": "medium",
            }
            transfers.setdefault(monorail_stop_id, []).append({**edge_base, "to": other_stop_id})
            transfers.setdefault(other_stop_id, []).append({**edge_base, "to": monorail_stop_id})
            edge_count += 2
    walking_transfers_cache[cache_key] = transfers
    monorail_feeder_transfer_count_cache = edge_count
    print(f"Generated {edge_count} Monorail feeder walking transfers.")
    return transfers


def nearest_brt_candidates(point, indexes, radius_meters=None, limit=3):
    radius_meters = radius_meters or IZEE_BRT_ACCESS_RADIUS_M
    brt_stop_details = {
        stop_id: stop
        for stop_id, stop in indexes.get("stop_details", {}).items()
        if is_brt_stop(stop_id, indexes)
    }
    return find_candidate_stops(
        lat=point["lat"], lon=point["lon"],
        stop_details=brt_stop_details,
        max_distance_meters=radius_meters, limit=limit,
    )


def nearest_lrt_candidates(point, indexes, radius_meters=None, limit=3):
    radius_meters = radius_meters or IZEE_BACKBONE_ACCESS_RADIUS_M
    lrt_stop_details = {
        stop_id: stop
        for stop_id, stop in indexes.get("stop_details", {}).items()
        if is_lrt_stop(stop_id, indexes)
    }
    return find_candidate_stops(
        lat=point["lat"], lon=point["lon"],
        stop_details=lrt_stop_details,
        max_distance_meters=radius_meters, limit=limit,
    )


def nearest_backbone_candidates_by_mode(
    point, indexes,
    radius_meters=IZEE_BACKBONE_ACCESS_RADIUS_M,
    per_mode_limit=IZEE_BACKBONE_CANDIDATES_PER_MODE,
    modes=BACKBONE_ACCESS_MODES,
):
    candidates = []
    stop_details = indexes.get("stop_details", {})
    for mode in modes:
        mode_stop_details = {
            stop_id: stop
            for stop_id, stop in stop_details.items()
            if mode in stop_modes(stop_id, indexes)
        }
        mode_candidates = find_candidate_stops(
            lat=point["lat"], lon=point["lon"],
            stop_details=mode_stop_details,
            max_distance_meters=radius_meters, limit=per_mode_limit,
        )
        for candidate in mode_candidates:
            candidate["candidate_policy"] = f"nearest_{mode}_backbone"
        candidates.extend(mode_candidates)
    return candidates


def nearest_backbone_candidates_unbounded(point, indexes, per_mode_limit=1, modes=BACKBONE_ACCESS_MODES):
    return nearest_backbone_candidates_by_mode(
        point=point, indexes=indexes,
        radius_meters=None, per_mode_limit=per_mode_limit, modes=modes,
    )


def merge_candidates_with_priority(base_candidates, priority_candidates, indexes=None):
    by_stop_id = {str(c["stop_id"]): c for c in base_candidates}
    for candidate in priority_candidates:
        stop_id = str(candidate["stop_id"])
        previous = by_stop_id.get(stop_id)
        if previous is None or candidate["distance_meters"] < previous["distance_meters"]:
            by_stop_id[stop_id] = candidate
    return sorted(
        by_stop_id.values(),
        key=lambda c: (
            0 if indexes is not None and stop_modes(c["stop_id"], indexes).intersection(BACKBONE_ACCESS_MODES) else 1,
            c["distance_meters"],
        ),
    )


def annotate_emergency_fallback(raw_result, reason):
    raw_result["fallback_used"] = True
    raw_result["fallback_type"] = "emergency_access"
    raw_result["fallback_reason"] = reason
    for alternative in raw_result.get("alternatives", []):
        alternative["fallback_used"] = True
        alternative["fallback_type"] = "emergency_access"
        alternative["fallback_reason"] = reason
    return raw_result


def is_metro_stop_detail(stop):
    stop_id = str(stop.get("stop_id", "")).upper()
    stop_name = str(stop.get("name", "")).upper()
    return "_METRO" in stop_id or " METRO" in stop_name or stop_name.endswith("METRO")


def nearby_stop_failure_response(kind, point, stop_details, max_distance_meters):
    wider_candidates = build_access_candidates(
        origin=point, stop_details=stop_details, max_distance_meters=5000, limit=3
    )
    return {
        "request_id": None,
        "routes": [],
        "message": (
            f"No nearby {kind} stops found within {max_distance_meters} meters. "
            "Try choosing a place closer to the transit coverage area."
        ),
        "nearest_stops": [
            {
                "stop_id": c["stop_id"],
                "name": c.get("stop", {}).get("name"),
                "distance_meters": c["distance_meters"],
                "walking_time": c["walking_time"],
            }
            for c in wider_candidates
        ],
    }


def summarize_candidate_stop(candidate, indexes):
    stop_id = str(candidate["stop_id"])
    routes = indexes["routes_by_stop"].get(stop_id, [])
    modes = sorted(stop_modes(stop_id, indexes))
    primary_mode = (
        "brt" if "brt" in modes
        else "metro" if "metro" in modes
        else "lrt" if "lrt" in modes
        else "monorail" if "monorail" in modes
        else modes[0] if modes
        else "unknown"
    )
    return {
        "stop_id": stop_id,
        "stop_name": candidate.get("stop", {}).get("name"),
        "name": candidate.get("stop", {}).get("name"),
        "mode": primary_mode,
        "station_type": "backbone" if set(modes).intersection(BACKBONE_ACCESS_MODES) else "surface",
        "distance_meters": candidate["distance_meters"],
        "walking_time": candidate["walking_time"],
        "candidate_policy": candidate.get("candidate_policy", "nearest_overall"),
        "routes_available": routes,
        "route_modes_available": modes,
        "reachable_routes": [
            {
                "route_id": route_id,
                "label": indexes["route_labels"].get(route_id, route_id),
                "mode": indexes["route_modes"].get(route_id, "unknown"),
            }
            for route_id in routes
        ],
    }


# ---------------------------------------------------------------------------
# Main registration function – call this from main.py
# ---------------------------------------------------------------------------

def register_routing_routes(app: FastAPI) -> None:
    """
    Attach all routing/geocoding/trip-plan endpoints to the given FastAPI app.
    Call this once after the app is created in main.py.
    """

    # Preload caches on startup
    @app.on_event("startup")
    def _routing_startup():
        preload_raptor_indexes_if_cached()
        start_walking_transfer_preload_background()

    # ------------------------------------------------------------------
    # Geocode / place-search endpoints
    # ------------------------------------------------------------------

    @app.get("/geocode/search")
    def geocode_search(
        query: str = Query(..., min_length=2),
        limit: int = Query(10, ge=1, le=10),
        debug: bool = False,
    ):
        started_at = time.perf_counter()
        limit = int(limit)
        results = search_places_with_nominatim(query, limit=limit)
        response = {"query": query, "results": results}
        if debug:
            response["debug"] = {
                "performance": {
                    "geocoding_ms": round((time.perf_counter() - started_at) * 1000, 2)
                }
            }
        return response

    @app.get("/places/search")
    def places_search(
        query: str = Query(..., min_length=2),
        limit: int = Query(10, ge=1, le=10),
        debug: bool = False,
    ):
        started_at = time.perf_counter()
        limit = int(limit)
        results = merged_place_search(query, limit=limit)
        response = {"query": query, "results": results}
        if debug:
            response["debug"] = {
                "performance": {
                    "places_search_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
                "internal_result_count": sum(
                    1 for r in results if r.get("source") == "internal_stop"
                ),
                "brt_enabled": EXPERIMENTAL_BRT_ENABLED,
            }
        return response

    # ------------------------------------------------------------------
    # Debug endpoints
    # ------------------------------------------------------------------

    @app.get("/debug/graph")
    def debug_graph():
        stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()
        graph = build_graph_from_gtfs(stop_times, trips)
        return graph

    @app.get("/debug/transfers")
    def debug_transfers(
        walk_type: str = "normal_transfer",
        limit: int = 100,
        db: Session = Depends(get_db),
    ):
        transfers = (
            db.query(WalkingTransfer)
            .filter(WalkingTransfer.walk_type == walk_type)
            .limit(limit)
            .all()
        )
        return {
            "walk_type": walk_type,
            "limit": limit,
            "transfers": [
                {
                    "from": t.from_stop_id,
                    "to": t.to_stop_id,
                    "mode": "walk",
                    "walk_type": t.walk_type,
                    "distance_meters": t.distance_meters,
                    "walking_time": t.walking_time,
                }
                for t in transfers
            ],
        }

    @app.get("/debug/transfers/{stop_id}")
    def debug_transfers_for_stop(
        stop_id: str,
        walk_type: str = "normal_transfer",
        db: Session = Depends(get_db),
    ):
        transfers = (
            db.query(WalkingTransfer)
            .filter(
                WalkingTransfer.from_stop_id == stop_id,
                WalkingTransfer.walk_type == walk_type,
            )
            .all()
        )
        return {
            "stop_id": stop_id,
            "walk_type": walk_type,
            "transfers": [
                {
                    "to": t.to_stop_id,
                    "mode": "walk",
                    "walk_type": t.walk_type,
                    "distance_meters": t.distance_meters,
                    "walking_time": t.walking_time,
                }
                for t in transfers
            ],
        }

    @app.get("/debug/metro/stops")
    def debug_metro_stops(limit: int = 50):
        indexes = get_raptor_indexes()
        metro_stops = [
            stop
            for stop in indexes["stop_details"].values()
            if is_metro_stop_detail(stop)
        ]
        return {"count": len(metro_stops), "sample": metro_stops[:limit]}

    @app.get("/debug/stops/search")
    def debug_search_stops(query: str, limit: int = 20):
        indexes = get_raptor_indexes()
        query_upper = query.upper()
        matches = [
            stop
            for stop in indexes["stop_details"].values()
            if query_upper in str(stop.get("name", "")).upper()
            or query_upper in str(stop.get("stop_id", "")).upper()
        ]
        return {"query": query, "count": len(matches), "sample": matches[:limit]}

    @app.get("/debug/metro/transfers/{stop_id}")
    def debug_metro_transfers_for_stop(
        stop_id: str,
        walk_type: str = "normal_transfer",
        db: Session = Depends(get_db),
    ):
        indexes = get_raptor_indexes()
        stop_details = indexes["stop_details"]
        rows = (
            db.query(WalkingTransfer)
            .filter(
                WalkingTransfer.from_stop_id == stop_id,
                WalkingTransfer.walk_type == walk_type,
            )
            .all()
        )
        metro_transfers = []
        for row in rows:
            to_stop = stop_details.get(row.to_stop_id, {"stop_id": row.to_stop_id})
            if not is_metro_stop_detail(to_stop):
                continue
            metro_transfers.append({
                "to": row.to_stop_id,
                "to_stop": to_stop,
                "distance_meters": row.distance_meters,
                "walking_time": row.walking_time,
            })
        metro_transfers.sort(key=lambda item: item["distance_meters"])
        return {
            "stop_id": stop_id,
            "from_stop": stop_details.get(stop_id, {"stop_id": stop_id}),
            "walk_type": walk_type,
            "metro_transfer_count": len(metro_transfers),
            "metro_transfers": metro_transfers,
        }

    @app.post("/debug/cache/clear-walking-transfers")
    def debug_clear_walking_transfer_cache():
        walking_transfers_cache.clear()
        return {"status": "walking_transfer_cache_cleared"}

    @app.post("/debug/cache/clear-walking-geometry")
    def debug_clear_walking_geometry_cache():
        clear_walking_geometry_cache()
        return {"status": "walking_geometry_cache_cleared"}

    @app.get("/debug/walking-geometry")
    def debug_walking_geometry(
        from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ):
        geometry = get_osrm_walking_geometry(
            {"lat": from_lat, "lon": from_lon},
            {"lat": to_lat, "lon": to_lon},
        )
        return {
            "source": "street_route" if geometry else "fallback_unavailable",
            "point_count": len(geometry) if geometry else 0,
            "cache_size": walking_geometry_cache_size(),
            "geometry": geometry or [],
        }

    @app.get("/debug/gtfs/validate")
    def debug_validate_gtfs():
        stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()
        return validate_gtfs(stops=stops, routes=routes, trips=trips, stop_times=stop_times, calendar=calendar)

    @app.get("/debug/frequencies/expand")
    def debug_expand_frequencies():
        stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()
        expanded_trips, expanded_stop_times = expand_frequencies(trips, stop_times, frequencies)
        frequency_trip_ids = set(frequencies["trip_id"].astype(str))
        remaining_template_trips = expanded_trips[
            expanded_trips["trip_id"].astype(str).isin(frequency_trip_ids)
        ]
        return {
            "original_trips": len(trips),
            "original_stop_times": len(stop_times),
            "frequency_template_trips": len(frequency_trip_ids),
            "expanded_trips": len(expanded_trips),
            "expanded_stop_times": len(expanded_stop_times),
            "remaining_template_trips": len(remaining_template_trips),
            "generated_virtual_trips": len(expanded_trips) - (len(trips) - len(frequency_trip_ids)),
            "generated_stop_times": len(expanded_stop_times) - len(
                stop_times[~stop_times["trip_id"].astype(str).isin(frequency_trip_ids)]
            ),
        }

    @app.get("/debug/index/routes-by-stop/{stop_id}")
    def debug_routes_by_stop(stop_id: str):
        indexes = get_raptor_indexes()
        return {"stop_id": stop_id, "routes": indexes["routes_by_stop"].get(stop_id, [])}

    @app.get("/debug/index/stops-by-route/{route_id}")
    def debug_stops_by_route(route_id: str):
        indexes = get_raptor_indexes()
        return {"route_id": route_id, "stops": indexes["stops_by_route"].get(route_id, [])}

    @app.get("/debug/index/trips-by-route/{route_id}")
    def debug_trips_by_route(route_id: str):
        indexes = get_raptor_indexes()
        return {"route_id": route_id, "trips": indexes["trips_by_route"].get(route_id, [])}

    @app.get("/debug/index/cache-status")
    def debug_index_cache_status():
        if raptor_indexes_cache is None:
            return {
                "status": "not_built",
                "disk_cache_exists": os.path.exists(RAPTOR_CACHE_PATH),
                "eta_segment_requests": 0 if eta_segment_requests_cache is None else len(eta_segment_requests_cache),
                "walking_transfer_cache": {
                    wt: sum(len(edges) for edges in transfers.values())
                    for wt, transfers in walking_transfers_cache.items()
                },
            }
        return {
            "status": "built",
            "disk_cache_exists": os.path.exists(RAPTOR_CACHE_PATH),
            "routes_by_stop": len(raptor_indexes_cache["routes_by_stop"]),
            "stops_by_route": len(raptor_indexes_cache["stops_by_route"]),
            "trips_by_route": len(raptor_indexes_cache["trips_by_route"]),
            "stop_times_by_trip": len(raptor_indexes_cache["stop_times_by_trip"]),
            "route_modes": len(raptor_indexes_cache["route_modes"]),
            "route_labels": len(raptor_indexes_cache["route_labels"]),
            "stop_details": len(raptor_indexes_cache["stop_details"]),
            "shape_points": len(raptor_indexes_cache["shape_points"]),
            "trip_shapes": len(raptor_indexes_cache["trip_shapes"]),
            "trip_stop_index": len(raptor_indexes_cache["trip_stop_index"]),
            "eta_segment_requests": len(get_eta_segment_requests(raptor_indexes_cache)),
            "walking_geometry_cache_size": walking_geometry_cache_size(),
            "walking_transfer_cache": {
                wt: sum(len(edges) for edges in transfers.values())
                for wt, transfers in walking_transfers_cache.items()
            },
        }

    @app.post("/debug/cache/clear-raptor-indexes")
    def debug_clear_raptor_index_cache():
        global raptor_indexes_cache, eta_segment_requests_cache
        raptor_indexes_cache = None
        eta_segment_requests_cache = None
        if os.path.exists(RAPTOR_CACHE_PATH):
            os.remove(RAPTOR_CACHE_PATH)
        return {"status": "raptor_index_cache_cleared"}

    @app.get("/debug/route/stop-to-stop")
    def debug_route_stop_to_stop(
        origin_stop_id: str,
        destination_stop_id: str,
        departure_time: int = 21600,
        max_transfers: int = 2,
        use_walking: bool = True,
        trace: str | None = None,
        db: Session = Depends(get_db),
    ):
        timings = {}
        start = time.perf_counter()
        indexes = get_raptor_indexes()
        timings["indexes_seconds"] = round(time.perf_counter() - start, 4)
        walking_transfers = {}
        if use_walking:
            start = time.perf_counter()
            walking_transfers = merge_walking_transfers(
                get_walking_transfers_from_db(db, walk_type="normal_transfer"),
                build_brt_feeder_transfers(indexes),
            )
            timings["walking_seconds"] = round(time.perf_counter() - start, 4)
        else:
            timings["walking_seconds"] = 0
        start = time.perf_counter()
        eta_estimates = get_eta_estimates_for_routing(indexes, departure_time_seconds=departure_time)
        timings["eta_seconds"] = round(time.perf_counter() - start, 4)
        timings["eta_estimate_count"] = len(eta_estimates)
        start = time.perf_counter()
        result = simple_raptor(
            indexes=indexes,
            origin_stop_id=origin_stop_id,
            destination_stop_id=destination_stop_id,
            departure_time_seconds=departure_time,
            max_transfers=max_transfers,
            walking_transfers=walking_transfers,
            eta_estimates=eta_estimates,
            trace_mode=trace,
            collect_diagnostics=True,
        )
        timings["raptor_seconds"] = round(time.perf_counter() - start, 4)
        result["timings"] = timings
        return result

    # ------------------------------------------------------------------
    # Trip-plan endpoints
    # ------------------------------------------------------------------

    app.get("/trip-plan/stop-to-stop")(trip_plan_stop_to_stop)
    app.post("/trip-plan")(trip_plan)

    # ------------------------------------------------------------------
    # Mode / agency debug
    # ------------------------------------------------------------------

    @app.get("/debug/modes/routes")
    def debug_route_modes():
        indexes = get_raptor_indexes()
        route_modes = indexes["route_modes"]
        summary: dict = {}
        for mode in route_modes.values():
            summary[mode] = summary.get(mode, 0) + 1
        return {"summary": summary, "sample": dict(list(route_modes.items())[:50])}

    @app.get("/debug/modes/routes/{route_id}")
    def debug_route_mode(route_id: str):
        indexes = get_raptor_indexes()
        return {"route_id": route_id, "mode": indexes["route_modes"].get(route_id, "unknown")}

    @app.get("/debug/agencies")
    def debug_agencies():
        stops, stop_times, trips, routes, calendar, frequencies, shapes = load_project_gtfs()
        if "agency_id" not in routes.columns:
            return {"error": "agency_id column missing"}
        agencies = routes["agency_id"].dropna().unique().tolist()
        return {"agencies": sorted([str(a) for a in agencies])}


# ---------------------------------------------------------------------------
# Module-level Trip Plan Functions (moved from nested to allow imports)
# ---------------------------------------------------------------------------

def trip_plan_stop_to_stop(
    origin_stop_id: str,
    destination_stop_id: str,
    departure_time: int = 21600,
    max_transfers: int = 2,
    use_walking: bool = True,
    debug: bool = False,
    trace: str | None = None,
    street_geometry: bool = False,
    street_geometry_scope: str = "none",
    db: Session = Depends(get_db),
):
    indexes = get_raptor_indexes()
    walking_transfers_local = {}
    if use_walking:
        walking_transfers_local = merge_walking_transfers(
            get_walking_transfers_from_db(db=db, walk_type="normal_transfer"),
            build_brt_feeder_transfers(indexes),
            build_lrt_feeder_transfers(indexes),
            build_monorail_feeder_transfers(indexes),
        )
    eta_estimates = get_eta_estimates_for_routing(indexes, departure_time_seconds=departure_time)
    raw_result = simple_raptor(
        indexes=indexes,
        origin_stop_id=origin_stop_id,
        destination_stop_id=destination_stop_id,
        departure_time_seconds=departure_time,
        max_transfers=max_transfers,
        walking_transfers=walking_transfers_local,
        eta_estimates=eta_estimates,
        trace_mode=trace if debug else None,
        collect_diagnostics=debug,
    )
    return build_trip_plan(
        raw_result, indexes, debug=debug,
        use_street_geometry=street_geometry,
        street_geometry_scope=street_geometry_scope,
    )


def trip_plan(
    request: TripPlanRequest,
    debug: bool = False,
    trace: str | None = None,
    street_geometry: bool = False,
    street_geometry_scope: str = "none",
    db: Session = Depends(get_db),
):
    timings = {}
    request_start = time.perf_counter()
    start = time.perf_counter()
    indexes = get_raptor_indexes()
    timings["indexes_seconds"] = round(time.perf_counter() - start, 4)

    stop_details = indexes["stop_details"]
    departure_time_seconds = departure_time_to_seconds(request.departure_time)
    origin = request.origin.model_dump()
    destination = request.destination.model_dump()

    start = time.perf_counter()
    origin_candidates = build_access_candidates(
        origin=origin, stop_details=stop_details,
        max_distance_meters=NORMAL_ACCESS_RADIUS_METERS,
        limit=NORMAL_ACCESS_CANDIDATE_LIMIT,
    )
    nearest_origin_brt = nearest_brt_candidates(origin, indexes)
    nearest_origin_lrt = nearest_lrt_candidates(origin, indexes)
    nearest_origin_backbone = nearest_backbone_candidates_by_mode(origin, indexes)
    nearest_origin_backbone_unbounded = nearest_backbone_candidates_unbounded(origin, indexes)
    origin_candidates = merge_candidates_with_priority(
        origin_candidates, nearest_origin_backbone, indexes=indexes,
    )[:NORMAL_ACCESS_CANDIDATE_LIMIT]
    timings["access_candidates_seconds"] = round(time.perf_counter() - start, 4)

    start = time.perf_counter()
    destination_candidates = build_egress_candidates(
        destination=destination, stop_details=stop_details,
        max_distance_meters=NORMAL_EGRESS_RADIUS_METERS,
        limit=NORMAL_EGRESS_CANDIDATE_LIMIT,
        max_extra_distance_meters=NORMAL_EGRESS_RADIUS_METERS,
    )
    nearest_destination_brt = nearest_brt_candidates(destination, indexes)
    nearest_destination_lrt = nearest_lrt_candidates(destination, indexes)
    nearest_destination_backbone = nearest_backbone_candidates_by_mode(destination, indexes)
    nearest_destination_backbone_unbounded = nearest_backbone_candidates_unbounded(destination, indexes)
    destination_candidates = merge_candidates_with_priority(
        destination_candidates, nearest_destination_backbone, indexes=indexes,
    )[:NORMAL_EGRESS_CANDIDATE_LIMIT]
    timings["egress_candidates_seconds"] = round(time.perf_counter() - start, 4)

    emergency_candidate_reason = None

    if not origin_candidates:
        start = time.perf_counter()
        origin_candidates = build_access_candidates(
            origin=origin, stop_details=stop_details,
            max_distance_meters=UNLIMITED_NEAREST_STOP_RADIUS_METERS,
            limit=NORMAL_ACCESS_CANDIDATE_LIMIT,
        )
        timings["emergency_origin_candidates_seconds"] = round(time.perf_counter() - start, 4)
        emergency_candidate_reason = (
            "no_origin_stop_within_normal_radius_using_nearest_available_stop"
        )

    if not destination_candidates:
        start = time.perf_counter()
        destination_candidates = build_egress_candidates(
            destination=destination, stop_details=stop_details,
            max_distance_meters=UNLIMITED_NEAREST_STOP_RADIUS_METERS,
            limit=NORMAL_EGRESS_CANDIDATE_LIMIT,
            max_extra_distance_meters=500,
        )
        timings["emergency_destination_candidates_seconds"] = round(time.perf_counter() - start, 4)
        emergency_candidate_reason = (
            "no_destination_stop_within_normal_radius_using_nearest_available_stop"
        )

    if not origin_candidates:
        return nearby_stop_failure_response(
            "origin", origin, stop_details,
            max_distance_meters=EMERGENCY_ACCESS_RADIUS_METERS,
        )
    if not destination_candidates:
        return nearby_stop_failure_response(
            "destination", destination, stop_details,
            max_distance_meters=EMERGENCY_EGRESS_RADIUS_METERS,
        )

    walking_transfers_local = {}
    emergency_walking_transfers = {}
    brt_feeder_transfers = {}
    lrt_feeder_transfers = {}
    monorail_feeder_transfers = {}

    if request.use_walking:
        start = time.perf_counter()
        walking_transfers_local = get_walking_transfers_from_db(db=db, walk_type="normal_transfer")
        brt_feeder_transfers = build_brt_feeder_transfers(indexes)
        lrt_feeder_transfers = build_lrt_feeder_transfers(indexes)
        monorail_feeder_transfers = build_monorail_feeder_transfers(indexes)
        emergency_walking_transfers = get_walking_transfers_from_db(db=db, walk_type="emergency_access")
        timings["walking_seconds"] = round(time.perf_counter() - start, 4)
    else:
        timings["walking_seconds"] = 0

    start = time.perf_counter()
    eta_estimates = get_eta_estimates_for_routing(indexes, departure_time_seconds=departure_time_seconds)
    timings["eta_seconds"] = round(time.perf_counter() - start, 4)
    timings["eta_estimate_count"] = len(eta_estimates)

    start = time.perf_counter()
    fallback_reason = emergency_candidate_reason
    routing_walking_transfers = merge_walking_transfers(
        walking_transfers_local, brt_feeder_transfers, lrt_feeder_transfers, monorail_feeder_transfers,
    )

    if fallback_reason and request.use_walking:
        routing_walking_transfers = merge_walking_transfers(
            walking_transfers_local, brt_feeder_transfers,
            lrt_feeder_transfers, monorail_feeder_transfers, emergency_walking_transfers,
        )

    raw_result = simple_raptor(
        indexes=indexes,
        departure_time_seconds=departure_time_seconds,
        max_transfers=request.max_transfers,
        walking_transfers=routing_walking_transfers,
        origin_candidates=origin_candidates,
        destination_candidates=destination_candidates,
        final_origin=origin,
        final_destination=destination,
        eta_estimates=eta_estimates,
        trace_mode=trace if debug else None,
        collect_diagnostics=debug,
    )

    if request.use_walking and not raw_result.get("found") and not fallback_reason:
        fallback_reason = "normal_route_not_found"
        raw_result = simple_raptor(
            indexes=indexes,
            departure_time_seconds=departure_time_seconds,
            max_transfers=request.max_transfers,
            walking_transfers=merge_walking_transfers(
                walking_transfers_local, brt_feeder_transfers,
                lrt_feeder_transfers, monorail_feeder_transfers, emergency_walking_transfers,
            ),
            origin_candidates=origin_candidates,
            destination_candidates=destination_candidates,
            final_origin=origin,
            final_destination=destination,
            eta_estimates=eta_estimates,
            trace_mode=trace if debug else None,
            collect_diagnostics=debug,
        )

    if fallback_reason and raw_result.get("found"):
        annotate_emergency_fallback(raw_result, fallback_reason)

    timings["raptor_seconds"] = round(time.perf_counter() - start, 4)
    raw_result["timings"] = timings

    build_start = time.perf_counter()
    response = build_trip_plan(
        raw_result, indexes, debug=debug,
        use_street_geometry=street_geometry,
        origin=origin,
        street_geometry_scope=street_geometry_scope,
    )
    timings["response_build_seconds"] = round(time.perf_counter() - build_start, 4)
    timings["total_seconds"] = round(time.perf_counter() - request_start, 4)

    if debug:
        routing_diagnostics = raw_result.get("routing_diagnostics", {})
        stage_timings = routing_diagnostics.get("stage_timings_seconds", {})
        performance = {
            "access_ms": round(timings.get("access_candidates_seconds", 0) * 1000, 2),
            "egress_ms": round(timings.get("egress_candidates_seconds", 0) * 1000, 2),
            "raptor_ms": round(timings.get("raptor_seconds", 0) * 1000, 2),
            "raptor_rounds_ms": round(stage_timings.get("raptor_rounds", 0) * 1000, 2),
            "label_creation_ms": round(stage_timings.get("raptor_rounds", 0) * 1000, 2),
            "dominance_checks_ms": round(stage_timings.get("raptor_rounds", 0) * 1000, 2),
            "reconstruction_ms": round(stage_timings.get("candidate_reconstruction", 0) * 1000, 2),
            "alternatives_ms": round(stage_timings.get("alternative_generation", 0) * 1000, 2),
            "alternative_deduplication_ms": round(stage_timings.get("alternative_generation", 0) * 1000, 2),
            "geometry_ms": round(timings.get("response_build_seconds", 0) * 1000, 2),
            "osrm_ms": round(timings.get("response_build_seconds", 0) * 1000, 2) if street_geometry else 0,
            "response_serialization_ms": round(timings.get("response_build_seconds", 0) * 1000, 2),
            "total_ms": round(timings.get("total_seconds", 0) * 1000, 2),
        }
        response["debug"] = {
            "timings": timings,
            "performance": performance,
            "origin_candidates": [summarize_candidate_stop(c, indexes) for c in origin_candidates],
            "destination_candidates": [summarize_candidate_stop(c, indexes) for c in destination_candidates],
            "brt_access": {
                "enabled": EXPERIMENTAL_BRT_ENABLED,
                "feeder_transfers_enabled": IZEE_ENABLE_BRT_FEEDER_TRANSFERS,
                "access_radius_m": IZEE_BRT_ACCESS_RADIUS_M,
                "backbone_access_radius_m": IZEE_BACKBONE_ACCESS_RADIUS_M,
                "backbone_candidates_per_mode": IZEE_BACKBONE_CANDIDATES_PER_MODE,
                "transfer_radius_m": IZEE_BRT_TRANSFER_RADIUS_M,
                "major_interchange_radius_m": IZEE_BRT_MAJOR_INTERCHANGE_RADIUS_M,
                "generated_brt_feeder_transfer_count": brt_feeder_transfer_count_cache,
                "nearest_origin_brt_stops": [summarize_candidate_stop(c, indexes) for c in nearest_origin_brt],
                "nearest_destination_brt_stops": [summarize_candidate_stop(c, indexes) for c in nearest_destination_brt],
                "nearest_origin_backbone_stops": [summarize_candidate_stop(c, indexes) for c in nearest_origin_backbone],
                "nearest_destination_backbone_stops": [summarize_candidate_stop(c, indexes) for c in nearest_destination_backbone],
                "nearest_origin_backbone_stops_unbounded": [summarize_candidate_stop(c, indexes) for c in nearest_origin_backbone_unbounded],
                "nearest_destination_backbone_stops_unbounded": [summarize_candidate_stop(c, indexes) for c in nearest_destination_backbone_unbounded],
                "origin_brt_injected": bool(nearest_origin_brt),
                "destination_brt_injected": bool(nearest_destination_brt),
            },
            "lrt_access": {
                "enabled": EXPERIMENTAL_LRT_ENABLED,
                "feeder_transfers_enabled": IZEE_ENABLE_LRT_FEEDER_TRANSFERS,
                "transfer_radius_m": IZEE_LRT_TRANSFER_RADIUS_M,
                "major_interchange_radius_m": IZEE_LRT_MAJOR_INTERCHANGE_RADIUS_M,
                "generated_lrt_feeder_transfer_count": lrt_feeder_transfer_count_cache,
                "nearest_origin_lrt_stops": [summarize_candidate_stop(c, indexes) for c in nearest_origin_lrt],
                "nearest_destination_lrt_stops": [summarize_candidate_stop(c, indexes) for c in nearest_destination_lrt],
                "origin_lrt_injected": bool(nearest_origin_lrt),
                "destination_lrt_injected": bool(nearest_destination_lrt),
            },
            "routing_diagnostics": routing_diagnostics,
            "lrt_debug": routing_diagnostics.get("lrt_debug"),
            "brt_debug": routing_diagnostics.get("brt_debug"),
            "round_cap_analysis": raw_result.get("routing_diagnostics", {}).get("round_cap_analysis"),
            "raptor_trace": raw_result.get("routing_diagnostics", {}).get("raptor_trace"),
        }

    return response
