import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alert_engine.engine import process_events_batch
from alert_engine.models import Alert
from database.connection import Base, SessionLocal, engine
import models.segment_statistics
import models.transit_event


ROUTE_ID = "SMOKE_ROUTE"
SEGMENT_ID = "SMOKE_SEGMENT_1"


def cleanup_smoke_data(db):
    db.execute(text("""
        DELETE FROM alerts
        WHERE route_id = :route_id
           OR source_event_id LIKE 'SMOKE_%'
    """), {"route_id": ROUTE_ID})
    db.execute(text("""
        DELETE FROM transit_events
        WHERE event_id LIKE 'SMOKE_%'
    """))
    db.execute(text("""
        DELETE FROM segment_statistics
        WHERE route_id = :route_id
    """), {"route_id": ROUTE_ID})
    db.commit()


def seed_smoke_data(db):
    now = datetime.now(timezone.utc).isoformat()

    db.execute(text("""
        INSERT INTO segment_statistics (
            segment_id, route_id, direction, day_type, time_period,
            avg_travel_time, median_travel_time, std_travel_time,
            sample_count, last_updated
        )
        VALUES (
            :segment_id, :route_id, 0, 'weekday', 'peak',
            100, 100, 10, 50, NOW()
        )
    """), {
        "segment_id": SEGMENT_ID,
        "route_id": ROUTE_ID,
    })

    events = [
        {
            "event_id": "SMOKE_DELAY_1",
            "event_type": "segment_completed",
            "vehicle_id": "SMOKE_BUS_1",
            "route_id": ROUTE_ID,
            "timestamp": now,
            "segment_id": SEGMENT_ID,
            "direction": 0,
            "day_of_week": "Monday",
            "time_period": "peak",
            "metrics": '{"travel_time": 250}',
        },
        {
            "event_id": "SMOKE_DELAY_2",
            "event_type": "segment_completed",
            "vehicle_id": "SMOKE_BUS_2",
            "route_id": ROUTE_ID,
            "timestamp": now,
            "segment_id": SEGMENT_ID,
            "direction": 0,
            "day_of_week": "Monday",
            "time_period": "peak",
            "metrics": '{"travel_time": 320}',
        },
        {
            "event_id": "SMOKE_DELAY_3",
            "event_type": "segment_completed",
            "vehicle_id": "SMOKE_BUS_3",
            "route_id": ROUTE_ID,
            "timestamp": now,
            "segment_id": SEGMENT_ID,
            "direction": 0,
            "day_of_week": "Monday",
            "time_period": "peak",
            "metrics": '{"travel_time": 210}',
        },
        {
            "event_id": "SMOKE_DWELL_1",
            "event_type": "dwell_time",
            "vehicle_id": "SMOKE_BUS_4",
            "route_id": ROUTE_ID,
            "timestamp": now,
            "stop_id": "SMOKE_STOP_1",
            "metrics": '{"dwell_time": 360}',
        },
    ]

    for event in events:
        db.execute(text("""
            INSERT INTO transit_events (
                event_id, event_type, vehicle_id, route_id, timestamp,
                stop_id, segment_id, direction, day_of_week, time_period,
                metrics, confidence, source, simulation_flag
            )
            VALUES (
                :event_id, :event_type, :vehicle_id, :route_id, :timestamp,
                :stop_id, :segment_id, :direction, :day_of_week, :time_period,
                CAST(:metrics AS JSON), 'high', 'smoke_test', TRUE
            )
        """), {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "vehicle_id": event["vehicle_id"],
            "route_id": event["route_id"],
            "timestamp": event["timestamp"],
            "stop_id": event.get("stop_id"),
            "segment_id": event.get("segment_id"),
            "direction": event.get("direction"),
            "day_of_week": event.get("day_of_week"),
            "time_period": event.get("time_period"),
            "metrics": event["metrics"],
        })

    db.commit()


def print_smoke_alerts(db):
    rows = db.execute(text("""
        SELECT type, severity, vehicle_id, route_id, segment_id, message
        FROM alerts
        WHERE route_id = :route_id
        ORDER BY type, severity, vehicle_id NULLS LAST
    """), {"route_id": ROUTE_ID}).fetchall()

    print()
    print("SMOKE TEST ALERTS:")
    for row in rows:
        data = dict(row._mapping)
        print(
            f"- {data['type']} | {data['severity']} | "
            f"vehicle={data['vehicle_id']} | {data['message']}"
        )
    print()
    print(f"Total smoke alerts: {len(rows)}")


def main():
    print("=" * 60)
    print("IZEE Alert Engine -- Smoke Test")
    print("=" * 60)

    Base.metadata.create_all(bind=engine, tables=[Alert.__table__])

    db = SessionLocal()
    try:
        cleanup_smoke_data(db)
        seed_smoke_data(db)
        summary = process_events_batch(db)

        print()
        print("RESULTS:")
        print(f"  Segment events checked: {summary['segment_events_checked']}")
        print(f"  Dwell events checked:   {summary['dwell_events_checked']}")
        print(f"  Alerts created:         {summary['alerts_created']}")
        print(f"  Delay alerts:           {summary['delay_alerts']}")
        print(f"  Disruptions:            {summary['disruptions']}")
        print(f"  Skipped (dedup):        {summary['skipped_dedup']}")

        print_smoke_alerts(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
