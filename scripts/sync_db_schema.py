import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal


STATEMENTS = [
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS route_id VARCHAR",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS direction INTEGER",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS day_of_week VARCHAR",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS day_number INTEGER",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS time_period VARCHAR",
    "ALTER TABLE transit_observations ADD COLUMN IF NOT EXISTS simulation_seed INTEGER",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS route_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS timestamp VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS matched_lat DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS matched_lon DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS current_stop_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS next_stop_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS stop_sequence INTEGER",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS segment_id VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS segment_progress DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS progress DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS distance_to_next_stop DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS speed DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS direction VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS movement VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS movement_state VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS current_delay DOUBLE PRECISION",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS confidence VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS source VARCHAR",
    "ALTER TABLE vehicle_live_state ADD COLUMN IF NOT EXISTS simulation_flag BOOLEAN",
]


def main():
    db = SessionLocal()
    try:
        for statement in STATEMENTS:
            db.execute(text(statement))
        db.commit()
        print("Database schema sync complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
