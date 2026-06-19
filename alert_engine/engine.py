import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from alert_engine.aggregator import check_route_disruptions
from alert_engine.deduplicator import should_create_alert
from alert_engine.models import Alert
from alert_engine.rules import handle_dwell_time, handle_segment_completed


logger = logging.getLogger(__name__)

DAY_TYPE_MAP = {
    "Monday": "weekday",
    "Tuesday": "weekday",
    "Wednesday": "weekday",
    "Thursday": "weekday",
    "Sunday": "weekday",
    "Friday": "friday",
    "Saturday": "saturday",
}


def _fetch_segment_stats(db: Session, event_row: dict) -> dict | None:
    day_type = DAY_TYPE_MAP.get(event_row.get("day_of_week"))
    if not day_type:
        return None

    row = db.execute(text("""
        SELECT avg_travel_time, std_travel_time, sample_count
        FROM segment_statistics
        WHERE segment_id = :segment_id
          AND route_id = :route_id
          AND direction = :direction
          AND day_type = :day_type
          AND time_period = :time_period
        LIMIT 1
    """), {
        "segment_id": event_row.get("segment_id"),
        "route_id": event_row.get("route_id"),
        "direction": event_row.get("direction"),
        "day_type": day_type,
        "time_period": event_row.get("time_period"),
    }).fetchone()

    return dict(row._mapping) if row else None


def _build_alert_orm(alert_dict: dict) -> Alert:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=alert_dict["expires_minutes"])

    return Alert(
        alert_id=uuid.uuid4(),
        type=alert_dict["type"],
        severity=alert_dict["severity"],
        message=alert_dict["message"],
        route_id=alert_dict.get("route_id"),
        vehicle_id=alert_dict.get("vehicle_id"),
        segment_id=alert_dict.get("segment_id"),
        source_event_id=alert_dict.get("source_event_id"),
        lat=alert_dict.get("lat"),
        lon=alert_dict.get("lon"),
        created_at=now,
        expires_at=expires_at,
        eta_based=False,
    )


def _fetch_segment_completed_events(db: Session):
    return db.execute(text("""
        SELECT event_id, event_type, vehicle_id, route_id,
               segment_id, direction, day_of_week, time_period,
               timestamp, metrics
        FROM transit_events
        WHERE event_type = 'segment_completed'
          AND (metrics->>'travel_time') IS NOT NULL
          AND (metrics->>'travel_time')::float > 30
    """)).fetchall()


def _fetch_dwell_events(db: Session):
    return db.execute(text("""
        SELECT event_id, event_type, vehicle_id, route_id,
               stop_id, timestamp, metrics
        FROM transit_events
        WHERE event_type = 'dwell_time'
    """)).fetchall()


def process_events_batch(db: Session) -> dict:
    logger.info("Alert Engine: starting batch processing")

    seg_events = _fetch_segment_completed_events(db)
    dwell_events = _fetch_dwell_events(db)

    delay_alerts_created = []
    alerts_to_insert = []
    created_count = 0
    skipped_dedup = 0

    for row in seg_events:
        event = dict(row._mapping)
        stats = _fetch_segment_stats(db, event)
        alert_dict = handle_segment_completed(event, stats)
        if alert_dict is None:
            continue

        if not should_create_alert(alert_dict.get("vehicle_id"), "delay", db):
            skipped_dedup += 1
            continue

        delay_alerts_created.append(alert_dict)
        alerts_to_insert.append(_build_alert_orm(alert_dict))
        created_count += 1

    for row in dwell_events:
        event = dict(row._mapping)
        alert_dict = handle_dwell_time(event)
        if alert_dict is None:
            continue

        if not should_create_alert(alert_dict.get("vehicle_id"), "dwell_issue", db):
            skipped_dedup += 1
            continue

        alerts_to_insert.append(_build_alert_orm(alert_dict))
        created_count += 1

    disruption_dicts = check_route_disruptions(delay_alerts_created)
    for alert_dict in disruption_dicts:
        if not should_create_alert(alert_dict.get("route_id"), "disruption", db):
            skipped_dedup += 1
            continue

        alerts_to_insert.append(_build_alert_orm(alert_dict))
        created_count += 1

    if alerts_to_insert:
        db.bulk_save_objects(alerts_to_insert)
        db.commit()
        logger.info("Alert Engine: inserted %s alerts", created_count)
    else:
        logger.info("Alert Engine: no new alerts generated")

    return {
        "alerts_created": created_count,
        "skipped_dedup": skipped_dedup,
        "delay_alerts": len(delay_alerts_created),
        "disruptions": len(disruption_dicts),
        "segment_events_checked": len(seg_events),
        "dwell_events_checked": len(dwell_events),
    }
