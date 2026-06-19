import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal
from loaders.load_gtfs import (
    load_agencies,
    load_routes,
    load_stop_times,
    load_stops,
    load_trips,
)
from models.agency import Agency
from models.route import Route
from models.stop import Stop
from models.stop_time import StopTime
from models.trip import Trip


def table_counts():
    db = SessionLocal()
    try:
        return {
            "agency": db.query(Agency).count(),
            "route": db.query(Route).count(),
            "trip": db.query(Trip).count(),
            "stop": db.query(Stop).count(),
            "stop_time": db.query(StopTime).count(),
        }
    finally:
        db.close()


def main():
    counts = table_counts()
    print("GTFS reference counts before load:", counts)

    if all(count > 0 for count in counts.values()):
        print("GTFS reference tables already loaded. Skipping load.")
        return

    if any(count > 0 for count in counts.values()):
        raise RuntimeError(
            "Some GTFS reference tables are loaded and some are empty. "
            "Clean or complete the reference data before continuing."
        )

    load_agencies()
    load_stops()
    load_routes()
    load_trips()
    load_stop_times()

    print("GTFS reference counts after load:", table_counts())


if __name__ == "__main__":
    main()
