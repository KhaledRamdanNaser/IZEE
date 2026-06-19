import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import SessionLocal


def main():
    db = SessionLocal()
    try:
        db.execute(text("""
            DELETE FROM alerts
            WHERE source_event_id IN (
                SELECT event_id
                FROM transit_events
                WHERE vehicle_id LIKE 'GTFS_%'
            )
            OR (
                route_id = 'CTA_M_112'
                AND type = 'disruption'
                AND message LIKE 'Service disruption on CTA_M_112.%'
            )
        """))
        db.execute(text("DELETE FROM transit_events WHERE vehicle_id LIKE 'GTFS_%'"))
        db.execute(text("DELETE FROM transit_observations WHERE vehicle_id LIKE 'GTFS_%'"))
        db.execute(text("DELETE FROM vehicle_live_state WHERE vehicle_id LIKE 'GTFS_%'"))
        db.execute(text("""
            DELETE FROM segment_statistics
            WHERE route_id = 'CTA_M_112'
              AND segment_id IN ('679_1994', '1994_1336')
        """))
        db.commit()
        print("GTFS pipeline test rows cleaned.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
