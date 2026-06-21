import pandas as pd


def load_gtfs(folder_path):
    stops = pd.read_csv(f"{folder_path}/stops.txt")
    stop_times = pd.read_csv(f"{folder_path}/stop_times.txt")
    trips = pd.read_csv(f"{folder_path}/trips.txt")
    routes = pd.read_csv(f"{folder_path}/routes.txt")
    calendar = pd.read_csv(f"{folder_path}/calendar.txt")
    frequencies = pd.read_csv(f"{folder_path}/frequencies.txt")
    shapes = pd.read_csv(f"{folder_path}/shapes.txt")

    if "shape_id" not in trips.columns and "shape_id" in shapes.columns:
        shape_ids = set(shapes["shape_id"].astype(str))

        def infer_shape_id(route_id):
            route_id = str(route_id)

            if route_id.startswith("L") and route_id[1:].isdigit():
                metro_shape_id = f"M{route_id[1:]}"

                if metro_shape_id in shape_ids:
                    return metro_shape_id

            return None

        trips["shape_id"] = trips["route_id"].apply(infer_shape_id)

    return stops, stop_times, trips, routes, calendar, frequencies, shapes


def combine_dataframes(dataframes):
    return pd.concat(dataframes, ignore_index=True, sort=False)


def load_multiple_gtfs(folder_paths):
    loaded_feeds = [load_gtfs(folder_path) for folder_path in folder_paths]

    stops = combine_dataframes([feed[0] for feed in loaded_feeds])
    stop_times = combine_dataframes([feed[1] for feed in loaded_feeds])
    trips = combine_dataframes([feed[2] for feed in loaded_feeds])
    routes = combine_dataframes([feed[3] for feed in loaded_feeds])
    calendar = combine_dataframes([feed[4] for feed in loaded_feeds])
    frequencies = combine_dataframes([feed[5] for feed in loaded_feeds])
    shapes = combine_dataframes([feed[6] for feed in loaded_feeds])

    return stops, stop_times, trips, routes, calendar, frequencies, shapes
