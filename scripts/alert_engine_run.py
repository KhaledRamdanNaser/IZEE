import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alert_engine.engine import process_events_batch
from alert_engine.models import Alert
from database.connection import Base, SessionLocal, engine


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    print("=" * 60)
    print("IZEE Alert Engine -- Batch Processing")
    print("=" * 60)

    Base.metadata.create_all(bind=engine, tables=[Alert.__table__])

    db = SessionLocal()
    try:
        summary = process_events_batch(db)
        print()
        print("RESULTS:")
        print(f"  Segment events checked: {summary['segment_events_checked']}")
        print(f"  Dwell events checked:   {summary['dwell_events_checked']}")
        print(f"  Alerts created:         {summary['alerts_created']}")
        print(f"  Delay alerts:           {summary['delay_alerts']}")
        print(f"  Disruptions:            {summary['disruptions']}")
        print(f"  Skipped (dedup):        {summary['skipped_dedup']}")
        print()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
