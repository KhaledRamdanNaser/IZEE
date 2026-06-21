import pandas as pd


def time_to_seconds(t):
    h, m, s = map(int, str(t).split(":"))
    return h * 3600 + m * 60 + s


def build_graph_from_gtfs(stop_times, trips):
    graph = {}

    # Step 1: attach route_id and direction_id to each stop_time row
    stop_times = stop_times.merge(
        trips[["trip_id", "route_id", "direction_id"]],
        on="trip_id",
        how="left"
    )

    # Step 2: sort stops inside each trip
    stop_times = stop_times.sort_values(
        by=["trip_id", "stop_sequence"]
    )

    # Step 3: loop through every consecutive pair of rows
    for i in range(len(stop_times) - 1):
        curr = stop_times.iloc[i]
        nxt = stop_times.iloc[i + 1]

        # Step 4: only connect stops from the same trip
        if curr["trip_id"] != nxt["trip_id"]:
            continue

        curr_stop = str(curr["stop_id"]) 
        next_stop = str(nxt["stop_id"])

        # Step 5: convert GTFS times into seconds
        departure_time = time_to_seconds(curr["departure_time"])
        arrival_time = time_to_seconds(nxt["arrival_time"])

        travel_time = arrival_time - departure_time

        # Step 6: skip broken time data
        if travel_time < 0:
            continue

        # Step 7: make sure both stops exist in the graph
        if curr_stop not in graph:
            graph[curr_stop] = []

        if next_stop not in graph:
            graph[next_stop] = []

        # Step 8: add forward ride edge
        graph[curr_stop].append({
            "to": next_stop,
            "mode": "ride",
            "trip_id": str(curr["trip_id"]),
            "route_id": str(curr["route_id"]),
            "direction_id": None if pd.isna(curr["direction_id"]) else int(curr["direction_id"]),
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "travel_time": travel_time
        })

    return graph