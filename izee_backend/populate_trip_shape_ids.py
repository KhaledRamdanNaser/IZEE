import csv
from pathlib import Path

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

# Adjust the DATABASE_URL according to your project's configuration
from database.connection import DATABASE_URL, Base
from models.trip import Trip

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# GTFS root directory – change if your data location differs
GTFS_ROOT = Path(__file__).parents[1] / "data" / "gtfs_experimental"

def load_trip_shape_map():
    """Build a dict mapping trip_id -> shape_id from all trips.txt files."""
    mapping = {}
    for trips_file in GTFS_ROOT.rglob('trips.txt'):
        with open(trips_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trip_id = row.get('trip_id')
                shape_id = row.get('shape_id')
                if trip_id and shape_id:
                    mapping[trip_id] = shape_id
    return mapping

def backfill_shape_ids():
    mapping = load_trip_shape_map()
    if not mapping:
        print('No trip/shape mappings found – check GTFS path.')
        return
    with SessionLocal() as session:
        batch = []
        for trip_id, shape_id in mapping.items():
            stmt = (
                update(Trip)
                .where(Trip.trip_id == trip_id)
                .values(shape_id=shape_id)
            )
            session.execute(stmt)
            batch.append(trip_id)
            if len(batch) >= 500:
                session.commit()
                print(f'Committed {len(batch)} updates')
                batch.clear()
        if batch:
            session.commit()
            print(f'Committed final {len(batch)} updates')
    print('Shape IDs backfilled for', len(mapping), 'trips')

if __name__ == '__main__':
    backfill_shape_ids()
