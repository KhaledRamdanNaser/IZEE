import csv
from database.connection import SessionLocal
from models.agency import Agency
from models.stop import Stop
from models.route import Route
from models.trip import Trip
from models.stop_time import StopTime


def load_agencies():
    db = SessionLocal()

    with open("gtfs/agency.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            db.add(Agency(
                agency_id=row["agency_id"],
                name=row["agency_name"]
            ))

    db.commit()
    db.close()
    print("Agencies loaded")


def load_stops():
    db = SessionLocal()

    with open("gtfs/stops.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            db.add(Stop(
                stop_id=row["stop_id"],
                name=row["stop_name"],
                lat=float(row["stop_lat"]),
                lon=float(row["stop_lon"])
            ))

    db.commit()
    db.close()
    print("Stops loaded")


def load_routes():
    db = SessionLocal()

    with open("gtfs/routes.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            db.add(Route(
                route_id=row["route_id"],
                route_name=row["route_long_name"],
                agency_id=row["agency_id"]
            ))

    db.commit()
    db.close()
    print("Routes loaded")


def load_trips():
    db = SessionLocal()

    with open("gtfs/trips.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            db.add(Trip(
                trip_id=row["trip_id"],
                route_id=row["route_id"],
                direction_id=int(row["direction_id"])
            ))

    db.commit()
    db.close()
    print("Trips loaded")


def load_stop_times():
    db = SessionLocal()

    with open("gtfs/stop_times.txt", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            db.add(StopTime(
                trip_id=row["trip_id"],
                stop_id=row["stop_id"],
                stop_sequence=int(row["stop_sequence"])
            ))

    db.commit()
    db.close()
    print("StopTimes loaded")


if __name__ == "__main__":
    load_agencies()
    load_stops()
    load_routes()
    load_trips()
    load_stop_times()