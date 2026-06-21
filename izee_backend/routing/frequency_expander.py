import pandas as pd


def time_to_seconds(t):
    h, m, s = map(int, str(t).split(":"))
    return h * 3600 + m * 60 + s


def seconds_to_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def expand_frequencies(trips, stop_times, frequencies):
    """
    Converts frequency-based GTFS trips into exact virtual trips.

    Example:
    trip T1 runs 06:00-07:00 every 600 sec
    -> T1__freq__21600, T1__freq__22200, T1__freq__22800, ...
    """

    if frequencies is None or len(frequencies) == 0:
        return trips, stop_times

    new_trips = []
    new_stop_times = []

    trips_by_id = {
        str(row["trip_id"]): row
        for row in trips.to_dict("records")
    }

    stop_times_by_trip = {
        str(trip_id): group.sort_values("stop_sequence").to_dict("records")
        for trip_id, group in stop_times.groupby("trip_id")
    }

    for _, freq in frequencies.iterrows():
        base_trip_id = str(freq["trip_id"])

        if base_trip_id not in trips_by_id:
            continue

        if base_trip_id not in stop_times_by_trip:
            continue

        start = time_to_seconds(freq["start_time"])
        end = time_to_seconds(freq["end_time"])

        if pd.isna(freq["headway_secs"]):
            continue

        headway = int(freq["headway_secs"])

        if headway <= 0:
            continue

        base_trip = trips_by_id[base_trip_id]
        base_stop_times = stop_times_by_trip[base_trip_id]

        first_departure = time_to_seconds(
            base_stop_times[0]["departure_time"]
        )

        current = start

        while current < end:
            offset = current - first_departure
            virtual_trip_id = f"{base_trip_id}__freq__{current}"

            trip_copy = dict(base_trip)
            trip_copy["trip_id"] = virtual_trip_id
            new_trips.append(trip_copy)

            for st in base_stop_times:
                st_copy = dict(st)
                st_copy["trip_id"] = virtual_trip_id

                arr = time_to_seconds(st["arrival_time"]) + offset
                dep = time_to_seconds(st["departure_time"]) + offset

                st_copy["arrival_time"] = seconds_to_time(arr)
                st_copy["departure_time"] = seconds_to_time(dep)

                new_stop_times.append(st_copy)

            current += headway

    frequency_trip_ids = set(frequencies["trip_id"].astype(str))

    base_trips = trips[
        ~trips["trip_id"].astype(str).isin(frequency_trip_ids)
    ].copy()

    base_stop_times = stop_times[
        ~stop_times["trip_id"].astype(str).isin(frequency_trip_ids)
    ].copy()

    expanded_trips = pd.concat(
        [base_trips, pd.DataFrame(new_trips, columns=trips.columns)],
        ignore_index=True
    )

    expanded_stop_times = pd.concat(
        [base_stop_times, pd.DataFrame(new_stop_times, columns=stop_times.columns)],
        ignore_index=True
    )

    return expanded_trips, expanded_stop_times
