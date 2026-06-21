import pandas as pd


def validate_gtfs(stops, routes, trips, stop_times, calendar=None):
    errors = []
    warnings = []

    # -----------------------------
    # 1. Required columns
    # -----------------------------
    required_columns = {
        "stops": ["stop_id", "stop_name", "stop_lat", "stop_lon"],
        "routes": ["route_id"],
        "trips": ["trip_id", "route_id", "service_id"],
        "stop_times": ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
    }

    datasets = {
        "stops": stops,
        "routes": routes,
        "trips": trips,
        "stop_times": stop_times,
    }

    for name, df in datasets.items():
        for col in required_columns[name]:
            if col not in df.columns:
                errors.append(f"{name}.txt missing required column: {col}")

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings
        }

    # -----------------------------
    # 2. stop_times.trip_id exists in trips
    # -----------------------------
    trip_ids = set(trips["trip_id"].astype(str))
    stop_time_trip_ids = set(stop_times["trip_id"].astype(str))

    missing_trip_ids = stop_time_trip_ids - trip_ids

    if missing_trip_ids:
        errors.append(
            f"{len(missing_trip_ids)} trip_id values in stop_times do not exist in trips.txt"
        )

    # -----------------------------
    # 3. stop_times.stop_id exists in stops
    # -----------------------------
    stop_ids = set(stops["stop_id"].astype(str))
    stop_time_stop_ids = set(stop_times["stop_id"].astype(str))

    missing_stop_ids = stop_time_stop_ids - stop_ids

    if missing_stop_ids:
        errors.append(
            f"{len(missing_stop_ids)} stop_id values in stop_times do not exist in stops.txt"
        )

    # -----------------------------
    # 4. trips.route_id exists in routes
    # -----------------------------
    route_ids = set(routes["route_id"].astype(str))
    trip_route_ids = set(trips["route_id"].astype(str))

    missing_route_ids = trip_route_ids - route_ids

    if missing_route_ids:
        errors.append(
            f"{len(missing_route_ids)} route_id values in trips do not exist in routes.txt"
        )

    # -----------------------------
    # 5. trips.service_id exists in calendar
    # -----------------------------
    if calendar is not None and "service_id" in calendar.columns:
        service_ids = set(calendar["service_id"].astype(str))
        trip_service_ids = set(trips["service_id"].astype(str))

        missing_service_ids = trip_service_ids - service_ids

        if missing_service_ids:
            warnings.append(
                f"{len(missing_service_ids)} service_id values in trips do not exist in calendar.txt"
            )
    else:
        warnings.append("calendar.txt not provided or missing service_id column")

    # -----------------------------
    # 6. stop_sequence ordering check
    # -----------------------------
    broken_sequence_trips = []

    for trip_id, group in stop_times.groupby("trip_id"):
        sequences = group["stop_sequence"].tolist()

        if sequences != sorted(sequences):
            broken_sequence_trips.append(str(trip_id))

    if broken_sequence_trips:
        errors.append(
            f"{len(broken_sequence_trips)} trips have unordered stop_sequence"
        )

    # -----------------------------
    # 7. time parse check
    # -----------------------------
    bad_time_rows = []

    def is_valid_gtfs_time(value):
        try:
            parts = str(value).split(":")
            if len(parts) != 3:
                return False

            h, m, s = map(int, parts)

            # GTFS allows hour > 23
            return m >= 0 and m < 60 and s >= 0 and s < 60
        except Exception:
            return False

    for idx, row in stop_times.iterrows():
        if not is_valid_gtfs_time(row["arrival_time"]):
            bad_time_rows.append(idx)

        if not is_valid_gtfs_time(row["departure_time"]):
            bad_time_rows.append(idx)

    if bad_time_rows:
        errors.append(
            f"{len(bad_time_rows)} stop_times rows have invalid arrival/departure time"
        )

    # -----------------------------
    # 8. direction_id check
    # -----------------------------
    if "direction_id" not in trips.columns:
        warnings.append("trips.txt missing direction_id; default to unknown")
    else:
        invalid_direction = trips[
            ~trips["direction_id"].isin([0, 1])
            & trips["direction_id"].notna()
        ]

        if len(invalid_direction) > 0:
            warnings.append(
                f"{len(invalid_direction)} trips have invalid direction_id"
            )

    # -----------------------------
    # 9. route mode inference check
    # -----------------------------
    if "route_type" not in routes.columns:
        warnings.append("routes.txt missing route_type; mode must be inferred manually")

    if "agency_id" not in routes.columns:
        warnings.append("routes.txt missing agency_id; Egypt mode mapping will be weaker")

    # -----------------------------
    # Final report
    # -----------------------------
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "stops": len(stops),
            "routes": len(routes),
            "trips": len(trips),
            "stop_times": len(stop_times),
            "calendar_rows": 0 if calendar is None else len(calendar)
        }
    }